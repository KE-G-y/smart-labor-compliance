# LangChain/Milvus 知识库转换资料

本目录由 `scripts/prepare_langchain_knowledge_base.py` 生成，用于将原始政策法规、陕西区域资料、西安办事规则、企业内部制度和 FAQ 整理成可入 Milvus 的标准 Markdown 文档。

## 内容统计

- `company_policy`：6 份
- `national_law`：10 份
- `shaanxi_policy`：8 份
- `standard_faq`：30 份
- `xian_service_rule`：3 份

## 目录结构

- `documents/official_sources/`：去重后的官方政策、法规和办事规则全文，已合并知识卡或办事指南摘要
- `documents/company_policies/`：企业内部制度脱敏入库版
- `documents/faqs/`：标准问答，主要用于提升常见问法召回率
- `manifest.csv` / `manifest.json`：入库清单和元数据
- `upload_plan.csv`：建议上传顺序
- `excluded_files.md`：未纳入向量库的资料类型说明

## 推荐入库方式

1. 启动项目并配置 `MILVUS_URI`、`MILVUS_COLLECTION` 和 Embedding 能力。默认优先使用 `backend/models/bge-m3` 本地模型；如果本地模型依赖不可用，则需要配置 `LANGCHAIN_API_KEY` 和 `LANGCHAIN_EMBEDDING_MODEL`。
2. 登录管理端，进入「来源管理」的「文档解析入库」。
3. 按 `upload_plan.csv` 上传 `prepared_file` 对应的 Markdown 文件，或使用 `backend/scripts/build_milvus_vector_db.py` 按 `manifest.csv` 批量构建版本化 collection。
4. 官方来源资料优先入库；企业制度和 FAQ 可按业务需要补充入库。FAQ 写入时使用 `document_type=faq`，普通资料使用 `document_type=document`。

## 推荐切分参数

- `VECTOR_CHUNK_SIZE=1000`
- `VECTOR_CHUNK_OVERLAP=150`
- 分隔符沿用项目后端 `RecursiveCharacterTextSplitter`：段落、换行、中文句号、分号、英文标点、空格。

## 注意事项

- 产物只保留相对来源路径，不写入本机绝对路径。
- `review_status=待人工复核` 的资料在正式上线前应由 HR/法务或政策负责人复核。
- FAQ 与官方来源冲突时，以最新官方来源和人工复核结果为准。
