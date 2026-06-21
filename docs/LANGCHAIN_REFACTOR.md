# LangChain 重构说明

本项目的智能问答链路已调整为：

1. `precheck`：在模型和检索前识别问候、帮助类简单问题，以及高风险非系统问题，直接给出范围说明或防范性回复。
2. `Milvus`：保存管理端上传文档和 `standard_faq` 向量片段，问答时按租户检索相关片段注入 Prompt。
3. `LangChain`：在存在 Milvus 文档片段或 FAQ 类型片段命中时，使用后端内置 `ChatPromptTemplate + ChatOpenAI + StrOutputParser` 链路调用 OpenAI-compatible 模型。
4. `quality_reports`：对输出答案和文档入库结果生成规则化质量报告，用于人工复核和运营调优。
5. `Dify`：在 LangChain 未配置、调用失败或附件问答场景中继续作为兼容回退；系统内问题要求 Dify 返回知识库来源，否则拒绝使用该回答。
6. `kb_no_match`：系统内问题没有 Milvus 片段命中，或外部生成链路不可用时，直接返回知识库边界提示，不基于 MySQL FAQ、外部常识或模型猜测生成答案。

## 配置项

后台「系统配置」可维护以下 LangChain 参数，也可通过 `backend/.env` 注入：

```env
LANGCHAIN_API_KEY=
LANGCHAIN_MODEL=gpt-4o-mini
LANGCHAIN_EMBEDDING_MODEL=bge-m3
LANGCHAIN_BASE_URL=
LANGCHAIN_TEMPERATURE=0.2
LANGCHAIN_TIMEOUT_SECONDS=45
MILVUS_URI=http://127.0.0.1:19530
MILVUS_TOKEN=
MILVUS_COLLECTION=slc_compliance_docs
VECTOR_TOP_K=4
VECTOR_CHUNK_SIZE=500
VECTOR_CHUNK_OVERLAP=50
LOCAL_EMBEDDING_ENABLED=true
LOCAL_EMBEDDING_MODEL_PATH=models/bge-m3
LOCAL_RERANKER_ENABLED=true
LOCAL_RERANKER_MODEL_PATH=models/bge-reranker-large
LOCAL_FALLBACK_BERT_MODEL_PATH=models/bert-base-chinese
```

`LANGCHAIN_BASE_URL` 可留空；当接入私有模型网关、OpenAI-compatible 代理或国内模型服务时，填写完整的 `http(s)` 地址。

本地开发会优先使用 `backend/models/bge-m3` 进行 Embedding；如果本地模型依赖未安装或加载失败，再回退到 `LANGCHAIN_API_KEY` 对应的 OpenAI-compatible Embedding。

## 代码入口

- `backend/app/services/langchain_provider.py`：LangChain LCEL 链路和 Prompt 模板。
- `backend/app/services/milvus_vector_service.py`：文档与 FAQ 的解析、切分、Embedding、Milvus 入库与检索。
- `backend/app/services/local_model_service.py`：`backend/models` 离线模型的懒加载、Embedding、重排和状态检查；问题分类仍由规则判断完成。
- `backend/app/services/question_guard.py`：问候、非系统问题、高风险非系统问题的前置规则判断。
- `backend/app/services/quality_reports.py`：答案质量评估和知识库文档入库质量报告。
- `backend/app/services/dify_service.py`：保留原服务入口，负责 provider 编排、Dify 兼容、知识库边界控制和响应格式统一。
- `backend/app/services/runtime_config.py`：运行时配置读取、校验与数据库覆盖。

## 问题预判与知识库边界

`ComplianceAnswerService` 会在调用 LangChain 或 Dify 前执行 `classify_question()`：

- 问候、感谢、能力询问等简单问题返回 `provider=precheck`，不触发 Milvus、Dify 或 LLM。
- 医疗处方、黑客攻击、投资建议、违法规避等高风险非系统问题返回防范性回复，提示转向官方或专业渠道。
- 天气、新闻、写作、编程等普通非系统问题返回范围说明，引导用户改写为劳动用工与社保合规问题。
- 劳动合同、工资、社保、医保、假期、工伤、入离职、劳动争议和知识库数据安全等系统内问题，必须先命中 Milvus 检索片段；FAQ 仅作为 Milvus 中的 `document_type=faq` 片段参与召回。未命中时返回 `provider=kb_no_match`。

