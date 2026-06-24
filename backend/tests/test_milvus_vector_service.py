from types import SimpleNamespace

from app.services.milvus_vector_service import MilvusVectorService, faq_document_id, faq_to_vector_text


def test_index_file_marks_manifest_faq_as_distinct_source_type(tmp_path):
    faq_file = tmp_path / "FAQ001.md"
    faq_file.write_text(
        '\n'.join(
            [
                "---",
                'document_id: "FAQ001"',
                'kb_category: "standard_faq"',
                'doc_type: "FAQ标准问答"',
                'title: "西安最低工资标准是多少？"',
                'category: "最低工资"',
                'risk_level: "中"',
                "---",
                "# FAQ001 西安最低工资标准是多少？",
                "## 标准答案",
                "西安最低工资标准以入库政策来源为准。",
                "这段补充说明用于模拟较长 FAQ 内容。" * 80,
            ]
        ),
        encoding="utf-8",
    )
    service = MilvusVectorService(
        SimpleNamespace(
            langchain_api_key="key",
            langchain_embedding_model="embedding",
            milvus_uri="http://127.0.0.1:19530",
            milvus_collection="collection",
            vector_chunk_size=1000,
            vector_chunk_overlap=150,
        )
    )
    captured = {}

    class Store:
        def add_documents(self, documents):
            captured["documents"] = documents

    def single_chunk(text, metadata):
        captured["text"] = text
        return [SimpleNamespace(page_content=text, metadata={**metadata, "chunk_index": 0})]

    def split_text(_text, _metadata):
        raise AssertionError("FAQ 文件入库不应按普通文档切成多个 chunk")

    service._single_chunk_documents = single_chunk
    service._split_text = split_text
    service._vector_store = lambda: Store()

    result = service.index_file(
        path=faq_file,
        filename=faq_file.name,
        local_file="documents/faqs/FAQ001.md",
        tenant_id=3,
        tenant_code="demo-sx",
        tenant_name="演示租户",
        extra_metadata={"kb_category": "standard_faq", "source_ids": "SX001"},
    )

    metadata = captured["documents"][0].metadata
    assert len(captured["documents"]) == 1
    assert result.chunks == 1
    assert result.document_id == "FAQ001"
    assert result.title == "西安最低工资标准是多少？"
    assert metadata["document_type"] == "faq"
    assert metadata["faq_code"] == "FAQ001"
    assert metadata["category"] == "最低工资"
    assert metadata["risk_level"] == "中"
    assert captured["documents"][0].page_content == captured["text"]


def test_index_file_strips_frontmatter_and_generated_sections_from_vector_body(tmp_path):
    document_file = tmp_path / "policy.md"
    document_file.write_text(
        "\n".join(
            [
                "---",
                'document_id: "SX001"',
                'title: "陕西最低工资标准"',
                'url: "https://example.com/policy"',
                'category: "最低工资"',
                "---",
                "# 陕西最低工资标准",
                "## 来源元数据",
                "| 字段 | 内容 |",
                "| --- | --- |",
                "| 来源编号 | SX001 |",
                "## 知识摘要",
                "#### 入库建议",
                "- 这是一段摘要入库建议，不应进入向量正文。",
                "#### 官方来源",
                "- https://example.com/policy",
                "## 正文",
                "来源URL：https://example.com/policy",
                "抓取日期：2026-04-29",
                "陕西最低工资标准正文有效内容。",
                "## 文档元数据",
                "| 字段 | 内容 |",
                "| 企业名称 | 测试公司 |",
                "## 外部来源链接",
                "- SX001：陕西最低工资标准（官方来源）https://example.com/policy",
                "## 入库提示",
                "- 这是一段入库提示，不应进入向量正文。",
            ]
        ),
        encoding="utf-8",
    )
    service = MilvusVectorService(
        SimpleNamespace(
            langchain_api_key="key",
            langchain_embedding_model="embedding",
            milvus_uri="http://127.0.0.1:19530",
            milvus_collection="collection",
            vector_chunk_size=1000,
            vector_chunk_overlap=150,
        )
    )
    captured = {}

    class Store:
        def add_documents(self, documents):
            captured["documents"] = documents

    def split_text(text, metadata):
        captured["text"] = text
        captured["metadata"] = metadata
        return [SimpleNamespace(page_content=text, metadata={**metadata, "chunk_index": 0})]

    service._split_text = split_text
    service._vector_store = lambda: Store()

    result = service.index_file(
        path=document_file,
        filename=document_file.name,
        local_file="documents/official_sources/SX001.md",
        tenant_id=3,
        tenant_code="demo-sx",
        tenant_name="演示租户",
    )

    assert result.document_id == "SX001"
    assert result.title == "陕西最低工资标准"
    assert result.characters == len(captured["text"])
    assert captured["metadata"]["url"] == "https://example.com/policy"
    assert captured["metadata"]["category"] == "最低工资"
    assert "document_id:" not in captured["text"]
    assert "## 来源元数据" not in captured["text"]
    assert "## 入库提示" not in captured["text"]
    assert "## 文档元数据" not in captured["text"]
    assert "入库提示" not in captured["text"]
    assert "入库建议" not in captured["text"]
    assert "来源URL" not in captured["text"]
    assert "抓取日期" not in captured["text"]
    assert "陕西最低工资标准正文有效内容" in captured["text"]
    assert "#### 官方来源" in captured["text"]
    assert "## 外部来源链接" in captured["text"]

    source = service._source_info_from_document(captured["documents"][0])
    assert source.snippet
    assert source.content
    assert "document_id:" not in source.snippet
    assert "document_id:" not in source.content
    assert "来源元数据" not in source.snippet
    assert "来源元数据" not in source.content
    assert "入库提示" not in source.snippet
    assert "入库提示" not in source.content
    assert "陕西最低工资标准正文有效内容" in source.content


