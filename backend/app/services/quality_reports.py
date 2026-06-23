"""Quality reports for generated answers and vectorized documents."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Optional

from app.schemas.chat import SourceInfo
from app.security import sanitize_text
from app.services.milvus_vector_service import VectorIndexResult


SENSITIVE_MARKERS = ("[身份证号已脱敏]", "[手机号已脱敏]", "[银行卡号已脱敏]", "[邮箱已脱敏]")


@dataclass(frozen=True)
class QualityDimension:
    key: str
    label: str
    score: int
    weight: float
    passed: bool
    detail: str


@dataclass(frozen=True)
class QualityReport:
    """质量报告的统一结构。

    前端不需要理解所有规则细节，只看 score、grade、status、findings
    和 recommendations 就能知道“这次回答/入库是否值得人工复核”。
    """

    report_type: str
    score: int
    grade: str
    status: str
    dimensions: list[QualityDimension] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def model_dump(self) -> dict:
        return asdict(self)


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "E"


def _status(score: int) -> str:
    if score >= 80:
        return "pass"
    if score >= 60:
        return "warning"
    return "fail"


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _source_coverage_score(sources: list[SourceInfo]) -> tuple[int, str, bool]:
    if not sources:
        return 35, "未返回可追溯来源", False
    with_snippet = sum(1 for item in sources if item.snippet)
    score = min(100, 62 + len(sources) * 10 + with_snippet * 4)
    return score, f"返回 {len(sources)} 个来源，其中 {with_snippet} 个包含摘要", score >= 75


def _latency_dimension(response_time_ms: Optional[int]) -> QualityDimension:
    if response_time_ms is None:
        return QualityDimension("latency", "问答耗时", 88, 0.06, True, "尚未写入完整接口耗时")
    if response_time_ms <= 3000:
        return QualityDimension("latency", "问答耗时", 95, 0.06, True, f"完整接口耗时 {response_time_ms}ms")
    if response_time_ms <= 10000:
        return QualityDimension("latency", "问答耗时", 82, 0.06, True, f"完整接口耗时 {response_time_ms}ms")
    if response_time_ms <= 30000:
        return QualityDimension("latency", "问答耗时", 65, 0.06, False, f"完整接口耗时 {response_time_ms}ms")
    return QualityDimension("latency", "问答耗时", 45, 0.06, False, f"完整接口耗时 {response_time_ms}ms")


def _latency_recommendations(response_time_ms: Optional[int], provider: str) -> list[str]:
    if response_time_ms is None:
        return []
    if response_time_ms <= 10000:
        return []
    if provider == "dify":
        return ["本次 Dify 链路耗时偏高，建议检查 Dify 工作流节点、外部知识库检索和 `DIFY_TIMEOUT_SECONDS`。"]
    if provider == "langchain":
        return ["本次 LangChain 链路耗时偏高，建议检查 Milvus TopK、rerank 开关、Prompt 长度和模型服务响应。"]
    return ["本次问答耗时偏高，建议在后台日志按 provider、风险等级和问题长度分组排查慢请求。"]


def build_answer_quality_report(
    *,
    question: str,
    answer: str,
    sources: Optional[list[SourceInfo]],
    provider: str,
    risk_level: str,
    fallback_reason: Optional[str] = None,
    response_time_ms: Optional[int] = None,
) -> QualityReport:
    """生成回答质量报告。

    这里不用 LLM 评分，而是用确定性规则检查来源、结构、风险等级、
    可执行建议、隐私脱敏和链路状态，便于测试和复现。
    """
    answer_text = sanitize_text(answer) or ""
    normalized = _normalize_space(answer_text)
    source_items = sources or []
    faq_source_count = sum(1 for item in source_items if getattr(item, "source_type", None) == "faq" or item.title.startswith("[FAQ]"))
    document_source_count = sum(1 for item in source_items if getattr(item, "source_type", None) == "document" or item.title.startswith("[文档]"))
    findings: list[str] = []
    recommendations: list[str] = []
    latency_dimension = _latency_dimension(response_time_ms)
    latency_recommendations = _latency_recommendations(response_time_ms, provider)
    if provider == "precheck":
        # precheck 表示问题在模型调用前就被规则处理，例如问候或能力说明。
        dimensions = [
            QualityDimension("intent_routing", "意图路由", 95, 0.36, True, "已在模型调用前完成简单问候或非业务问题识别"),
            QualityDimension("scope_control", "范围控制", 92, 0.27, True, "未进入知识库检索或外部模型生成"),
            QualityDimension("privacy_safety", "隐私安全", 100, 0.19, True, "未发现未脱敏敏感信息"),
            QualityDimension("provider_health", "链路状态", 80, 0.12, True, "provider=precheck"),
            latency_dimension,
        ]
        score = round(sum(item.score * item.weight for item in dimensions))
        return QualityReport(
            report_type="answer",
            score=score,
            grade=_grade(score),
            status=_status(score),
            dimensions=dimensions,
            findings=["问题已由前置规则处理，未触发知识库检索或模型调用。"],
            recommendations=(["请继续输入劳动用工、社保、医保、假期、工资或劳动争议等合规问题。"] + latency_recommendations)[:6],
            metrics={
                "answer_characters": len(normalized),
                "source_count": 0,
                "faq_source_count": 0,
                "document_source_count": 0,
                "provider": provider,
                "risk_level": risk_level,
                "response_time_ms": response_time_ms,
            },
        )

    if provider == "kb_no_match":
        # kb_no_match 是“知识库边界保护”命中：没有证据就不生成结论。
        source_score, source_detail, source_passed = _source_coverage_score(source_items)
        dimensions = [
            QualityDimension("knowledge_boundary", "知识库边界", 92, 0.30, True, "未命中时已阻止外部常识回答"),
            QualityDimension("source_coverage", "来源覆盖", source_score, 0.22, source_passed, source_detail),
            QualityDimension("risk_label", "风险标注", 88, 0.13, True, "已返回风险等级或待核验提示"),
            QualityDimension("actionability", "可执行性", 78, 0.13, True, "已提示补充事实或上传审核资料"),
            QualityDimension("privacy_safety", "隐私安全", 100, 0.1, True, "未发现未脱敏敏感信息"),
            QualityDimension("provider_health", "链路状态", 76, 0.06, True, "provider=kb_no_match"),
            latency_dimension,
        ]
        score = round(sum(item.score * item.weight for item in dimensions))
        return QualityReport(
            report_type="answer",
            score=score,
            grade=_grade(score),
            status=_status(score),
            dimensions=dimensions,
            findings=["系统内问题未命中可用知识库证据，已按知识库边界策略停止生成。"],
            recommendations=(["请补充地区、员工身份、时间节点等事实，或先上传并审核相关政策、企业制度、FAQ 后重试。"] + latency_recommendations)[:6],
            metrics={
                "answer_characters": len(normalized),
                "source_count": len(source_items),
                "faq_source_count": faq_source_count,
                "document_source_count": document_source_count,
                "provider": provider,
                "risk_level": risk_level,
                "response_time_ms": response_time_ms,
            },
        )

    source_score, source_detail, source_passed = _source_coverage_score(source_items)
    if not source_passed:
        recommendations.append("补充官方来源、FAQ 或 Milvus 检索片段，提升回答可追溯性。")

    structure_words = ("结论", "依据", "建议", "行动", "待核验", "风险")
    structure_hits = sum(1 for word in structure_words if word in answer_text)
    structure_score = min(100, 35 + structure_hits * 12 + (15 if "\n" in answer_text else 0))
    if structure_score < 75:
        recommendations.append("回答应包含结论、依据、行动建议和待核验项。")

    risk_mentions = ("风险等级", "高风险", "中风险", "低风险", "high", "medium", "low", "高", "中", "低")
    risk_present = _contains_any(answer_text, risk_mentions) or risk_level in {"high", "medium", "low"}
    risk_score = 90 if risk_present else 45
    if not risk_present:
        recommendations.append("补充明确的风险等级，便于业务人员判断优先级。")

    action_present = _contains_any(answer_text, ("建议", "应", "需要", "办理", "复核", "核验", "准备", "步骤"))
    verification_present = _contains_any(answer_text, ("待核验", "复核", "以当地", "官方", "经办", "最终"))
    guidance_score = 45 + (25 if action_present else 0) + (25 if verification_present else 0)
    if guidance_score < 80:
        recommendations.append("补充可执行的处理步骤和需人工复核的政策口径。")

    sanitized = any(marker in answer_text for marker in SENSITIVE_MARKERS)
    raw_sensitive = sanitize_text(answer_text) != answer_text
    safety_score = 100 if not raw_sensitive else 55
    if sanitized:
        findings.append("回答中包含已脱敏的个人信息标记。")
    if raw_sensitive:
        recommendations.append("回答中仍存在疑似敏感信息，应在输出前完成脱敏。")

    length = len(normalized)
    if length < 80:
        length_score = 45
        recommendations.append("回答偏短，建议补充依据和行动清单。")
    elif length > 4000:
        length_score = 70
        recommendations.append("回答偏长，建议压缩重复内容并突出结论。")
    else:
        length_score = 92

    provider_score = 90
    if provider in {"langchain_unavailable", "dify_unavailable", "knowledge_package_disabled", "provider_disabled"}:
        provider_score = 60
        findings.append(f"当前回答使用降级引擎：{provider}。")
    if fallback_reason:
        findings.append(f"回退原因：{fallback_reason}")
    recommendations.extend(latency_recommendations)

    dimensions = [
        QualityDimension("source_coverage", "来源覆盖", source_score, 0.2, source_passed, source_detail),
        QualityDimension("answer_structure", "结构完整", structure_score, 0.17, structure_score >= 75, f"命中 {structure_hits} 个结构要素"),
        QualityDimension("risk_label", "风险标注", risk_score, 0.13, risk_score >= 75, "已识别风险等级" if risk_present else "缺少风险等级"),
        QualityDimension("actionability", "可执行性", guidance_score, 0.17, guidance_score >= 80, "包含行动建议与复核提示" if guidance_score >= 80 else "行动或复核提示不足"),
        QualityDimension("privacy_safety", "隐私安全", safety_score, 0.13, safety_score >= 80, "未发现未脱敏敏感信息" if safety_score >= 80 else "存在疑似敏感信息"),
        QualityDimension("answer_length", "篇幅适中", length_score, 0.08, length_score >= 80, f"回答长度 {length} 字符"),
        QualityDimension("provider_health", "链路状态", provider_score, 0.06, provider_score >= 80, f"provider={provider}"),
        latency_dimension,
    ]
    score = round(sum(item.score * item.weight for item in dimensions))
    if not findings:
        findings.append("回答质量规则检查未发现明显问题。")
    if not recommendations:
        recommendations.append("当前回答可进入人工复核或直接用于一般咨询场景。")

    return QualityReport(
        report_type="answer",
        score=score,
        grade=_grade(score),
        status=_status(score),
        dimensions=dimensions,
        findings=findings[:6],
        recommendations=recommendations[:6],
        metrics={
            "answer_characters": length,
            "source_count": len(source_items),
            "faq_source_count": faq_source_count,
            "document_source_count": document_source_count,
            "provider": provider,
            "risk_level": risk_level,
            "response_time_ms": response_time_ms,
        },
    )


def build_vector_ingest_quality_report(
    *,
    result: VectorIndexResult,
    title: Optional[str],
    source_id: Optional[int],
    tenant_code: str,
) -> QualityReport:
    """生成文档入库质量报告。

    文档成功写入 Milvus 不代表质量一定好：可能文本太短、切分异常、
    没有标题或没关联来源。这个报告用于提醒运营人员补资料。
    """
    findings: list[str] = []
    recommendations: list[str] = []
    characters = int(result.characters or 0)
    chunks = int(result.chunks or 0)
    title_text = (title or result.title or "").strip()

    if characters < 500:
        text_score = 50
        recommendations.append("文档文本较短，建议确认是否解析完整或是否上传了扫描件。")
    elif characters > 300000:
        text_score = 72
        recommendations.append("文档过长，建议拆分为法规、指南或企业制度等更小主题后入库。")
    else:
        text_score = 94

    if chunks <= 0:
        chunk_score = 20
        recommendations.append("未生成 chunk，请检查文档解析和切分配置。")
    elif chunks == 1 and characters > 2500:
        chunk_score = 68
        recommendations.append("文档较长但只生成 1 个 chunk，建议检查 `vector_chunk_size` 配置。")
    else:
        chunk_score = 92

    metadata_score = 55
    metadata_notes = []
    if title_text:
        metadata_score += 20
        metadata_notes.append("标题完整")
    else:
        metadata_notes.append("缺少标题")
        recommendations.append("入库时补充标准标题，提升检索结果可读性。")
    if source_id:
        metadata_score += 15
        metadata_notes.append("已关联来源")
    else:
        metadata_notes.append("未关联来源")
        recommendations.append("建议关联来源目录 `source_id`，方便回答回链官方依据。")
    if tenant_code:
        metadata_score += 10
    metadata_score = min(metadata_score, 100)

    density = round(characters / chunks) if chunks else 0
    density_score = 90
    if density and density < 180:
        density_score = 68
        recommendations.append("平均 chunk 较短，建议检查是否存在表格噪声或过度换行。")
    elif density > 2500:
        density_score = 72
        recommendations.append("平均 chunk 较长，可能影响召回精度，建议降低切分长度。")

    safety_score = 100
    if any(marker in result.title or "" for marker in SENSITIVE_MARKERS):
        safety_score = 80
        findings.append("标题中包含脱敏标记。")

    dimensions = [
        QualityDimension("text_volume", "文本规模", text_score, 0.24, text_score >= 75, f"解析 {characters} 字符"),
        QualityDimension("chunking", "切分结果", chunk_score, 0.22, chunk_score >= 75, f"生成 {chunks} 个 chunk"),
        QualityDimension("metadata", "元数据完整", metadata_score, 0.24, metadata_score >= 75, "，".join(metadata_notes)),
        QualityDimension("chunk_density", "切分密度", density_score, 0.16, density_score >= 75, f"平均 {density} 字符/chunk" if density else "无 chunk"),
        QualityDimension("privacy_safety", "隐私安全", safety_score, 0.14, safety_score >= 80, "未发现标题敏感信息"),
    ]
    score = round(sum(item.score * item.weight for item in dimensions))
    if not findings:
        findings.append("文档已完成解析、切分和 Milvus 写入。")
    if not recommendations:
        recommendations.append("当前文档入库质量良好，可进入问答检索验证。")

    return QualityReport(
        report_type="vector_ingest",
        score=score,
        grade=_grade(score),
        status=_status(score),
        dimensions=dimensions,
        findings=findings[:6],
        recommendations=recommendations[:6],
        metrics={
            "characters": characters,
            "chunks": chunks,
            "average_chunk_characters": density,
            "collection": result.collection,
            "document_id": result.document_id,
            "tenant_code": tenant_code,
            "source_id": source_id or 0,
        },
    )