系统内问题的答案必须来自知识库证据。`LangChain` Prompt 也要求只能依据可用知识上下文回答；如果上下文不足，必须说明知识库未命中，不能补充外部常识。

## 答案质量评估

`/api/chat` 和 `/api/chat-with-file` 的响应会附带 `evaluation` 字段，并同步写入 `slc_chat_logs.evaluation`，便于后续从历史记录中复盘。

报告结构：

```json
{
  "report_type": "answer",
  "score": 86,
  "grade": "B",
  "status": "pass",
  "dimensions": [
    {"key": "source_coverage", "label": "来源覆盖", "score": 86, "passed": true}
  ],
  "findings": ["回答质量规则检查未发现明显问题。"],
  "recommendations": ["当前回答可进入人工复核或直接用于一般咨询场景。"],
  "metrics": {"source_count": 2, "provider": "langchain", "risk_level": "medium"}
}
```

当前评估是可解释的规则评分，不额外调用模型。主要维度包括：

- 来源覆盖：是否返回 Milvus/FAQ/来源目录依据。
- 结构完整：是否包含结论、依据、建议、待核验项和风险提示。
- 风险标注：是否明确风险等级。
- 可执行性：是否给出处理动作与复核口径。
- 隐私安全：是否存在未脱敏敏感信息。
- 链路状态：是否发生 LangChain/Dify 回退。

## 文档入库

管理端「来源管理」顶部提供「文档解析入库」入口。后端接口为：

```http
POST /api/admin/vector-documents/upload
Content-Type: multipart/form-data
```

表单字段：

- `file`：必填，支持 `TXT`、`Markdown`、`CSV`、`HTML`、`PDF`、`DOCX`、`XLSX`
- `title`：可选，不填时使用文件名
- `source_id`：可选，用于关联已有来源目录

入库成功响应会附带 `quality_report`：

```json
{
  "chunks": 8,
  "characters": 6400,
  "collection": "slc_compliance_docs_demo_sx_v20260620",
  "quality_report": {
    "report_type": "vector_ingest",
    "score": 88,
    "status": "pass",
    "metrics": {"average_chunk_characters": 800}
  }
}
```

入库质量报告重点检查：

- 文本规模：判断文档是否过短、过长或疑似解析不完整。
- 切分结果：判断是否成功生成 chunk。
- 元数据完整：标题、租户、来源关联是否完整。
- 切分密度：平均 chunk 字符数是否适合召回。
- 隐私安全：标题等关键字段是否出现敏感信息。

## FAQ 向量管理

FAQ 已纳入 Milvus 向量知识库管理，但会与普通资料做显式区分：

- 普通文档 metadata 写入 `document_type=document`。
- FAQ metadata 写入 `document_type=faq`、`document_id`、`category`、`risk_level` 等 manifest 信息。
- 检索返回的 `SourceInfo` 会带 `source_type`，FAQ 来源标题以 `[FAQ]` 开头，普通资料以 `[文档]` 开头。
- LangChain Prompt 中会把 Milvus 片段标注为 `FAQ 标准问答` 或 `知识库文档`，便于模型区分“标准问答”和“政策/制度资料”。

FAQ 不再通过 MySQL 后台 CRUD 管理。请把 FAQ 整理为 `manifest.csv` 中的 `standard_faq` Markdown 文档，再通过版本化构建写入 Milvus；更新 FAQ 时重建并激活新的向量版本。

版本化构建脚本 `backend/scripts/build_milvus_vector_db.py` 默认索引 `manifest.csv` 中的 `standard_faq` 文件：

```bash
python scripts/build_milvus_vector_db.py
```

## 附件问答

当前附件解析仍交给 Dify 工作流处理。LangChain 链路只处理文本问答，不在后端本地解析上传文件内容。