def test_faq_vector_text_marks_document_type_and_metadata():
    faq = SimpleNamespace(
        id=12,
        faq_code="FAQ012",
        question="劳动合同一定要签书面的吗？",
        answer="建立劳动关系应当订立书面劳动合同。",
        category="劳动合同",
        region="全国",
        risk_level="high",
        language="zh-CN",
        keywords=["劳动合同"],
        aliases=["书面合同"],
        source_ids=["LAW002"],
    )

    assert faq_document_id(faq) == "FAQ012"
    text = faq_to_vector_text(faq)

    assert 'document_type: "faq"' in text
    assert 'faq_code: "FAQ012"' in text
    assert "## 标准答案" in text
    assert "建立劳动关系应当订立书面劳动合同" in text


def test_index_faq_uses_single_chunk_instead_of_text_splitter():
    service = MilvusVectorService(
        SimpleNamespace(
            langchain_api_key="key",
            langchain_embedding_model="embedding",
            milvus_uri="http://127.0.0.1:19530",
            milvus_collection="collection",
            vector_chunk_size=300,
            vector_chunk_overlap=50,
        )
    )
    faq = SimpleNamespace(
        id=12,
        faq_code="FAQ012",
        question="劳动合同一定要签书面的吗？",
        answer="建立劳动关系应当订立书面劳动合同。" * 80,
        category="劳动合同",
        region="全国",
        risk_level="high",
        language="zh-CN",
        keywords=["劳动合同"],
        aliases=["书面合同"],
        source_ids=["LAW002"],
    )
    captured = {}

    class Store:
        def add_documents(self, documents):
            captured["documents"] = documents

        def delete(self, expr=None):
            captured["delete_expr"] = expr
            return True

    def single_chunk(text, metadata):
        captured["text"] = text
        return [SimpleNamespace(page_content=text, metadata={**metadata, "chunk_index": 0})]

    def split_text(_text, _metadata):
        raise AssertionError("FAQ 对象入库不应按普通文档切成多个 chunk")

    service._single_chunk_documents = single_chunk
    service._split_text = split_text
    service._vector_store = lambda: Store()

    result = service.index_faq(
        faq=faq,
        tenant_id=3,
        tenant_code="demo-sx",
        tenant_name="演示租户",
    )

    assert result.document_id == "FAQ012"
    assert result.chunks == 1
    assert len(captured["documents"]) == 1
    assert captured["documents"][0].page_content == captured["text"]
    assert captured["documents"][0].metadata["chunk_index"] == 0
    assert captured["documents"][0].metadata["document_type"] == "faq"
    assert "metadata[\"document_type\"] == \"faq\"" in captured["delete_expr"]


def test_search_k_caps_rerank_candidates():
    service = MilvusVectorService(
        SimpleNamespace(
            local_reranker_enabled=True,
        )
    )

    assert service._search_k(1) == 3
    assert service._search_k(4) == 12
    assert service._search_k(8) == 16
    assert service._search_k(12) == 16


def test_similarity_search_prefers_sparse_before_dense():
    service = MilvusVectorService(
        SimpleNamespace(
            langchain_api_key="key",
            langchain_embedding_model="embedding",
            milvus_uri="http://127.0.0.1:19530",
            milvus_collection="collection",
            milvus_token="",
            vector_search_mode="dense",
            vector_top_k=3,
            langchain_timeout_seconds=6,
            local_embedding_enabled=False,
            local_reranker_enabled=False,
        )
    )
    calls = []
    sparse_doc = SimpleNamespace(
        page_content="## 标准答案\n试用期工资不得低于最低工资标准。",
        metadata={"tenant_id": 3, "tenant_code": "demo-sx", "document_type": "faq", "filename": "FAQ002.md"},
    )

    def sparse_search(query, *, top_k, expr, tenant_id, tenant_code):
        calls.append(("sparse", query, top_k, expr, tenant_id, tenant_code))
        return [sparse_doc]

    service._sparse_search = sparse_search
    service._dense_search = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("命中 sparse 时不应继续触发 dense embedding 检索")
    )

    sources = service.similarity_search("试用期工资可以低于最低工资吗？", tenant_id=3, tenant_code="demo-sx")

    assert calls and calls[0][0] == "sparse"
    assert 'metadata["tenant_id"] == 3' in calls[0][3]
    assert len(sources) == 1
    assert sources[0].source_type == "faq"
    assert "试用期工资不得低于最低工资标准" in (sources[0].content or "")


