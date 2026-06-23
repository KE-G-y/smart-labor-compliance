# LangChain 知识库向量化整理说明

本文说明如何将资料包中的文件转化为当前项目可用的 `LangChain + Milvus` 知识库资料。

## 转化原则

同一政策来源通常同时存在 `DOCX`、`PDF`、`HTML`、`TXT`、`JSON` 和知识卡。向量库不应把这些重复格式全部入库，否则检索时会反复命中同一份资料。

推荐规则：

- 官方政策法规：以 `sources.csv` 为索引，每个 `source_id` 只生成一份标准 Markdown。
- 法规类 `DOCX` 优先：保留条款结构，解析质量通常比扫描 PDF 稳定。
- 网页类资料优先使用同源 `TXT`：比 `HTML` 噪声少。
- 知识卡、办事指南不单独重复入库，而是合并到对应官方来源 Markdown 的「知识摘要」部分。
- 企业内部制度使用 `Markdown入库版`，不使用原始 PDF/DOCX 重复入库。
- FAQ 单独整理为问答文档，用于提升常见问法召回率，但回答依据仍应回链官方来源。

## 生成转换资料

从项目根目录执行：

```bash
python scripts/prepare_langchain_knowledge_base.py \
  --source-root "<资料目录>" \
  --output-dir knowledge_base/langchain_vector_import
```

生成目录：

```text
knowledge_base/langchain_vector_import/
├── README.md
├── excluded_files.md
├── manifest.csv
├── manifest.json
├── upload_plan.csv
└── documents/
    ├── official_sources/
    ├── company_policies/
    └── faqs/
```

`manifest.csv` 是后续批量入库或审计的主清单，核心字段包括：

- `document_id`：标准文档编号，如 `LAW001`、`SX001`、`XA001`、`FAQ001`
- `kb_category`：知识类型，如 `national_law`、`shaanxi_policy`、`xian_service_rule`
- `source_ids`：关联官方来源编号
- `prepared_file`：可上传到后端解析入库的 Markdown 文件
- `source_relative_path`：原始资料包中的相对路径
- `review_status`：复核状态
- `sha256`：生成文档内容哈希

## 入库到 Milvus

当前后端已经提供管理端入口：

```http
POST /api/admin/vector-documents/upload
Content-Type: multipart/form-data
```

建议流程：

1. 启动 `mysql`、`milvus`、`backend`、`frontend`。
2. 配置 `MILVUS_URI`、`MILVUS_COLLECTION` 和 Embedding 能力。默认优先使用 `backend/models/bge-m3` 本地模型；如果本地模型依赖不可用，则需要配置 `LANGCHAIN_API_KEY` 和 `LANGCHAIN_EMBEDDING_MODEL`。
3. 登录管理端，进入「来源管理」。
4. 按 `upload_plan.csv` 上传 `documents/` 下的 Markdown 文件。
5. 上传时选择对应租户；企业内部制度建议只给对应租户入库。

也可以使用自动构建脚本批量入库：

```bash
cd backend
python scripts/build_milvus_vector_db.py \
  --manifest ../knowledge_base/langchain_vector_import/manifest.csv \
  --tenant-code demo-sx \
  --version v20260620 \
  --activate
```

Docker 部署时使用：

```bash
docker compose --profile tools run --rm vector-builder
```

构建脚本会把本次 manifest 转换成一个独立的 Milvus collection，并在 MySQL 中记录版本元数据。默认 collection 命名规则为：

```text
{MILVUS_BASE_COLLECTION}_{tenant_code}_{version}
```

例如 `MILVUS_BASE_COLLECTION=slc_compliance_docs`、租户 `demo-sx`、版本 `v20260620` 会生成：

```text
slc_compliance_docs_demo_sx_v20260620
```

常用版本参数：

- `--version`：指定版本号；不传则自动生成时间戳版本。
- `--base-collection`：指定版本化 collection 前缀。
- `--collection-name`：完全指定本次写入的 Milvus collection。
- `--activate` / `--no-activate`：构建成功后是否立即切换当前问答检索版本。
- `--reset-collection`：构建前删除目标 collection，适合重建同一版本。
- `--include-manifest-faqs`：同时索引 `manifest.csv` 中的 `standard_faq` Markdown。
### FAQ 入库策略

FAQ 已纳入 Milvus 向量库，但与普通资料分开标识：

- FAQ 向量 metadata 使用 `document_type=faq`，并写入 `document_id`、`category`、`risk_level` 等 manifest 元数据。
- 普通政策、制度、办事资料 metadata 使用 `document_type=document`。
- 问答检索返回时，FAQ 来源显示为 `[FAQ] ...`，普通资料显示为 `[文档] ...`。

构建脚本不再读取 MySQL FAQ，也不再提供后台 FAQ CRUD。FAQ 应先由 `scripts/prepare_langchain_knowledge_base.py` 整理成 Markdown 和 manifest 记录，再通过版本化构建写入 Milvus；如需更新 FAQ，修改源资料后重建并激活新的向量版本。

如需先构建但不切换线上检索：

```bash
cd backend
python scripts/build_milvus_vector_db.py \
  --manifest ../knowledge_base/langchain_vector_import/manifest.csv \
  --tenant-code demo-sx \
  --version v20260620-review \
  --no-activate
```

审核通过后可在管理端「向量库版本」页面激活该版本，也可以调用：

```http
PUT /api/admin/vector-versions/{version_id}/activate
Content-Type: application/json

{"tenant_id": 1}
```

回滚同理：选择任意历史 `ready` 版本激活即可。激活动作只切换 `milvus_collection` 和 `active_vector_version_id`，不会删除旧 collection。

后端会完成：

- Markdown 文本解析
- `RecursiveCharacterTextSplitter` 切分
- Embedding 生成
- Milvus collection 写入
- 租户 metadata 注入

推荐环境变量：

```env
VECTOR_CHUNK_SIZE=500
VECTOR_CHUNK_OVERLAP=50
VECTOR_TOP_K=4
MILVUS_COLLECTION=slc_compliance_docs
```

## 数据如何进入向量库

转化链路如下：

```text
原始资料包
  -> 去重选择主资料
  -> 统一生成 Markdown
  -> 写入 manifest 元数据
  -> 后端解析上传
  -> 文本切分 chunk
  -> Embedding
  -> Milvus 向量和 metadata
  -> LangChain 检索增强问答
```

每个 chunk 会携带租户、文件名、标题、来源编号等 metadata。问答时后端按租户过滤后进行相似度检索，再把命中的片段注入 LangChain Prompt。

## 不建议直接入库的内容

以下资料更适合保留为项目管理、配置或审计资料，不建议直接作为业务问答知识：

- 资料包索引和完整性报告
- 数据库 SQL
- 接口文档
- Dify Prompt 和导入说明
- 测试验收资料
- 商业化汇报资料
- 下载日志和 JSON 抓取元数据

这些内容一旦进入向量库，容易让用户问政策问题时检索到项目说明、接口字段或测试数据，影响回答质量。
