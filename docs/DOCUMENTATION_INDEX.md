# 项目文档总索引

最后梳理日期：2026-06-23

本文用于统一说明项目内各类说明文档的用途、可信状态和维护边界。项目运行后，也可以在前端访问：

- 项目说明文档中心：`http://localhost:3000/project-docs`
- 后端 Swagger/OpenAPI：`http://localhost:8000/docs`

说明文档中心的后端接口是 `GET /api/project-docs` 和 `GET /api/project-docs/{doc_id}`。接口只读取后端白名单中的 Markdown 文件，不接收任意文件路径，避免路径穿越和误读服务器文件。前端 `/project-docs` 是独立访问路由，不显示在主导航中；前端 `/docs` 仅做兼容重定向，后端 FastAPI 的 Swagger/OpenAPI 仍是 `/docs`。

## 文档可信状态

| 状态 | 含义 |
| --- | --- |
| 已按当前代码梳理 | 与当前代码结构、启动方式和部署链路已同步，可作为当前使用依据。 |
| 需求基线文档，部分实现已在代码中迭代 | 保留需求和验收背景，具体实现以 `README.md`、`docs/` 和代码为准。 |
| 方案材料，技术细节以 docs/ 与 README 为准 | 可用于商务、交付或项目背景说明，不能替代技术配置文档。 |
| 历史记录，仅作排障参考 | 记录过往问题定位过程，当前环境不一定复现。 |

## 快速开始

| 文档 | 路径 | 当前用途 | 状态 |
| --- | --- | --- | --- |
| 项目总览 README | `README.md` | 项目定位、核心能力、技术栈、快速启动和总入口。 | 已按当前代码梳理 |
| 操作文档 | `docs/OPERATION.md` | 本地一键启动、参数来源、账号、服务地址、本地模型和日常操作。 | 已按当前代码梳理 |
| 后端 README | `backend/README.md` | FastAPI 后端启动、配置、初始化和 LangChain/Milvus/Dify 相关说明。 | 已按当前代码梳理 |
| 前端 README | `frontend/README.md` | Vue 前端启动、页面路由、构建和前端技术栈说明。 | 已按当前代码梳理 |

## 架构与 AI 链路

| 文档 | 路径 | 当前用途 | 状态 |
| --- | --- | --- | --- |
| 技术架构总览 | `docs/TECHNICAL_ARCHITECTURE.md` | 说明前端、后端、MySQL、Milvus、LangChain、Dify/RAGFlow 的整体架构和流程图。 | 已按当前代码梳理 |
| LangChain 重构说明 | `docs/LANGCHAIN_REFACTOR.md` | 说明 precheck、Milvus 检索、LangChain 生成、Dify 回退、答案评估和 FAQ 向量管理。 | 已按当前代码梳理 |
| 问答耗时记录与优化方案 | `docs/CHAT_RESPONSE_TIME_OPTIMIZATION.md` | 说明每次问答耗时记录口径、查看位置、慢请求分级和优化方案。 | 已按当前代码梳理 |
| Dify 与 RAGFlow 配合开发指南 | `docs/DIFY_RAGFLOW_GUIDE.md` | 说明 Dify 工作流输入输出、RAGFlow 资料整理建议和外部服务连接口径。 | 已按当前代码梳理 |

## 部署与运维

| 文档 | 路径 | 当前用途 | 状态 |
| --- | --- | --- | --- |
| Docker 部署说明 | `docs/DOCKER_DEPLOYMENT.md` | Docker Compose 服务、环境变量、向量构建工具、端口和持久化卷说明。 | 已按当前代码梳理 |
| 安全与多租户设计说明 | `docs/SECURITY_AND_TENANCY.md` | 租户隔离、角色权限、脱敏、限流、数据库连接池和上线检查。 | 已按当前代码梳理 |
| 自动化测试报告 | `docs/AUTOMATED_TEST_REPORT.md` | 后端接口、前端契约、安全边界和回归测试覆盖说明。 | 已按当前代码梳理 |

## 知识库与向量库

