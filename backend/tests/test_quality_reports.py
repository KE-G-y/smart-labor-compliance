from app.schemas.chat import SourceInfo
from app.services.milvus_vector_service import VectorIndexResult
from app.services.quality_reports import build_answer_quality_report, build_vector_ingest_quality_report


def test_answer_quality_report_scores_traceable_structured_answer():
    report = build_answer_quality_report(
        question="陕西产假多少天？",
        answer="风险等级：中\n\n结论：应按陕西省现行人口与计划生育条例复核。\n\n依据：参考官方来源。\n\n行动建议：HR 复核员工情形并留存材料。\n\n待核验项：以当地经办口径为准。",
        sources=[SourceInfo(title="[FAQ] FAQ009.faq.md #chunk-0", snippet="产假规定摘要", source_type="faq")],
        provider="langchain",
        risk_level="medium",
    )

    data = report.model_dump()
    assert data["report_type"] == "answer"
    assert data["score"] >= 80
    assert data["status"] == "pass"
    assert data["metrics"]["source_count"] == 1
    assert data["metrics"]["faq_source_count"] == 1


def test_vector_ingest_quality_report_warns_missing_source_link():
    result = VectorIndexResult(
        document_id="doc-1",
        title="测试政策",
        filename="policy.md",
        local_file="tenant_1/vector-documents/policy.md",
        characters=1200,
        chunks=3,
        collection="slc_docs_demo_v1",
    )
    report = build_vector_ingest_quality_report(
        result=result,
        title="测试政策",
        source_id=None,
        tenant_code="demo-sx",
    ).model_dump()

    assert report["report_type"] == "vector_ingest"
    assert report["metrics"]["chunks"] == 3
    assert any("source_id" in item for item in report["recommendations"])


def test_answer_quality_report_handles_precheck_provider_as_safe_routing():
    report = build_answer_quality_report(
        question="你好",
        answer="您好，我可以帮助查询企业用工、社保、医保等合规问题。",
        sources=None,
        provider="precheck",
        risk_level="low",
        fallback_reason="simple_small_talk",
    ).model_dump()

    assert report["status"] == "pass"
    assert report["metrics"]["provider"] == "precheck"
    assert any(item["key"] == "intent_routing" for item in report["dimensions"])


def test_answer_quality_report_handles_knowledge_base_no_match_boundary():
    report = build_answer_quality_report(
        question="公司能否要求员工承担未知费用？",
        answer="当前知识库未检索到足够明确的依据，系统不会基于外部常识或模型猜测生成合规结论。",
        sources=None,
        provider="kb_no_match",
        risk_level="medium",
        fallback_reason="knowledge_base_no_match",
    ).model_dump()

    assert report["status"] == "warning"
    assert report["metrics"]["provider"] == "kb_no_match"
    assert any(item["key"] == "knowledge_boundary" for item in report["dimensions"])
