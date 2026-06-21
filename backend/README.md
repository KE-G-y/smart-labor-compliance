# 后端服务

FastAPI 后端负责认证、多租户隔离、问答日志、来源管理、反馈闭环、LangChain 问答编排、Milvus 向量检索、Dify 兼容回退与知识库边界控制。

## 技术栈优势

- `FastAPI`：基于类型标注自动生成 OpenAPI 文档，接口参数校验清晰，适合快速交付后台管理、问答和反馈等 REST API。
- `Pydantic`：请求体、响应模型和配置读取统一校验，能在接口入口提前拦截错误数据。
- `SQLAlchemy`：业务模型集中在 `app/models/`，查询逻辑可复用，并通过启动时的兼容补列逻辑支持演示库平滑升级。
- `PyMySQL + MySQL`：与本机 Docker MySQL 配合简单，适合保存租户、账号、问答日志、来源目录、知识包和配置等结构化数据。
- `JWT + bcrypt`：满足前后端分离登录态和密码哈希存储要求，配合角色权限实现平台超管、租户管理员、运营人员和只读人员的能力边界。
- `LangChain/Milvus/Dify/RAGFlow 可配置接入`：后端通过服务层封装外部 AI 与知识库能力，LangChain 优先调用 OpenAI-compatible 模型并检索 Milvus 文档片段，Dify 作为兼容回退；系统内问题未命中知识库时不会基于 MySQL FAQ 或外部常识补充结论。

## 启动

后端依赖建议使用 Python 3.11 安装，与 Docker 镜像版本保持一致。不要使用 Python 3.14 运行本项目，否则部分依赖可能没有可用 wheel，触发 Rust 源码编译失败。

以下命令默认从项目根目录执行。

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 配置

本地开发配置在 `.env` 中，默认连接本机 Docker MySQL：

- database：`employment`
- user：`root`
- password：`infini_rag_flow`

`.env` 已被 git 忽略。首次本地启动时，`scripts/start_project.sh` 会从 `backend/.env.example` 自动生成一份默认配置；生产部署前必须修改 `JWT_SECRET_KEY`、初始密码和 LangChain/Dify/RAGFlow API Key。

常用 LangChain 配置项：

- `LANGCHAIN_API_KEY`：模型服务 API Key，需要从 OpenAI 或 OpenAI-compatible 模型服务商控制台创建
- `LANGCHAIN_MODEL`：模型名称，默认 `qwen3.7-max`，由所选模型服务商支持列表决定
- `LANGCHAIN_EMBEDDING_MODEL`：Embedding 模型标识，默认 `bge-m3`；启用 `LOCAL_EMBEDDING_ENABLED=true` 时，入库与检索优先使用 `LOCAL_EMBEDDING_MODEL_PATH` 指向的本地模型
- `LANGCHAIN_BASE_URL`：OpenAI-compatible 地址，可留空使用默认端点；接入代理、私有网关或国内模型服务时填写服务商提供的 Base URL
- `LANGCHAIN_TEMPERATURE`：生成温度，范围 `0-2`
- `LANGCHAIN_TIMEOUT_SECONDS`：调用超时时间，范围 `5-300`
- `MILVUS_URI`：Milvus 连接地址，本地一键脚本启动的 Milvus 使用 `http://127.0.0.1:19530`；Docker 容器内服务互访使用 `http://milvus:19530`
- `MILVUS_TOKEN`：Milvus / Zilliz Cloud 鉴权 Token，可选
- `MILVUS_COLLECTION`：向量集合名称，项目默认 `slc_compliance_docs`，向量版本构建后会由后台激活具体版本 collection
- `VECTOR_TOP_K`：问答检索片段数，默认 `4`
- `VECTOR_CHUNK_SIZE` / `VECTOR_CHUNK_OVERLAP`：文档切分参数

管理端「来源管理」提供文档解析入库入口，支持 `TXT`、`Markdown`、`CSV`、`HTML`、`PDF`、`DOCX`、`XLSX`。

如需启用 `LOCAL_EMBEDDING_ENABLED` 或 `LOCAL_RERANKER_ENABLED`，需要额外安装 `requirements-local-models.txt`。本地模型依赖要求 `torch>=2.6`，低版本 torch 会因 `torch.load` 安全限制导致 Transformers 拒绝加载部分模型权重。

## 初始化

启动时会自动建表并幂等导入演示数据。当前演示数据包含 1 个演示租户、2 个管理员账号、来源目录、1 个知识包和 4 条测试问题；FAQ 通过知识库资料整理与 Milvus 构建流程维护。也可以手动执行：

```bash
python -c "from app.database import init_db; init_db()"
```

## 初始账号

- 平台超管：`admin / Admin@123456`
- 演示租户管理员：`tenant_admin / Tenant@123456 / demo-sx`

更多说明见项目根目录的 `docs/OPERATION.md`、`docs/SECURITY_AND_TENANCY.md`。
