# 企业用工与社保合规智能平台

基于 `Vue 3 + FastAPI + MySQL + Dify + RAGFlow` 的前后端分离项目。首期聚焦陕西地区企业用工、社保、医保、假期和劳动争议场景，支持多租户、数据隔离、后台知识运营、问答日志、反馈闭环和测试数据验收。

## 核心能力

- 前后端分离：`frontend/` 与 `backend/` 独立运行
- 本机 Docker MySQL：默认使用 `employment` 数据库
- 多租户：新增租户、租户管理员、本租户数据隔离
- 安全：JWT、bcrypt、敏感信息脱敏、限流、请求体限制、安全响应头
- 智能问答：Dify API Key 可配置，未配置时使用本地 FAQ 兜底
- RAGFlow 配合：用于资料整理、知识卡和知识库建设
- 国际化：前端支持中文与英文切换
- 演示数据：启动自动导入租户、账号、来源、FAQ、知识包和测试问题

## 技术栈与选型优势

| 层级 | 技术 | 选择优势 |
| --- | --- | --- |
| 前端 | Vue 3 + Vite | Vue 3 组合式 API 适合拆分复杂后台页面，Vite 启动和热更新速度快，便于快速迭代用户问答台与管理后台。 |
| 后端 | Python + FastAPI | FastAPI 原生支持类型标注、Pydantic 校验和 OpenAPI 文档，适合承载多租户 API、问答接口和后台管理接口。 |
| 数据库 | MySQL + SQLAlchemy | MySQL 易部署、运维成本低，适合保存租户、日志、FAQ、来源目录等结构化数据；SQLAlchemy 让模型、查询和兼容迁移更集中。 |
| 安全 | JWT + bcrypt + 脱敏中间件 | JWT 适合前后端分离认证，bcrypt 保护密码哈希，后端统一脱敏和限流可降低日志与接口侧的数据泄露风险。 |
| AI 编排 | Dify | Dify 负责 Chatflow、Prompt 约束和模型接入，让业务后端保持稳定，AI 能力可以独立调优和替换。 |
| 知识整理 | RAGFlow | RAGFlow 适合政策资料清洗、知识卡整理和人工复核，补齐原始法规、网页和企业制度进入问答前的治理环节。 |

整体架构采用“业务系统稳定落库 + AI 能力可配置接入 + 本地 FAQ 兜底”的方式：即使 Dify 或 RAGFlow 暂不可用，核心后台、日志、来源目录和高频 FAQ 仍可运行。

## 项目结构

```text
.
├── backend/                 # FastAPI 后端、模型、路由、服务与演示数据
├── frontend/                # Vue 3 + Vite 前端
├── docs/                    # 运维、安全、多租户、Dify/RAGFlow 配合文档
├── sql/                     # MySQL 初始化参考脚本
├── 后端需求文档.md
├── 前端需求文档.md
└── 企业用工与社保合规智能平台项目书_商业化正式版.md
```

## 快速启动

以下命令默认从项目根目录执行。

推荐使用一键脚本同时启动后端与前端：

```bash
./scripts/start_project.sh
```

访问 `http://localhost:3000`


停止项目：

```bash
./scripts/stop_project.sh
```

如需手工排障，也可以分别启动：

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

## 初始账号

- 平台超管：`admin / Admin@123456`
- 演示租户管理员：`tenant_admin / Tenant@123456 / demo-sx`

## 文档

- [操作文档](docs/OPERATION.md)
- [Dify 与 RAGFlow 配合开发指南](docs/DIFY_RAGFLOW_GUIDE.md)
- [安全与多租户设计说明](docs/SECURITY_AND_TENANCY.md)
- [MySQL 初始化参考](sql/init_schema.sql)
- [后端需求文档](后端需求文档.md)
- [前端需求文档](前端需求文档.md)
- [商业化项目书](企业用工与社保合规智能平台项目书_商业化正式版.md)

## 重要说明

演示数据中含部分“待复核/演示口径”的政策来源，正式上线前必须按陕西省人社厅、医保局、西安市人社局等官方渠道核验最新口径。
