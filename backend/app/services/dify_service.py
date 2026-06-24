"""Dify、LangChain 与向量知识库的统一问答服务。"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Optional, cast

import requests
from sqlalchemy.orm import Session

from app.database import settings
from app.models import KnowledgePackage, Source, Tenant
from app.schemas.chat import ChatResponse, SourceInfo, TaskInfo
from app.security import sanitize_text
from app.services.langchain_provider import (
    LangChainComplianceProvider,
    LangChainPromptContext,
    LangChainUnavailable,
)
from app.services.local_model_service import local_model_status
from app.services.milvus_vector_service import MilvusVectorService, VectorStoreUnavailable
from app.services.question_guard import QuestionGuardDecision, classify_question
from app.services.quality_reports import build_answer_quality_report
from app.services.runtime_config import DEFAULT_QUERY_STRATEGY, QUERY_STRATEGIES, get_runtime_config


logger = logging.getLogger(__name__)

DISCLAIMER = (
    "本回答用于企业合规辅助和演示，不替代正式法律意见。涉及具体待遇、金额、期限或争议处理时，"
    "请以当地人社、医保、税务等官方经办口径及企业制度最终复核为准。"
)

USER_ROLE_LABELS = {
    "enterprise_hr": "企业HR",
    "administrator_staff": "行政人员",
    "legal_staff": "法务人员",
    "employee": "员工",
    "admin_user": "管理员",
}

DEFAULT_ANSWER_STYLE = "结构清晰、结论先行、引用来源、明确风险等级和待核验项"
QUERY_STRATEGY_ORDER = {
    "langchain_first": ("langchain", "dify"),
    "dify_first": ("dify", "langchain"),
    "langchain_only": ("langchain",),
    "dify_only": ("dify",),
    "vector_only": (),
}
CONTEXT_FIELD_LIMITS = {
    "answer_style": 600,
    "user_goal": 160,
    "urgency_level": 80,
    "output_format": 120,
    "known_facts": 1000,
    "verification_focus": 600,
}
CONTEXT_FIELD_LABELS = {
    "user_goal": "问题目标",
    "urgency_level": "紧急程度",
    "output_format": "输出格式",
    "known_facts": "已知事实",
    "verification_focus": "重点核验",
}


_generation_tasks: dict[str, dict[str, str]] = {}
_generation_tasks_lock = threading.Lock()


@dataclass
class ChatAttachment:
    """待转交给 Dify 的用户附件。

    当前项目的 LangChain 链路只处理文本问答；带文件的问题仍交给 Dify，
    因为 Dify 工作流更适合做文件解析、节点编排和流式返回。
    """

    filename: str
    content_type: str
    file: BinaryIO


class ComplianceAnswerService:
    """按管理员策略编排 LangChain、Dify 与向量知识库边界。

    可以把这个类理解成“问答总调度员”：
    1. 先判断问题是否太简单或不在系统范围内。
    2. 系统内问题必须先从 Milvus 找到知识库证据。
    3. 根据管理员配置选择 LangChain 或 Dify 生成答案。
    4. 生成后补充质量评估，方便前端和运营人员复核。
    """

    def __init__(self, db: Session, tenant: Tenant):
        self.db = db
        self.tenant = tenant
        self.runtime_config = get_runtime_config(db)
        self.last_dify_error: Optional[str] = None
        self.last_langchain_error: Optional[str] = None
        self.trace_metrics: dict[str, Any] = {}
        self._vector_source_cache: dict[str, list[SourceInfo]] = {}

    def _reset_request_trace(self) -> None:
        self.trace_metrics = {}
        self._vector_source_cache = {}

    def _elapsed_trace_ms(self, started_at: float) -> int:
        return max(0, int((time.perf_counter() - started_at) * 1000))

    def _add_trace_ms(self, key: str, started_at: float) -> None:
        elapsed = self._elapsed_trace_ms(started_at)
        current = self.trace_metrics.get(key)
        self.trace_metrics[key] = int(current or 0) + elapsed

    def _set_trace_metric(self, key: str, value: Any) -> None:
        if value is not None:
            self.trace_metrics[key] = value

    def _increment_trace_metric(self, key: str) -> None:
        self.trace_metrics[key] = int(self.trace_metrics.get(key) or 0) + 1

    def _trace_snapshot(self) -> dict[str, Any]:
        return dict(self.trace_metrics)

    def _get_dify_base_url(self) -> str:
        return self.runtime_config.dify_base_url

    def _get_dify_timeout_seconds(self) -> int:
        return self.runtime_config.dify_timeout_seconds

    def answer(
        self,
        question: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        language: str = "zh-CN",
        user_role: str = "employee",
        province: str = "陕西省",
        city: str = "西安市",
        attachment: Optional[ChatAttachment] = None,
        generation_id: Optional[str] = None,
        answer_style: Optional[str] = None,
        user_goal: Optional[str] = None,
        urgency_level: Optional[str] = None,
        output_format: Optional[str] = None,
        known_facts: Optional[str] = None,
        verification_focus: Optional[str] = None,
    ) -> ChatResponse:
        # 业务入口只负责“生成答案 + 生成质量报告”。真正的路由判断在 _answer_core，
        # 这样前端拿到的每个回答都有同一套 evaluation 字段。
        response = self._answer_core(
            question=question,
            user_id=user_id,
            conversation_id=conversation_id,
            language=language,
            user_role=user_role,
            province=province,
            city=city,
            attachment=attachment,
            generation_id=generation_id,
            answer_style=answer_style,
            user_goal=user_goal,
            urgency_level=urgency_level,
            output_format=output_format,
            known_facts=known_facts,
            verification_focus=verification_focus,
        )
        trace_metrics = self._trace_snapshot()
        quality_start = time.perf_counter()
        response.evaluation = build_answer_quality_report(
            question=question,
            answer=response.answer,
            sources=response.sources,
            provider=response.provider,
            risk_level=response.risk_level,
            fallback_reason=response.fallback_reason,
            response_time_ms=response.response_time,
            trace_metrics=trace_metrics,
        ).model_dump()
        self._add_trace_ms("quality_report_ms", quality_start)
        response.trace_metrics = self._trace_snapshot()
        if response.evaluation:
            response.evaluation.setdefault("metrics", {})["trace"] = response.trace_metrics
        return response

    def _answer_core(
        self,
        question: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        language: str = "zh-CN",
        user_role: str = "employee",
        province: str = "陕西省",
        city: str = "西安市",
        attachment: Optional[ChatAttachment] = None,
        generation_id: Optional[str] = None,
        answer_style: Optional[str] = None,
        user_goal: Optional[str] = None,
        urgency_level: Optional[str] = None,
        output_format: Optional[str] = None,
        known_facts: Optional[str] = None,
        verification_focus: Optional[str] = None,
    ) -> ChatResponse:
        self._reset_request_trace()
        question = sanitize_text(question) or ""
        self.last_dify_error = None
        self.last_langchain_error = None
        self._set_trace_metric("question_characters", len(question))
        context = self._normalize_context(
            answer_style=answer_style,
            user_goal=user_goal,
            urgency_level=urgency_level,
            output_format=output_format,
            known_facts=known_facts,
            verification_focus=verification_focus,
        )
        self._set_trace_metric("context_characters", sum(len(value or "") for value in context.values()))
        start_time = int(time.time() * 1000)
        # 第一道门：问候、感谢、能力询问等简单问题直接返回固定话术；
        # 高风险且系统外的问题也在这里挡住，避免模型自由发挥。
        precheck_start = time.perf_counter()
        guard_decision = classify_question(question)
        self._add_trace_ms("precheck_ms", precheck_start)
        if attachment is not None and guard_decision.should_short_circuit and guard_decision.category != "high_risk_out_of_scope":
            guard_decision = QuestionGuardDecision(category="domain", should_short_circuit=False)
        if guard_decision.should_short_circuit:
            return self._guardrail_response(
                guard_decision,
                start_time=start_time,
                user_role=user_role,
                province=province,
                city=city,
                context=context,
            )

        # 知识包相当于“当前租户是否允许使用知识库”的总开关。
        # 停用时不继续调用 Milvus、LangChain 或 Dify，避免误用旧资料。
        package_start = time.perf_counter()
        has_active_package = self._has_active_package()
        self._add_trace_ms("knowledge_package_ms", package_start)
        if not has_active_package:
            response = ChatResponse(
                answer=self._with_context_prefix(
                    self._inactive_package_answer(question),
                    user_role,
                    province,
                    city,
                    context,
                ),
                sources=None,
                related_tasks=[],
                response_time=int(time.time() * 1000) - start_time,
                provider="knowledge_package_disabled",
                risk_level=self._estimate_risk(question),
                suggestions=[],
                disclaimer=DISCLAIMER,
            )
            return response

        # 系统内问题必须有知识库证据。没有命中 Milvus 时直接提示补充资料，
        # 不让模型基于常识猜法规、金额、时限或办理入口。
        if guard_decision.category == "domain" and attachment is None and not self._has_knowledge_evidence(question, language):
            return self._knowledge_base_no_match_response(
                question,
                start_time=start_time,
                user_role=user_role,
                province=province,
                city=city,
                context=context,
            )

        tenant_dify_key_value = getattr(self.tenant, "dify_api_key", None)
        tenant_dify_key = str(tenant_dify_key_value).strip() if tenant_dify_key_value is not None else ""
        dify_key = tenant_dify_key or self.runtime_config.dify_api_key
        langchain_key = self.runtime_config.langchain_api_key
        provider_order = self._query_provider_order(attachment=attachment)
        attempted_langchain = False
        attempted_dify = False
        is_domain_question = guard_decision.category == "domain"
        self._set_trace_metric("query_strategy", self._query_strategy())

        # provider_order 来自后台“查询方案”：LangChain 优先、Dify 优先、
        # 仅 LangChain、仅 Dify，或 vector_only。循环按顺序尝试，可用就返回。
        for provider_name in provider_order:
            if provider_name == "langchain":
                if not langchain_key:
                    continue
                attempted_langchain = True
                langchain_response = self._call_langchain(
                    question,
                    user_id,
                    conversation_id,
                    language,
                    user_role,
                    province,
                    city,
                    context,
                )
                if langchain_response:
                    langchain_response.response_time = int(time.time() * 1000) - start_time
                    return langchain_response
                continue

            if provider_name == "dify":
                if not dify_key:
                    continue
                attempted_dify = True
                dify_response = self._call_dify(
                    question,
                    dify_key,
                    user_id,
                    conversation_id,
                    user_role,
                    province,
                    city,
                    attachment,
                    generation_id,
                    context,
                    require_sources=is_domain_question and attachment is None,
                )
                if dify_response:
                    dify_response.response_time = int(time.time() * 1000) - start_time
                    return dify_response

        # 附件场景只能走 Dify。如果 Dify 被策略禁用或调用失败，就明确告诉用户，
        # 不能悄悄改用本地解析或普通文本问答。
        if attachment:
            strategy = self._query_strategy()
            if "dify" not in provider_order:
                answer = (
                    "已收到附件，但当前管理员配置的查询方案不允许调用 Dify 文件解析链路。"
                    "系统不会绕过该策略处理附件内容，请联系管理员切换为 Dify 相关查询方案后重试。"
                )
                provider = "provider_disabled"
                fallback_reason = f"query_strategy={strategy}"
            else:
                answer = (
                    "已收到附件，但文件内容解析必须由 Dify 完成。当前 Dify 未配置或调用失败，"
                    "系统未对附件内容进行本地解析，请检查 Dify 应用密钥、文件上传能力和工作流配置后重试。"
                )
                provider = "dify_unavailable"
                fallback_reason = self.last_dify_error
            return ChatResponse(
                answer=self._with_context_prefix(
                    answer,
                    user_role,
                    province,
                    city,
                    context,
                ),
                sources=None,
                related_tasks=[],
                response_time=int(time.time() * 1000) - start_time,
                provider=provider,
                fallback_reason=fallback_reason,
                risk_level=self._estimate_risk(question),
                suggestions=[],
                disclaimer=DISCLAIMER,
            )

        # 所有外部生成链路都不可用时，落到知识库边界提示。
        # 对系统内问题，allow_fallback=False，仍然不能编造答案。
        local_response = self._knowledge_boundary_fallback(
            question,
            language,
            allow_fallback=not is_domain_question,
        )
        if attempted_langchain:
            if local_response.provider != "kb_no_match":
                local_response.provider = "langchain_unavailable"
            reasons = [self.last_langchain_error or "LangChain 调用失败"]
            if attempted_dify and self.last_dify_error:
                reasons.append(self.last_dify_error)
            local_response.fallback_reason = "；".join(reasons)
        elif attempted_dify:
            if local_response.provider != "kb_no_match":
                local_response.provider = "dify_unavailable"
            local_response.fallback_reason = self.last_dify_error or "Dify 调用失败"
        local_response.answer = self._with_context_prefix(local_response.answer, user_role, province, city, context)
        local_response.response_time = int(time.time() * 1000) - start_time
        return local_response

    def _query_strategy(self) -> str:
        """读取管理员配置的查询方案，异常值回到默认策略。"""
        strategy = str(getattr(self.runtime_config, "query_strategy", DEFAULT_QUERY_STRATEGY) or DEFAULT_QUERY_STRATEGY)
        return strategy if strategy in QUERY_STRATEGIES else DEFAULT_QUERY_STRATEGY

    def _query_provider_order(self, attachment: Optional[ChatAttachment] = None) -> tuple[str, ...]:
        """把查询方案翻译成实际调用顺序。附件问题只允许 Dify 处理。"""
        order = QUERY_STRATEGY_ORDER[self._query_strategy()]
        if attachment is not None:
            return tuple(provider for provider in order if provider == "dify")
        return order

    def _set_langchain_error(self, message: str) -> None:
        self.last_langchain_error = sanitize_text(message) or message

    def _set_dify_error(self, message: str) -> None:
        self.last_dify_error = sanitize_text(message) or message

    def _invoke_langchain_with_hard_timeout(
        self,
        provider: LangChainComplianceProvider,
        prompt_context: LangChainPromptContext,
    ) -> str:
        timeout_seconds = max(1, min(int(self.runtime_config.langchain_timeout_seconds or 6), 8))
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="langchain-hard-timeout")
        future = executor.submit(provider.answer, prompt_context)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            raise LangChainUnavailable(f"LangChain 调用超过硬超时 {timeout_seconds} 秒") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _call_langchain(
        self,
        question: str,
        user_id: Optional[str],
        conversation_id: Optional[str],
        language: str,
        user_role: str,
        province: str,
        city: str,
        context: Optional[dict[str, str]] = None,
    ) -> Optional[ChatResponse]:
        langchain_start = time.perf_counter()
        try:
            # LangChain 不是自己存知识库，它只负责“把检索到的知识片段放进 Prompt，
            # 再调用 OpenAI-compatible 模型”。知识片段来自 _build_langchain_source_context。
            provider = LangChainComplianceProvider(
                api_key=self.runtime_config.langchain_api_key,
                model=self.runtime_config.langchain_model,
                base_url=self.runtime_config.langchain_base_url,
                temperature=self.runtime_config.langchain_temperature,
                timeout_seconds=self.runtime_config.langchain_timeout_seconds,
                langsmith_tracing_enabled=self.runtime_config.langsmith_tracing_enabled,
                langsmith_endpoint=self.runtime_config.langsmith_endpoint,
                langsmith_api_key=self.runtime_config.langsmith_api_key,
                langsmith_project=self.runtime_config.langsmith_project,
            )
            self._set_trace_metric("langchain_configured", provider.configured)
            if not provider.configured:
                return None
            source_context_start = time.perf_counter()
            source_context, source_infos = self._build_langchain_source_context(question, language)
            self._add_trace_ms("langchain_source_context_ms", source_context_start)
            # PromptContext 是喂给模板的数据包：问题、租户、地区、用户角色、
            # 回答风格和 Milvus 检索片段都在这里统一整理。
            context_notes = self._format_context_notes(context)
            self._set_trace_metric("context_notes_chars", len(context_notes))
            self._set_trace_metric("source_context_chars", len(source_context))
            self._set_trace_metric("source_count", len(source_infos))
            prompt_context = LangChainPromptContext(
                question=question,
                language=language,
                tenant_code=self.tenant.code,
                tenant_name=self.tenant.name,
                region=self._region_label(province, city),
                province=province,
                city=city,
                user_role=USER_ROLE_LABELS.get(user_role, user_role),
                answer_style=(context or {}).get("answer_style") or DEFAULT_ANSWER_STYLE,
                context_notes=context_notes,
                source_context=source_context,
                disclaimer=DISCLAIMER,
            )
            prompt_context_chars = sum(len(str(value or "")) for value in prompt_context.__dict__.values())
            self._set_trace_metric("prompt_context_chars", prompt_context_chars)
            model_start = time.perf_counter()
            try:
                raw_answer = self._invoke_langchain_with_hard_timeout(provider, prompt_context)
            finally:
                self._add_trace_ms("langchain_model_ms", model_start)
            answer = self._normalize_answer(raw_answer)
            return ChatResponse(
                answer=answer,
                sources=source_infos or None,
                related_tasks=self._extract_tasks(question),
                response_time=0,
                conversation_id=conversation_id,
                question_id=None,
                provider="langchain",
                risk_level=self._risk_from_answer(answer) or self._estimate_risk(question),
                suggestions=self._suggestions(question),
                disclaimer=DISCLAIMER,
            )
        except LangChainUnavailable as exc:
            self._set_langchain_error(str(exc))
            logger.warning(
                "LangChain chat request failed; falling back to next provider. user_id=%s model=%s error=%s",
                user_id or "anonymous",
                self.runtime_config.langchain_model,
                exc,
            )
            return None
        finally:
            self._add_trace_ms("langchain_total_ms", langchain_start)

    def _guardrail_response(
        self,
        decision: QuestionGuardDecision,
        *,
        start_time: int,
        user_role: str,
        province: str,
        city: str,
        context: Optional[dict[str, str]] = None,
    ) -> ChatResponse:
        return ChatResponse(
            answer=self._with_context_prefix(decision.answer, user_role, province, city, context),
            sources=None,
            related_tasks=[],
            response_time=int(time.time() * 1000) - start_time,
            provider=decision.provider,
            fallback_reason=decision.fallback_reason,
            risk_level=decision.risk_level,
            suggestions=decision.suggestions,
            disclaimer=DISCLAIMER,
        )

    def _knowledge_base_no_match_response(
        self,
        question: str,
        *,
        start_time: int,
        user_role: str,
        province: str,
        city: str,
        context: Optional[dict[str, str]] = None,
    ) -> ChatResponse:
        answer = (
            "当前知识库未检索到足够明确的依据，系统不会基于外部常识或模型猜测生成合规结论。\n"
            "请补充更具体的地区、员工身份、时间节点或业务事实后重试；也可由管理员先上传并审核相关政策、"
            "企业制度或 FAQ 后再发起问答。\n\n"
            "风险等级：{risk}\n"
            "待核验项：请以已入库的官方政策、当地人社/医保/税务经办口径和企业制度为准。"
        ).format(risk=self._estimate_risk(question))
        return ChatResponse(
            answer=self._with_context_prefix(answer, user_role, province, city, context),
            sources=None,
            related_tasks=[],
            response_time=int(time.time() * 1000) - start_time,
            provider="kb_no_match",
            fallback_reason="knowledge_base_no_match",
            risk_level=self._estimate_risk(question),
            suggestions=self._suggestions(question),
            disclaimer=DISCLAIMER,
        )

    def _dify_error_from_response(self, response: requests.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            data = {}
        message = data.get("message") if isinstance(data, dict) else None
        if message:
            return f"Dify 返回错误 {response.status_code}: {message}"
        body = (response.text or "").strip()
        if body:
            return f"Dify 返回错误 {response.status_code}: {body[:200]}"
        return f"Dify 返回错误 {response.status_code}"

    def _dify_error_from_event(self, event: dict) -> str:
        message = event.get("message") or event.get("error") or event.get("code")
        if message:
            return f"Dify 流式返回错误: {message}"
        return "Dify 流式返回错误"

    def _call_dify(
        self,
        question: str,
        api_key: str,
        user_id: Optional[str],
        conversation_id: Optional[str],
        user_role: str,
        province: str,
        city: str,
        attachment: Optional[ChatAttachment] = None,
        generation_id: Optional[str] = None,
        context: Optional[dict[str, str]] = None,
        require_sources: bool = False,
    ) -> Optional[ChatResponse]:
        dify_start = time.perf_counter()
        try:
            # Dify 仍保留为兼容回退：它接收同样的租户/地区/上下文字段，
            # 但具体检索和生成由 Dify 工作流决定。
            payload = {
                "query": question,
                "user": user_id or "anonymous",
                "response_mode": "streaming",
                "inputs": self._build_dify_inputs(user_role, province, city, context),
            }
            if conversation_id:
                payload["conversation_id"] = conversation_id
            if attachment:
                upload_file_id = self._upload_file_to_dify(api_key, user_id, attachment)
                if not upload_file_id:
                    logger.warning("Dify file upload failed; falling back to knowledge boundary response. filename=%s", attachment.filename)
                    return None
                payload["files"] = [
                    {
                        "type": self._dify_file_type(attachment.filename, attachment.content_type),
                        "transfer_method": "local_file",
                        "upload_file_id": upload_file_id,
                    }
                ]

            response = requests.post(
                f"{self._get_dify_base_url().rstrip('/')}/chat-messages",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                stream=True,
                timeout=self._get_dify_timeout_seconds(),
            )
            if response.status_code != 200:
                self._set_dify_error(self._dify_error_from_response(response))
                logger.warning(
                    "Dify chat request failed; falling back to knowledge boundary response. status=%s body=%s",
                    response.status_code,
                    response.text[:1000],
                )
                return None

            data = self._consume_dify_stream(response, generation_id, api_key, user_id or "anonymous")
            if not data:
                if not self.last_dify_error:
                    self._set_dify_error("Dify 未返回有效回答，已回退到知识库边界响应")
                return None

            metadata = data.get("metadata") or {}
            sources = []
            for resource in metadata.get("retriever_resources", []):
                sources.append(
                    SourceInfo(
                        title=resource.get("document_name") or resource.get("title") or "Dify 知识库来源",
                        url=resource.get("url"),
                        snippet=(resource.get("content") or "")[:220],
                    )
                )
            if require_sources and not sources:
                # 系统内问题必须有检索来源。Dify 若没有返回 retriever_resources，
                # 就认为它没有给出可追溯证据，拒绝使用该回答。
                self._set_dify_error("Dify 未返回知识库来源，已拒绝非知识库回答")
                logger.warning("Dify answer rejected because no retriever resources were returned for a domain question.")
                return None
            answer = self._normalize_answer(data.get("answer") or "")
            return ChatResponse(
                answer=answer,
                sources=sources or None,
                related_tasks=self._extract_tasks(question),
                response_time=0,
                conversation_id=data.get("conversation_id"),
                question_id=None,
                provider="dify",
                risk_level=self._risk_from_answer(answer) or self._estimate_risk(question),
                suggestions=self._suggestions(question),
                disclaimer=DISCLAIMER,
            )
        except requests.Timeout as exc:
            self._set_dify_error(f"Dify 请求超时: {exc}")
            logger.warning(
                "Dify chat request timed out after %ss; falling back to knowledge boundary response. url=%s error=%s",
                self._get_dify_timeout_seconds(),
                f"{self._get_dify_base_url().rstrip('/')}/chat-messages",
                exc,
            )
            return None
        except requests.RequestException as exc:
            self._set_dify_error(f"Dify 请求失败: {exc}")
            logger.warning("Dify chat request failed; falling back to knowledge boundary response. error=%s", exc)
            return None
        finally:
            self._add_trace_ms("dify_total_ms", dify_start)
            if generation_id:
                self._unregister_generation(generation_id)

    def _consume_dify_stream(
        self,
        response: requests.Response,
        generation_id: Optional[str],
        api_key: str,
        user_id: str,
    ) -> Optional[dict]:
        """把 Dify 的 SSE 流式响应拼成一个普通 dict，方便后续统一处理。"""
        answer_parts: list[str] = []
        final_data: dict = {}
        metadata: dict = {}
        task_id = ""

        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            if raw_line.startswith("event:"):
                continue
            if not raw_line.startswith("data:"):
                continue

            try:
                event = json.loads(raw_line[5:].strip())
            except json.JSONDecodeError:
                logger.warning("Failed to decode Dify stream line: %s", raw_line[:300])
                continue

            task_id = task_id or str(event.get("task_id") or "")
            if generation_id and task_id:
                self._register_generation(
                    generation_id,
                    task_id,
                    api_key,
                    user_id,
                    self._get_dify_base_url(),
                    self._get_dify_timeout_seconds(),
                )

            event_type = event.get("event")
            if event_type == "message":
                answer_parts.append(event.get("answer") or "")
                final_data["conversation_id"] = event.get("conversation_id") or final_data.get("conversation_id")
                final_data["message_id"] = event.get("message_id") or final_data.get("message_id")
            elif event_type == "message_end":
                metadata = event.get("metadata") or {}
                final_data["conversation_id"] = event.get("conversation_id") or final_data.get("conversation_id")
                final_data["message_id"] = event.get("message_id") or final_data.get("message_id")
            elif event_type == "workflow_finished":
                data = event.get("data") or {}
                outputs = data.get("outputs") or {}
                if outputs.get("answer"):
                    answer_parts = [outputs["answer"]]
            elif event_type == "error":
                self._set_dify_error(self._dify_error_from_event(event))
                logger.warning("Dify stream returned error: %s", event)
                return None

        final_data["answer"] = "".join(answer_parts)
        final_data["metadata"] = metadata
        return final_data if final_data["answer"] else None

    @classmethod
    def _register_generation(
        cls,
        generation_id: str,
        task_id: str,
        api_key: str,
        user_id: str,
        base_url: str,
        timeout_seconds: int,
    ) -> None:
        with _generation_tasks_lock:
            _generation_tasks[generation_id] = {
                "task_id": task_id,
                "api_key": api_key,
                "user_id": user_id,
                "base_url": base_url,
                "timeout_seconds": str(timeout_seconds),
            }

    @classmethod
    def _unregister_generation(cls, generation_id: str) -> None:
        with _generation_tasks_lock:
            _generation_tasks.pop(generation_id, None)

    @classmethod
    def stop_generation(cls, generation_id: str) -> bool:
        with _generation_tasks_lock:
            task = _generation_tasks.get(generation_id)

        if not task:
            return False

        try:
            base_url = task.get("base_url") or settings.dify_base_url
            timeout_seconds = int(task.get("timeout_seconds") or 10)
            response = requests.post(
                f"{base_url.rstrip('/')}/chat-messages/{task['task_id']}/stop",
                headers={"Authorization": f"Bearer {task['api_key']}", "Content-Type": "application/json"},
                json={"user": task["user_id"]},
                timeout=timeout_seconds,
            )
            if response.status_code >= 400:
                logger.warning("Dify stop request failed. status=%s body=%s", response.status_code, response.text[:500])
                return False
            return True
        except requests.RequestException as exc:
            logger.warning("Dify stop request failed. generation_id=%s error=%s", generation_id, exc)
            return False
        finally:
            cls._unregister_generation(generation_id)

    def _upload_file_to_dify(
        self,
        api_key: str,
        user_id: Optional[str],
        attachment: ChatAttachment,
    ) -> Optional[str]:
        try:
            if hasattr(attachment.file, "seek"):
                attachment.file.seek(0)
            response = requests.post(
                f"{self._get_dify_base_url().rstrip('/')}/files/upload",
                headers={"Authorization": f"Bearer {api_key}"},
                data={"user": user_id or "anonymous"},
                files={
                    "file": (
                        attachment.filename,
                        attachment.file,
                        attachment.content_type or "application/octet-stream",
                    )
                },
                timeout=self._get_dify_timeout_seconds(),
            )
            if response.status_code not in (200, 201):
                logger.warning(
                    "Dify file upload returned non-success status. status=%s body=%s",
                    response.status_code,
                    response.text[:1000],
                )
                return None
            data = response.json()
            return data.get("id")
        except requests.Timeout as exc:
            logger.warning(
                "Dify file upload timed out after %ss. filename=%s error=%s",
                self._get_dify_timeout_seconds(),
                attachment.filename,
                exc,
            )
            return None
        except requests.RequestException as exc:
            logger.warning("Dify file upload failed. filename=%s error=%s", attachment.filename, exc)
            return None

    def _dify_file_type(self, filename: str, content_type: str) -> str:
        content_type = (content_type or "").lower()
        suffix = Path(filename or "").suffix.lower().lstrip(".")
        if content_type.startswith("image/"):
            return "image"
        if content_type.startswith("audio/"):
            return "audio"
        if content_type.startswith("video/"):
            return "video"
        if suffix in {
            "pdf",
            "txt",
            "md",
            "markdown",
            "html",
            "htm",
            "csv",
            "doc",
            "docx",
            "xls",
            "xlsx",
            "ppt",
            "pptx",
            "rtf",
        }:
            return "document"
        return "custom"

    def _knowledge_boundary_fallback(self, question: str, language: str, allow_fallback: bool = True) -> ChatResponse:
        """生成“知识库边界”回复。

        allow_fallback=False 表示这是系统内合规问题，哪怕外部模型不可用，
        也只能返回已检索片段或提示补充资料，不能使用外部常识兜底。
        """
        if not allow_fallback:
            vector_sources = self._vector_source_infos(question)
            if vector_sources:
                answer = self._vector_only_answer(question, vector_sources)
                provider = "vector_only"
                fallback_reason = None
            else:
                answer = (
                    "当前知识库未检索到足够明确的依据，系统不会基于外部常识或模型猜测生成合规结论。\n"
                    "请补充更具体的地区、员工身份、时间节点或业务事实后重试，或由管理员先上传并审核相关资料。\n\n"
                    f"风险等级：{self._estimate_risk(question)}\n"
                    "待核验项：请以已入库知识库和当地官方经办口径为准。"
                )
                provider = "kb_no_match"
                fallback_reason = "knowledge_base_generation_unavailable"
            return ChatResponse(
                answer=answer,
                sources=vector_sources or None,
                related_tasks=[],
                response_time=0,
                provider=provider,
                fallback_reason=fallback_reason,
                risk_level=self._estimate_risk(question),
                suggestions=self._suggestions(question),
                disclaimer=DISCLAIMER,
            )

        return ChatResponse(
            answer=self._fallback_answer(question),
            sources=self._source_infos([]) or None,
            related_tasks=self._extract_tasks(question),
            response_time=0,
            provider="kb_no_match",
            fallback_reason="external_provider_unavailable",
            risk_level=self._estimate_risk(question),
            suggestions=self._suggestions(question),
            disclaimer=DISCLAIMER,
        )

    def _vector_only_answer(self, question: str, sources: list[SourceInfo]) -> str:
        """用命中的知识库片段直接组成低延迟回答，不调用外部模型。"""
        primary = sources[0]
        primary_text = primary.content or primary.snippet or ""
        standard_answer = self._extract_standard_answer(primary_text)
        conclusion = standard_answer or primary.snippet or primary_text[:420] or "已命中知识库片段，请查看来源详情。"
        source_lines = []
        for index, source in enumerate(sources[:3], start=1):
            label = "FAQ" if source.source_type == "faq" or source.title.startswith("[FAQ]") else "文档"
            source_lines.append(f"{index}. {label}：{source.title}")
        return (
            "当前为低延迟知识库回答，未调用外部模型。\n\n"
            f"风险等级：{self._estimate_risk(question)}\n\n"
            f"结论：{conclusion.strip()}\n\n"
            "依据：\n"
            f"{chr(10).join(source_lines)}\n\n"
            "行动建议：请结合员工身份、实际工作地、合同约定和企业制度版本复核；涉及金额、期限或争议处理时，以当地人社、医保、税务等官方经办口径为准。\n\n"
            "待核验项：仅依据已返回的知识库来源片段，不补充外部常识。"
        )

    def _extract_standard_answer(self, text: str) -> str:
        if not text:
            return ""
        match = re.search(r"##\s*标准答案\s*(.+?)(?:\n##\s+|\Z)", text, flags=re.S)
        if not match:
            return ""
        answer = re.sub(r"\n{3,}", "\n\n", match.group(1)).strip()
        return answer[:800]

    def _has_knowledge_evidence(self, question: str, language: str) -> bool:
        """判断系统内问题是否能在 Milvus 找到证据。"""
        return bool(self._vector_source_infos(question))

    def _source_infos(self, source_ids: list[int]) -> list[SourceInfo]:
        if not self._has_active_package():
            return []
        query = self.db.query(Source).filter(Source.tenant_id == self.tenant.id)
        if source_ids:
            query = query.filter(Source.id.in_(source_ids))
        else:
            query = query.order_by(Source.created_at.desc()).limit(3)
        sources = query.all()
        result = []
        for item in sources:
            source = cast(Any, item)
            result.append(
                SourceInfo(
                    title=str(source.title or ""),
                    url=str(source.url) if source.url else None,
                    snippet=str(source.description) if source.description else None,
                )
            )
        return result

    def _extract_tasks(self, question: str) -> list[TaskInfo]:
        if not any(word in question for word in ["仲裁", "办理", "申请", "共济", "医保"]):
            return []
        return [
            TaskInfo(
                title="合规办理建议路径",
                steps=[
                    "确认适用地区、员工身份、时间节点和企业制度版本。",
                    "准备劳动合同、考勤、工资、社保缴费或医保参保等证据材料。",
                    "通过当地人社、医保、税务等官方渠道核验最新办理入口。",
                    "对高风险事项保留书面处理记录，必要时交由 HR/法务复核。",
                ],
                url=self.runtime_config.ragflow_web_url,
            )
        ]

    def _normalize_answer(self, answer: str) -> str:
        answer = sanitize_text(answer) or ""
        if DISCLAIMER not in answer:
            answer = f"{answer.strip()}\n\n风险提示：{DISCLAIMER}"
        return answer

    def _normalize_context(
        self,
        *,
        answer_style: Optional[str] = None,
        user_goal: Optional[str] = None,
        urgency_level: Optional[str] = None,
        output_format: Optional[str] = None,
        known_facts: Optional[str] = None,
        verification_focus: Optional[str] = None,
    ) -> dict[str, str]:
        raw_context = {
            "answer_style": answer_style,
            "user_goal": user_goal,
            "urgency_level": urgency_level,
            "output_format": output_format,
            "known_facts": known_facts,
            "verification_focus": verification_focus,
        }
        context: dict[str, str] = {}
        for key, value in raw_context.items():
            cleaned = sanitize_text(value) if value is not None else ""
            cleaned = (cleaned or "").strip()
            if key == "answer_style" and not cleaned:
                cleaned = DEFAULT_ANSWER_STYLE
            limit = CONTEXT_FIELD_LIMITS[key]
            if cleaned:
                context[key] = cleaned[:limit]
        return context

    def _region_label(self, province: str, city: str) -> str:
        return f"{province}{city}" if province and city else (province or city or self.tenant.region)

    def _format_context_notes(self, context: Optional[dict[str, str]] = None) -> str:
        lines = []
        for key in ("user_goal", "urgency_level", "output_format", "known_facts", "verification_focus"):
            value = (context or {}).get(key)
            if value:
                lines.append(f"{CONTEXT_FIELD_LABELS[key]}：{value}")
        return "\n".join(lines) if lines else "无额外补充信息。"

    def _build_langchain_source_context(self, question: str, language: str) -> tuple[str, list[SourceInfo]]:
        """把 Milvus 检索结果整理成 LLM 能读懂的上下文文本。

        返回两个东西：
        - source_context：放进 Prompt 的文字证据。
        - source_infos：返回给前端展示的来源列表。
        """
        lines = []
        source_infos: list[SourceInfo] = []
        catalog_source_infos: list[SourceInfo] = []
        vector_sources = self._vector_source_infos(question)
        if vector_sources:
            # Milvus 来源是最可信的问答依据，FAQ 与普通文档会在标题里区分。
            lines.append(
                "\n\n".join(
                    [
                        "\n".join(
                            [
                                f"Milvus 检索片段 {index}（{self._source_type_label(source)}）：{source.title}",
                                f"证据摘录：{self._source_evidence_excerpt(source) or '未提供'}",
                            ]
                        )
                        for index, source in enumerate(vector_sources, start=1)
                    ]
                )
            )
            source_infos.extend(vector_sources)

        if not source_infos:
            # 没有向量片段时，只把来源目录作为兜底展示信息。
            # 注意：系统内问题在前面已经要求必须命中 Milvus，所以这里不会用目录编造结论。
            catalog_source_infos = self._source_infos([])
            source_infos = catalog_source_infos

        for index, source in enumerate(catalog_source_infos[:6], start=1):
            lines.append(
                "\n".join(
                    [
                        f"来源 {index}：{source.title}",
                        f"链接：{source.url or '未提供'}",
                        f"摘要：{source.snippet or '未提供'}",
                    ]
                )
            )

        if not lines:
            lines.append("当前租户没有可用于本次问题的已启用向量知识库片段或来源目录。")

        return "\n\n".join(lines), source_infos

    def _source_evidence_excerpt(self, source: SourceInfo) -> str:
        raw_text = source.content or source.snippet or ""
        if not raw_text:
            return ""
        standard_answer = self._extract_standard_answer(raw_text)
        excerpt = standard_answer or raw_text
        excerpt = re.sub(r"\s+", " ", excerpt).strip()
        return excerpt[:520]

    def _source_type_label(self, source: SourceInfo) -> str:
        if source.source_type == "faq" or source.title.startswith("[FAQ]"):
            return "FAQ 标准问答"
        return "知识库文档"

    def _vector_source_infos(self, question: str) -> list[SourceInfo]:
        """调用 Milvus 做相似度检索，失败时返回空列表让上层走边界提示。"""
        cache_key = sanitize_text(question) or ""
        if cache_key in self._vector_source_cache:
            self._increment_trace_metric("vector_search_cache_hits")
            self._set_trace_metric("vector_search_reused", True)
            return self._vector_source_cache[cache_key]

        service = MilvusVectorService(self.runtime_config)
        if not service.configured:
            self._set_trace_metric("vector_store_configured", False)
            self._vector_source_cache[cache_key] = []
            return []
        search_start = time.perf_counter()
        self._increment_trace_metric("vector_search_count")
        sources: list[SourceInfo] = []
        try:
            sources = service.similarity_search(
                question,
                tenant_id=self.tenant.id,
                tenant_code=self.tenant.code,
            )
        except VectorStoreUnavailable as exc:
            logger.warning("Milvus vector search unavailable; continuing without vector context. error=%s", exc)
        except Exception as exc:
            logger.warning("Milvus vector search failed; continuing without vector context. error=%s", exc)
        finally:
            self._add_trace_ms("vector_search_ms", search_start)
        self._set_trace_metric("vector_source_count", len(sources))
        self._vector_source_cache[cache_key] = sources
        return sources

    def _build_dify_inputs(
        self,
        user_role: str,
        province: str,
        city: str,
        context: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        region = f"{province}{city}" if province and city else (province or city or self.tenant.region)
        inputs = {
            "tenant_code": self.tenant.code,
            "tenant_name": self.tenant.name,
            "region": region,
            "province": province,
            "city": city,
            "user_role": USER_ROLE_LABELS.get(user_role, user_role),
            "answer_style": DEFAULT_ANSWER_STYLE,
        }
        inputs.update(context or {})
        return inputs

    def _with_context_prefix(
        self,
        answer: str,
        user_role: str,
        province: str,
        city: str,
        context: Optional[dict[str, str]] = None,
    ) -> str:
        role = USER_ROLE_LABELS.get(user_role, user_role or "员工")
        region = f"{province}{city}" if province and city else (province or city or self.tenant.region)
        lines = [f"适用角色：{role}", f"所在地区：{region}"]
        for key in ("user_goal", "urgency_level", "output_format", "known_facts", "verification_focus"):
            value = (context or {}).get(key)
            if value:
                lines.append(f"{CONTEXT_FIELD_LABELS[key]}：{value}")
        return f"{chr(10).join(lines)}\n\n{answer}"

    def _has_active_package(self) -> bool:
        return (
            self.db.query(KnowledgePackage.id)
            .filter(KnowledgePackage.tenant_id == self.tenant.id, KnowledgePackage.status == "active")
            .first()
            is not None
        )

    def _inactive_package_answer(self, question: str) -> str:
        risk = self._estimate_risk(question)
        return (
            "当前租户的知识包已停用，系统不会调用知识库文件或外部知识包检索。\n"
            "请先在管理后台启用知识包，或由管理员确认当前资料可用后再进行智能问答。\n"
            f"本次问题仅做通用风险识别，初步风险等级为：{risk}。\n\n"
            f"风险提示：{DISCLAIMER}"
        )

    def _fallback_answer(self, question: str) -> str:
        risk = self._estimate_risk(question)
        return (
            "当前问题未命中足够明确的向量知识库依据，系统无法生成可复核的合规结论。\n"
            "1. 先确认适用地区、时间口径、员工身份、合同和企业制度版本。\n"
            "2. 请由管理员先将 FAQ、官方政策或企业制度作为知识库文档解析入 Milvus，并完成复核后再提问。\n"
            "3. 对包含身份证号、手机号、银行卡号等个人信息的材料，应先脱敏再进入知识库或日志。\n"
            f"4. 本问题初步风险等级为：{risk}。系统不会基于 MySQL FAQ 或外部常识补充结论。"
        )

    def _estimate_risk(self, question: str) -> str:
        high_words = ["仲裁", "工伤", "解除", "赔偿", "最低工资", "未签", "违法", "身份证", "手机号"]
        medium_words = ["社保", "医保", "产假", "护理假", "加班", "离职", "补缴"]
        if any(word in question for word in high_words):
            return "high"
        if any(word in question for word in medium_words):
            return "medium"
        return "low"

    def _risk_from_answer(self, answer: str) -> Optional[str]:
        text = sanitize_text(answer) or ""
        patterns = [
            r"风险等级\s*[:：]\s*(?:\*\*)?\s*(高风险|中风险|低风险|高|中|低|high|medium|low)",
            r"初步风险等级\s*为\s*[:：]?\s*(?:\*\*)?\s*(高风险|中风险|低风险|高|中|低|high|medium|low)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return self._normalize_risk_level(match.group(1))
        return None

    def _normalize_risk_level(self, value: str) -> Optional[str]:
        normalized = (sanitize_text(value) or "").strip().lower().strip("*：:，,。.;；")
        mapping = {
            "高": "high",
            "高风险": "high",
            "high": "high",
            "中": "medium",
            "中风险": "medium",
            "中等": "medium",
            "中等风险": "medium",
            "medium": "medium",
            "低": "low",
            "低风险": "low",
            "low": "low",
        }
        return mapping.get(normalized)

    def _suggestions(self, question: str) -> list[str]:
        if "产假" in question or "护理假" in question:
            return ["陕西护理假多少天？", "生育津贴和产假工资如何衔接？", "企业制度低于地方假期规定怎么办？"]
        if "仲裁" in question:
            return ["劳动仲裁时效是多久？", "仲裁申请需要哪些材料？", "员工所在地和公司所在地哪个有管辖权？"]
        if "社保" in question or "医保" in question:
            return ["新员工入职后多久要办理社保？", "居民医保断缴后还能报销吗？", "社保补缴有什么风险？"]
        return ["试用期工资可以低于最低工资吗？", "劳动合同最晚什么时候签？", "周末加班工资怎么算？"]


def check_external_services() -> dict:
    """探测本机 Dify 与 RAGFlow 服务状态。"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        runtime_config = get_runtime_config(db)
    finally:
        db.close()

    services = {
        "langchain": {
            "name": "LangChain",
            "url": runtime_config.langchain_base_url or "OpenAI-compatible default",
            "configured": bool(
                runtime_config.local_embedding_enabled
                or (runtime_config.langchain_api_key and runtime_config.langchain_model)
            ),
            "model": runtime_config.langchain_model,
            "embedding_model": runtime_config.langchain_embedding_model,
            "local_embedding_enabled": runtime_config.local_embedding_enabled,
        },
        "milvus": {
            "name": "Milvus",
            "url": runtime_config.milvus_uri,
            "configured": bool(runtime_config.milvus_uri and runtime_config.milvus_collection),
            "collection": runtime_config.milvus_collection,
        },
        "dify": {
            "name": "Dify",
            "url": runtime_config.dify_base_url,
            "configured": bool(runtime_config.dify_api_key),
        },
        "langsmith": {
            "name": "LangSmith",
            "url": runtime_config.langsmith_endpoint,
            "configured": bool(runtime_config.langsmith_tracing_enabled and runtime_config.langsmith_api_key),
            "project": runtime_config.langsmith_project,
        },
        "ragflow": {
            "name": "RAGFlow",
            "url": runtime_config.ragflow_web_url,
            "configured": bool(runtime_config.ragflow_api_key),
        },
    }
    for key, item in services.items():
        if key == "milvus":
            if not item["configured"]:
                item["online"] = None
                item["status_code"] = None
                continue
            try:
                from pymilvus import MilvusClient

                client_kwargs: dict[str, Any] = {"uri": runtime_config.milvus_uri}
                if runtime_config.milvus_token:
                    client_kwargs["token"] = runtime_config.milvus_token
                client = MilvusClient(**client_kwargs)
                item["online"] = client.has_collection(runtime_config.milvus_collection)
                item["status_code"] = 200 if item["online"] else 404
            except Exception as exc:
                logger.warning("Milvus status probe failed. uri=%s collection=%s error=%s", runtime_config.milvus_uri, runtime_config.milvus_collection, exc)
                item["online"] = False
                item["status_code"] = None
            continue
        if key == "langchain" and (not item["configured"] or not runtime_config.langchain_base_url):
            item["online"] = None
            item["status_code"] = None
            continue
        if key == "langsmith" and not item["configured"]:
            item["online"] = None
            item["status_code"] = None
            continue
        probe_url = item["url"]
        try:
            response = requests.get(probe_url, timeout=3)
            item["online"] = response.status_code < 500
            item["status_code"] = response.status_code
        except requests.RequestException:
            item["online"] = False
            item["status_code"] = None
    services["local_models"] = local_model_status(runtime_config)
    return services