| 文档 | 路径 | 当前用途 | 状态 |
| --- | --- | --- | --- |
| LangChain 知识库向量化整理说明 | `docs/KNOWLEDGE_BASE_VECTORIZATION.md` | 说明原始资料如何整理为 Markdown、manifest，并批量构建 Milvus 版本。 | 已按当前代码梳理 |
| LangChain/Milvus 知识库转换资料 README | `knowledge_base/langchain_vector_import/README.md` | 说明当前已整理的政策法规、办事规则、企业制度和 FAQ 入库资料。 | 已按当前代码梳理 |
| 未纳入向量库资料说明 | `knowledge_base/langchain_vector_import/excluded_files.md` | 说明哪些资料不建议直接入库，避免接口、测试或项目管理资料污染业务问答。 | 已按当前代码梳理 |

当前项目中 FAQ 不再由 MySQL 后台 CRUD 管理。FAQ 已整理为 `knowledge_base/langchain_vector_import/documents/faqs/` 下的 Markdown，并通过 `manifest.csv` 作为 `standard_faq` 文档写入 Milvus。检索时 FAQ 使用 `document_type=faq`，普通资料使用 `document_type=document`，前端来源标题也会区分 `[FAQ]` 和 `[文档]`。

业务知识库中的法规、政策、办事指南、企业制度和 FAQ 是 RAG 问答资料，不逐篇放入项目说明文档中心。它们的入库、审核和版本切换应通过 `knowledge_base/langchain_vector_import/README.md`、`manifest.csv`、`backend/scripts/build_milvus_vector_db.py` 和管理端「向量库版本」共同管理。

## 需求、方案与历史记录

| 文档 | 路径 | 当前用途 | 状态 |
| --- | --- | --- | --- |
| 前端需求文档 | `前端需求文档.md` | 前端页面、交互、管理后台和可视化需求基线。 | 需求基线文档，部分实现已在代码中迭代 |
| 后端需求文档 | `后端需求文档.md` | 后端接口、数据模型、权限和外部系统接入需求基线。 | 需求基线文档，部分实现已在代码中迭代 |
| 商业化项目书 | `企业用工与社保合规智能平台项目书_商业化正式版.md` | 项目定位、价值、交付范围和商务说明。 | 方案材料，技术细节以 docs/ 与 README 为准 |
| 向量入库错误排查记录 | `debug-vector-ingest-error.md` | 记录向量入库问题定位过程。 | 历史记录，仅作排障参考 |
| Milvus 离线状态排查记录 | `debug-milvus-offline-status.md` | 记录 Milvus 服务状态问题定位过程。 | 历史记录，仅作排障参考 |
| 普通问题未命中排查记录 | `debug-normal-query-no-match.md` | 记录知识库未命中和问答边界问题定位过程。 | 历史记录，仅作排障参考 |

## 当前准确性口径

- 本地一键启动脚本：`./scripts/start_project.sh`，默认会准备 `backend/.env`，并在 Docker 可用时启动 `mysql`、`etcd`、`minio`、`milvus`。
- 后端本地热重载：`scripts/start_project.sh` 默认 `BACKEND_RELOAD=1`；Docker 后端服务也使用 `uvicorn --reload` 并挂载 `./backend/app`、`./backend/scripts`。
- 前端项目文档中心：`/project-docs` 是独立前端路由，不出现在主导航；前端 `/docs` 会重定向到 `/project-docs`；后端 FastAPI 的 Swagger/OpenAPI 仍是 `/docs`。
- 完整 Docker 服务：`docker compose up -d --build` 会启动 `frontend`、`backend`、`mysql`、`milvus`、`etcd`、`minio`。
- 自动构建向量库：`docker compose --profile tools run --rm vector-builder` 或在 `backend/` 下执行 `python scripts/build_milvus_vector_db.py --manifest ../knowledge_base/langchain_vector_import/manifest.csv --tenant-code demo-sx --activate`。
- 系统内问题必须基于 Milvus 知识库命中回答；未命中时返回知识库边界提示，不使用 MySQL FAQ 或模型外部常识兜底。
- MySQL 用于结构化业务数据和运行配置；Milvus 用于非结构化知识片段的向量检索，二者不能互相替代。

## 维护约定

- 新增项目说明类 Markdown 后，应在 `backend/app/routers/project_docs.py` 的 `DOCUMENTS` 白名单中登记，前端 `/project-docs` 才会展示。
- 文档路径统一写项目内相对路径，不写本机绝对路径。
- 涉及模型、端口、API Key、数据库、Milvus collection 等配置时，以 `.env.example`、`backend/.env.example`、`docker-compose.yml` 和管理端「系统配置」为准。
- 涉及政策法规和社保医保口径时，正式上线前必须按官方渠道复核最新版本。
