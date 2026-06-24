from app.schemas.chat import SourceInfo
from app.services.milvus_vector_service import VectorIndexResult
from app.services.milvus_vector_service import MilvusVectorService
from app.services.quality_reports import build_answer_quality_report, build_vector_ingest_quality_report
from scripts.build_milvus_vector_db import BuildItem, BuildSummary, append_quality_report


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


def test_milvus_source_info_uses_parent_document_title_and_chunk_metadata():
    class DocumentStub:
        page_content = "新员工入职后，应依法及时办理参保。"
        metadata = {
            "filename": "FAQ004_新员工入职后多久要办理社保？.md",
            "document_type": "faq",
            "document_id": "FAQ004",
            "local_file": "documents/faqs/FAQ004_新员工入职后多久要办理社保？.md",
            "chunk_index": 3,
            "url": "https://example.com/source",
        }

    service = object.__new__(MilvusVectorService)
    source = service._source_info_from_document(DocumentStub())

    assert source.title == "[FAQ] FAQ004_新员工入职后多久要办理社保？.md"
    assert "#chunk" not in source.title
    assert source.chunk_index == 3
    assert source.document_id == "FAQ004"
    assert source.local_file == "documents/faqs/FAQ004_新员工入职后多久要办理社保？.md"


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


def test_batch_builder_summarizes_vector_ingest_quality_report():
    item = BuildItem(
        document_id="FAQ001",
        title="西安最低工资标准是多少？",
        kb_category="standard_faq",
        doc_type="FAQ标准问答",
        region="陕西西安",
        issuer="system",
        publish_date="",
        effective_date="",
        validity_status="有效",
        review_status="已复核",
        source_ids="SX001",
        url="",
        prepared_file="documents/faqs/FAQ001.md",
        source_relative_path="资料/faqs/FAQ001.md",
        sha256="abc",
        characters=1800,
        vector_priority=70,
        notes="",
    )
    result = VectorIndexResult(
        document_id="FAQ001",
        title=item.title,
        filename="FAQ001.md",
        local_file=item.prepared_file,
        characters=1800,
        chunks=2,
        collection="slc_docs_demo_v1",
    )
    report = build_vector_ingest_quality_report(
        result=result,
        title=item.title,
        source_id=12,
        tenant_code="demo-sx",
    ).model_dump()
    summary = BuildSummary(
        tenant_code="demo-sx",
        manifest="knowledge_base/langchain_vector_import/manifest.csv",
        collection="slc_docs_demo_v1",
        version="v-test",
        dry_run=False,
    )

    append_quality_report(summary, item=item, result=result, source_id=12, report=report)

    assert summary.quality_overview["total_reports"] == 1
    assert summary.quality_overview["pass_count"] == 1
    assert summary.quality_reports[0]["document_id"] == "FAQ001"
    assert summary.quality_reports[0]["kb_category"] == "standard_faq"


def test_vector_ingest_quality_report_allows_single_chunk_faq():
    result = VectorIndexResult(
        document_id="FAQ099",
        title="长 FAQ 示例",
        filename="FAQ099_长 FAQ 示例.md",
        local_file="documents/faqs/FAQ099_长 FAQ 示例.md",
        characters=3600,
        chunks=1,
        collection="slc_docs_demo_v1",
    )

    report = build_vector_ingest_quality_report(
        result=result,
        title=result.title,
        source_id=12,
        tenant_code="demo-sx",
    ).model_dump()

    assert report["metrics"]["chunks"] == 1
    assert not any("vector_chunk_size" in item for item in report["recommendations"])


def test_answer_quality_report_handles_precheck_provider_as_safe_routing():
    report = build_answer_quality_report(
        question="你好",
        answer="您好，我可以帮助查询企业用工、社保、医保等合规问题。",
        sources=None,
        provider="precheck",
        risk_level="low",
        fallback_reason="simple_small_talk",
        response_time_ms=120,
    ).model_dump()

    assert report["status"] == "pass"
    assert report["metrics"]["provider"] == "precheck"
    assert report["metrics"]["response_time_ms"] == 120
    assert any(item["key"] == "intent_routing" for item in report["dimensions"])
    assert any(item["key"] == "latency" and item["passed"] for item in report["dimensions"])


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


def test_answer_quality_report_adds_latency_dimension_and_langchain_recommendation():
    report = build_answer_quality_report(
        question="员工离职后社保什么时候停缴？",
        answer="风险等级：中\n\n结论：应结合离职时间、工资结算和当地社保经办口径处理。\n\n依据：参考官方来源。\n\n行动建议：HR 复核离职日期、申报周期和缴费状态。\n\n待核验项：以当地经办机构最终口径为准。",
        sources=[SourceInfo(title="[文档] 西安社保办事规则 #chunk-1", snippet="离职停缴情形摘要", source_type="document")],
        provider="langchain",
        risk_level="medium",
        response_time_ms=12000,
    ).model_dump()

    latency = next(item for item in report["dimensions"] if item["key"] == "latency")
    assert report["metrics"]["response_time_ms"] == 12000
    assert latency["score"] == 65
    assert latency["passed"] is False
    assert any("LangChain" in item for item in report["recommendations"])


def test_answer_quality_report_uses_trace_metrics_for_targeted_latency_advice():
    report = build_answer_quality_report(
        question="员工离职后社保什么时候停缴？",
        answer="风险等级：中\n\n结论：应结合离职时间、工资结算和当地社保经办口径处理。\n\n依据：参考官方来源。\n\n行动建议：HR 复核离职日期、申报周期和缴费状态。\n\n待核验项：以当地经办机构最终口径为准。",
        sources=[SourceInfo(title="[文档] 西安社保办事规则 #chunk-1", snippet="离职停缴情形摘要", source_type="document")],
        provider="langchain",
        risk_level="medium",
        response_time_ms=12000,
        trace_metrics={
            "vector_search_ms": 3400,
            "langchain_model_ms": 8100,
            "source_context_chars": 2100,
        },
    ).model_dump()

    assert "trace" in report["metrics"]
    trace = report["metrics"]["trace"]
    assert trace["vector_search_ms"] == 3400
    assert trace["langchain_model_ms"] == 8100
    assert any("Milvus" in item for item in report["recommendations"])
    assert any("模型生成" in item or "模型服务" in item for item in report["recommendations"])