def dify_attachment_capability(db: Session, tenant: Tenant) -> dict:
    """返回用户端是否应显示附件解析入口。

    附件内容只能交给 Dify 处理；因此只有管理员策略允许 Dify、已配置
    Dify Key 且服务地址可连通时，前端才展示上传控件。
    """
    runtime_config = get_runtime_config(db)
    strategy = runtime_config.query_strategy if runtime_config.query_strategy in QUERY_STRATEGIES else DEFAULT_QUERY_STRATEGY
    strategy_allows_dify = "dify" in QUERY_STRATEGY_ORDER[strategy]
    tenant_dify_key_value = getattr(tenant, "dify_api_key", None)
    tenant_dify_key = str(tenant_dify_key_value).strip() if tenant_dify_key_value is not None else ""
    configured = bool(runtime_config.dify_base_url and (tenant_dify_key or runtime_config.dify_api_key))
    result = {
        "available": False,
        "provider": "dify",
        "reason": "unavailable",
    }
    if not strategy_allows_dify:
        result["reason"] = "strategy_disabled"
        return result
    if not configured:
        result["reason"] = "not_configured"
        return result
    try:
        response = requests.get(runtime_config.dify_base_url, timeout=3)
        online = response.status_code < 500
    except requests.RequestException:
        online = False
    result["available"] = online
    result["reason"] = "available" if online else "offline"
    return result
