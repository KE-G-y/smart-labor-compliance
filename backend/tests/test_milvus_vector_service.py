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

    service._split_text = lambda text, metadata: [SimpleNamespace(page_content=text, metadata={**metadata, "chunk_index": 0})]
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
    assert result.document_id == "FAQ001"
    assert result.title == "西安最低工资标准是多少？"
    assert metadata["document_type"] == "faq"
    assert metadata["faq_code"] == "FAQ001"
    assert metadata["category"] == "最低工资"
    assert metadata["risk_level"] == "中"


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
