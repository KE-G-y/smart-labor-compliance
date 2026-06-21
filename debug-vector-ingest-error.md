# Debug Session: vector-ingest-error

Status: OPEN

## Problem

执行知识库的数据向量库入库操作报错。

## Constraints

- 在获得运行时证据前不修改业务逻辑。
- 不主动启动服务、服务器、数据库或后台进程。
- 优先读取现有日志、容器状态和代码路径定位问题。

## Hypotheses

1. 本地 Embedding 已启用，但本地模型依赖或 torch 版本不满足要求，导致向量生成失败。
2. LangChain/OpenAI-compatible Embedding 未配置 API Key，且本地 Embedding 不可用，导致没有可用 Embedding provider。
3. Milvus 服务虽然健康，但 collection/schema 或连接参数与代码预期不一致，导致入库失败。
4. 知识库来源文档解析后没有有效 chunk，导致构建流程在空数据或元数据阶段失败。
5. 后端运行环境与当前 shell 环境不一致，配置项或依赖版本在实际服务进程中不同。

## Evidence Log

- Docker Compose 依赖服务 mysql/minio/etcd/milvus 均为 healthy。
- `backend/.env` 中 `LOCAL_EMBEDDING_ENABLED=true`，`LOCAL_EMBEDDING_MODEL_PATH=models/bge-m3`。
- 后端日志多次出现 `Local embedding unavailable; falling back to OpenAI embeddings`，错误为 Transformers 要求 `torch>=2.6`。
- 当前 shell Python 环境未安装 `torch`、`transformers`、`sentence_transformers`，但运行中后端曾加载到旧 torch，说明运行环境/历史进程依赖状态可能不一致。
- 数据库 `slc_vector_collection_versions` 最新记录 `v20260620093839` 为 `failed`，`document_count=57`、`indexed_count=0`、`failed_count=57`、`chunk_count=0`。
- 系统配置表 `slc_system_config` 中 `local_embedding_enabled=true`，`milvus_uri=http://127.0.0.1:19530`，`milvus_collection=slc_compliance_docs`，`langchain_embedding_model=bge-m3`。

## Current Assessment

第一阶段根因是向量构建优先尝试本地 Embedding，但本地模型依赖不可用或 torch 版本低于 2.6，导致 57 个文档全部失败。增强 summary errors 后，第二次构建显示新根因变为 `ConnectionNotExistException: should create connection first`。

## Follow-up Evidence

- 最新构建 `v20260620095402` 仍为 failed，`document_count=57`、`indexed_count=0`、`failed_count=57`、`chunk_count=0`。
- 新增 `build_summary.errors` 中前 20 条均为 `ConnectionNotExistException`。
- 独立探针复现：`langchain-milvus==0.3.3` 创建 store 后执行 `add_texts()` 会在 `Collection(self.collection_name, using=self.alias)` 处报连接别名不存在。
- 手动注册 `pymilvus.connections.connect(alias=store.alias, uri=...)` 后，若构造器仍传 `timeout`，会触发 `MilvusClient.insert() got multiple values for keyword argument 'timeout'`。
- 移除 Milvus 构造器 `timeout` 并注册 `store.alias` 后，独立探针和项目 `MilvusVectorService` 探针均能成功插入调试 collection。

## Fix Applied

- `MilvusVectorService._vector_store()` 不再向 `langchain_milvus.Milvus` 构造器传 `timeout`。
- 创建 store 后显式用 `pymilvus.connections.connect(alias=store.alias, **connection_args)` 注册旧 ORM 连接别名，兼容 `langchain-milvus` 内部仍调用 `Collection(..., using=alias)` 的路径。
- 使用项目路径探针验证 `store.add_texts()` 成功，消除 `ConnectionNotExistException`。

## Latest Evidence

- 新版本 `v20260620100306` 曾停留在 `building`，无构建脚本进程运行。
- 对应 Milvus collection `slc_compliance_docs_demo_sx_v20260620100306` 已有行数，说明写入过程部分成功，但脚本未执行最终版本状态落库。
- 已将该 stale building 记录标记为 `failed`，保留 `build_summary.error=vector build process exited before finalizing version status`。
- 构建脚本已增加每个文档后的进度落库，并捕获 `KeyboardInterrupt`，避免后续出现无进程但版本永久 building 的状态。