def test_similarity_search_falls_back_to_dense_when_sparse_misses():
    service = MilvusVectorService(
        SimpleNamespace(
            langchain_api_key="key",
            langchain_embedding_model="embedding",
            milvus_uri="http://127.0.0.1:19530",
            milvus_collection="collection",
            milvus_token="",
            vector_search_mode="dense",
            vector_top_k=3,
            langchain_timeout_seconds=6,
            local_embedding_enabled=False,
            local_reranker_enabled=False,
        )
    )
    calls = []
    dense_doc = SimpleNamespace(
        page_content="劳动合同应当在用工之日起一个月内订立书面劳动合同。",
        metadata={"tenant_id": "3", "tenant_code": "demo-sx", "document_type": "document", "filename": "LAW002.md"},
    )

    service._sparse_search = lambda *args, **kwargs: calls.append("sparse") or []
    service._dense_search = lambda *args, **kwargs: calls.append("dense") or [dense_doc]

    sources = service.similarity_search("劳动合同最晚什么时候签？", tenant_id=3, tenant_code="demo-sx")

    assert calls == ["sparse", "dense"]
    assert len(sources) == 1
    assert sources[0].source_type == "document"
    assert "一个月内" in (sources[0].snippet or "")


def test_similarity_search_expands_dismissal_query_and_filters_unrelated_how_to():
    service = MilvusVectorService(
        SimpleNamespace(
            langchain_api_key="key",
            langchain_embedding_model="embedding",
            milvus_uri="http://127.0.0.1:19530",
            milvus_collection="collection",
            milvus_token="",
            vector_search_mode="dense",
            vector_top_k=3,
            langchain_timeout_seconds=6,
            local_embedding_enabled=False,
            local_reranker_enabled=False,
        )
    )
    captured = {}
    unrelated_doc = SimpleNamespace(
        page_content="工伤职工转诊转院怎么办？由工伤医疗协议机构提出意见。",
        metadata={"tenant_id": 3, "tenant_code": "demo-sx", "document_type": "faq", "filename": "FAQ025.md"},
    )
    dismissal_doc = SimpleNamespace(
        page_content="违法解除劳动合同的，应结合经济补偿、赔偿金和劳动争议仲裁路径处理。",
        metadata={"tenant_id": 3, "tenant_code": "demo-sx", "document_type": "document", "filename": "LAW002.md"},
    )

    def sparse_search(query, *, top_k, expr, tenant_id, tenant_code):
        captured["query"] = query
        return [unrelated_doc, dismissal_doc]

    service._sparse_search = sparse_search
    service._dense_search = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("扩展检索命中解除劳动合同来源后不应继续触发 dense 检索")
    )

    sources = service.similarity_search("违规辞退怎么办", tenant_id=3, tenant_code="demo-sx")

    assert "违法解除劳动合同" in captured["query"]
    assert len(sources) == 1
    assert sources[0].title.startswith("[文档] LAW002")
    assert "违法解除劳动合同" in (sources[0].content or "")


def test_source_info_from_vector_document_distinguishes_faq_and_document():
    service = MilvusVectorService(SimpleNamespace())

    faq_doc = SimpleNamespace(
        page_content="问题：劳动仲裁收费吗？\n答案：劳动争议仲裁一般不收费。",
        metadata={"document_type": "faq", "filename": "FAQ019.faq.md", "chunk_index": 0},
    )
    source_doc = SimpleNamespace(
        page_content="陕西省最低工资标准摘要",
        metadata={"document_type": "document", "filename": "SX001.md", "chunk_index": 1},
    )

    faq_source = service._source_info_from_document(faq_doc)
    document_source = service._source_info_from_document(source_doc)

    assert faq_source.source_type == "faq"
    assert faq_source.title.startswith("[FAQ]")
    assert document_source.source_type == "document"
    assert document_source.title.startswith("[文档]")
    assert document_source.content == "陕西省最低工资标准摘要"


def test_delete_faq_vectors_uses_tenant_and_faq_metadata_expression():
    service = MilvusVectorService(
        SimpleNamespace(
            langchain_api_key="key",
            langchain_embedding_model="embedding",
            milvus_uri="http://127.0.0.1:19530",
            milvus_collection="collection",
        )
    )
    faq = SimpleNamespace(id=9)

    class Store:
        expr = None

        def delete(self, expr=None):
            self.expr = expr
            return True

    store = Store()

    assert service.delete_faq_vectors(faq=faq, tenant_id=3, store=store) is True
    assert 'metadata["tenant_id"] == 3' in store.expr
    assert 'metadata["document_type"] == "faq"' in store.expr
    assert 'metadata["faq_id"] == 9' in store.expr
