# Docker 部署说明

本项目提供一套 `Docker Compose` 部署配置，包含：

- `frontend`：`Vue 3 + Vite` 生产构建，由 `Nginx` 托管静态资源并代理 `/api`
- `backend`：`FastAPI` 服务
- `mysql`：业务数据库
- `milvus`：向量数据库
- `etcd` / `minio`：`Milvus standalone` 依赖服务

## 快速启动

从项目根目录执行：

```bash
cp .env.example .env
```

首次启动前，至少修改 `.env` 中的以下配置：

- `JWT_SECRET_KEY`
- `INITIAL_ADMIN_PASSWORD`
- `DB_PASSWORD`
- `LANGCHAIN_API_KEY`，如需启用 LangChain 问答和 Milvus 文档入库
- `DIFY_API_KEY` / `RAGFLOW_API_KEY`，如需接入对应服务

启动全部服务：

```bash
docker compose up -d --build
```

访问入口：

- 前端页面：`http://localhost:3000`
- 后端接口文档：`http://localhost:8000/docs`
- Milvus WebUI：`http://localhost:9091/webui/`
- MinIO Console：`http://localhost:9001`

默认初始账号：

- 平台超管：`admin / Admin@123456`
- 演示租户管理员：`tenant_admin / Tenant@123456 / demo-sx`

## 文档解析入库

管理端登录后进入「来源管理」，使用「文档解析入库」上传文档。后端会解析文件、按租户切分文本，并写入 `MILVUS_COLLECTION` 指定的 Milvus collection。

支持文件类型：

- `TXT`
- `Markdown`
- `CSV`
- `HTML`
- `PDF`
- `DOCX`
- `XLSX`

文档入库需要配置可用的 `LANGCHAIN_API_KEY` 和 embedding 模型；未配置时，基础后台仍可运行，但系统内问答不会使用 MySQL FAQ 兜底。

## 向量库版本管理

项目采用“一个版本对应一个 Milvus collection”的方式管理向量库版本。自动构建脚本会在 MySQL 的 `slc_vector_collection_versions` 表记录版本号、collection 名称、manifest 哈希、文档数量、chunk 数量、构建状态和激活状态。

激活版本不会移动或覆盖旧向量数据，只会更新运行配置中的：

- `milvus_collection`
- `active_vector_version_id`

因此回滚时只需要在管理端进入「向量库版本」，选择历史 `ready` 版本并点击「激活」。当前激活版本不能归档；归档只影响版本状态，不会自动删除 Milvus collection。

## 自动构建 Milvus 向量库

项目内置了一次性构建服务 `vector-builder`，用于把 `knowledge_base/langchain_vector_import/manifest.csv` 中的资料批量写入 Milvus；FAQ 也应作为 manifest 中的 `standard_faq` 文档入库。

启动基础服务后执行：

```bash
docker compose --profile tools run --rm vector-builder
```

构建完成后，摘要会写入后端持久化卷中的：

```text
storage/vector-build-summary.json
```

常用参数可以通过 `.env` 控制：

- `VECTOR_BUILD_TENANT_CODE`：入库租户，默认 `demo-sx`
- `VECTOR_BUILD_CATEGORIES`：按知识类型过滤，留空表示全部入库
- `VECTOR_BUILD_VERSION`：版本号，留空时自动生成 `vYYYYMMDDHHMMSS`
- `VECTOR_BUILD_ACTIVATE`：构建成功后是否自动激活，默认 `--activate`，可改为 `--no-activate`
- `MILVUS_BASE_COLLECTION`：版本化 collection 的基础前缀，默认 `slc_compliance_docs`

例如只过滤 manifest 中的官方政策法规和陕西/西安资料：

```env
VECTOR_BUILD_CATEGORIES=national_law,shaanxi_policy,xian_service_rule
VECTOR_BUILD_VERSION=v20260620
```

构建后生成的 collection 名称形如：

```text
slc_compliance_docs_demo_sx_v20260620
```

FAQ 会以 `document_type=faq` 写入同一个版本 collection，普通资料使用 `document_type=document`。脚本不再读取 MySQL FAQ，默认索引 `manifest.csv` 中的 `standard_faq` 文件。

如需清空并重建 collection，可以覆盖默认命令：

```bash
docker compose --profile tools run --rm vector-builder \
  python scripts/build_milvus_vector_db.py \
  --manifest knowledge_base/langchain_vector_import/manifest.csv \
  --tenant-code demo-sx \
  --version v20260620 \
  --reset-collection
```

本地非 Docker 环境也可以从项目根目录执行：

```bash
cd backend
python scripts/build_milvus_vector_db.py \
  --manifest ../knowledge_base/langchain_vector_import/manifest.csv \
  --tenant-code demo-sx \
  --version v20260620 \
  --activate
```

正式入库前可先查看计划：

```bash
cd backend
python scripts/build_milvus_vector_db.py \
  --manifest ../knowledge_base/langchain_vector_import/manifest.csv \
  --tenant-code demo-sx \
  --dry-run
```

## 常用操作

查看服务状态：

```bash
docker compose ps
```

查看后端日志：

```bash
docker compose logs -f backend
```

停止服务：

```bash
docker compose down
```

停止并清理所有持久化数据：

```bash
docker compose down -v
```

## 端口与平台说明

如果本机端口被占用，可以在 `.env` 中调整：

- `FRONTEND_HOST_PORT`
- `BACKEND_HOST_PORT`
- `MYSQL_HOST_PORT`
- `MILVUS_HOST_PORT`
- `MILVUS_WEBUI_HOST_PORT`
- `MINIO_API_HOST_PORT`
- `MINIO_CONSOLE_HOST_PORT`

`MILVUS_PLATFORM` 默认设置为 `linux/amd64`，便于在 Docker Desktop 环境拉起官方 Milvus 镜像。如果运行环境已经原生支持目标镜像架构，可以按需调整。

`DIFY_BASE_URL`、`RAGFLOW_BASE_URL` 默认使用 `host.docker.internal`，用于容器访问宿主机上运行的 Dify 或 RAGFlow；如果它们也部署在同一个 Compose 网络中，请改成对应 service name。

## 持久化数据

Compose 使用 named volumes 保存数据，不依赖宿主机绝对路径：

- `mysql_data`
- `etcd_data`
- `minio_data`
- `milvus_data`
- `backend_storage`

生产环境上线前，请结合实际基础设施补充数据库备份、对象存储备份、日志采集、TLS 终止和密钥管理。
