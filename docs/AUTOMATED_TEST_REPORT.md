# 自动化测试报告

## 1. 测试目标

本测试报告根据项目根目录 README、前后端需求文档、运维文档、安全与多租户设计说明、Dify/RAGFlow 指南生成。测试目标是覆盖企业用工与社保合规智能平台 MVP 的核心功能、边界问题和安全约束，并用三轮“测试 - 修改 - 回归”持续优化项目。

## 2. 测试范围

### 2.1 后端接口

- 基础服务：`/`、`/health`、安全响应头。
- 用户端：`/api/chat`、`/api/chat-with-file`、`/api/chat/stop`、`/api/history`、`/api/history/export`、`/api/recommended-questions`、`/api/tenant-public`。
- 反馈闭环：`/api/feedback`、`/api/admin/feedbacks`、反馈状态更新。
- 管理端认证：登录、令牌校验、角色权限、越权访问。
- 多租户：用户端租户解析、后台 `tenant_id` 强制过滤、租户管理员跨租户禁止。
- 知识运营：来源目录、知识包、向量版本、测试问题列表。
- 导入导出：来源/知识包 CSV 导入导出、无效文件、缺字段、重复数据覆盖；FAQ 管理接口已移除，FAQ 通过向量资料入库。
- 安全边界：敏感信息脱敏、请求体大小限制、上传文件扩展名和路径安全、只读角色写操作禁止。

### 2.2 前端契约

- API 封装必须覆盖后端真实接口。
- 请求拦截器必须带 `X-Tenant-Code`。
- 401 响应必须清理登录态并跳转登录。
- 路由必须覆盖用户端、历史记录和管理后台主要页面。
- `npm run build` 必须通过，确保 Vue/Vite 可构建。

## 3. 测试环境

- 后端：FastAPI + SQLAlchemy + MySQL。
- 数据库：自动化测试使用专用数据库 `employment_slc_auto_test`，运行前后自动删除。
- 外部 AI：测试环境默认不配置 Dify/RAGFlow API Key，验证知识库边界与降级链路。
- 前端：Node + Vite，执行契约检查和生产构建。

## 4. 自动化脚本

### 4.1 全量执行

```bash
bash scripts/run_full_tests.sh
```

### 4.2 后端单独执行

```bash
cd backend
python -m pytest -q
```

### 4.3 前端单独执行

```bash
cd frontend
npm test
npm run build
```

## 5. 三轮测试记录

### 第一轮

- 状态：已完成。
- 目标：验证新增测试脚本是否可稳定启动测试服务，识别代码真实缺陷与测试脚本偏差。
- 结果：后端 `16` 个用例中 `13` 个通过、`3` 个失败；前端尚未进入执行。
- 发现：
  - FAQ 管理已从 MySQL 后台移除，相关旧用例应改为验证接口不可用。
  - `viewer` 角色可读取来源、反馈、知识包和测试问题，不符合“只读人员仅概览与日志”的权限设计。
  - 超长问题测试使用中文字符时先触发请求体大小限制，未进入 Pydantic 长度校验。
- 修改：
  - FAQ 后台 CRUD 不再作为验收目标，FAQ 改由向量知识库资料管理。
  - 后台来源、反馈、知识包、测试问题读写接口补充模块权限校验。
  - 超长问题用例改用 ASCII 字符，稳定验证 `max_length=3000`。

### 第二轮

- 状态：已完成。
- 目标：针对第一轮发现的问题补充边界用例并修复业务缺陷。
- 结果：全量通过，后端 `16 passed`；前端契约检查通过，API wrapper 与主要路由均匹配；`npm run build` 通过。
- 修改：
  - 新增发散边界测试：禁用知识包短路、跨租户重复来源、上传大小限制、Dify streaming 解析。
  - 来源列表/导出搜索扩展为 `title` + `source_code` + `url`。

### 第三轮

- 状态：已完成。
- 目标：全量回归后确认脚本、前端构建、接口边界和文档一致。
- 结果：第一次新增边界回归 `19 passed / 1 failed`，失败原因为测试仅禁用了一个知识包，而当前租户仍存在其他 active 知识包；调整语义后最终全量通过。
- 最终结果：
  - 后端：`20 passed, 7 warnings in 6.15s`。
  - 前端契约：当前脚本校验用户端、项目说明文档中心、管理端主要页面和向量版本页面；实际数量以 `frontend/scripts/contract-check.mjs` 输出为准。
  - 前端构建：`vite build` 成功。
- 说明：`7 warnings` 来自依赖层的 passlib `crypt` 弃用提醒和 Pydantic V2 class-based config 弃用提醒，不影响本轮功能回归。

## 6. 覆盖矩阵

| 文档要求 | 覆盖脚本 | 覆盖点 |
| --- | --- | --- |
| 智能问答、知识库边界、问答日志 | `backend/tests/test_public_chat_history.py` | 成功问答、空问题、超长问题、历史查询、CSV 导出、清空历史 |
| 敏感信息脱敏 | `backend/tests/test_public_chat_history.py`、`backend/tests/test_feedback_admin_security.py` | 身份证、手机号、邮箱写库前脱敏 |
| 多租户隔离 | `backend/tests/test_feedback_admin_security.py` | 租户管理员不能访问其他租户数据 |
| 后台认证和角色 | `backend/tests/test_feedback_admin_security.py` | 未登录、错误登录、无效授权头、viewer 只读 |
| 反馈闭环 | `backend/tests/test_feedback_admin_security.py` | 提交反馈、后台筛选、状态更新、无效状态 |
| 来源/知识包运营 | `backend/tests/test_admin_catalog_import_export.py` | 来源 CRUD、CSV 导入导出、批量操作、重复覆盖、复核锁定；FAQ 管理接口移除 |
| 上传安全 | `backend/tests/test_admin_catalog_import_export.py` | 非法扩展名、路径归一化、上传大小限制 |
| 请求体限制和安全响应头 | `backend/tests/test_request_guard_and_helpers.py` | 413、`X-Frame-Options`、`Cache-Control` 等 |
| Dify 与知识包边界 | `backend/tests/test_service_and_tenant_edges.py` | 禁用知识包短路、Dify streaming 解析、停止生成任务清理 |
| 跨租户数据唯一性 | `backend/tests/test_service_and_tenant_edges.py` | 同一来源编码/标题/URL 在不同租户内可独立存在 |
| 前端 API 与路由契约 | `frontend/scripts/contract-check.mjs` | API wrapper、租户请求头、401 处理、主要路由 |

## 7. 后续优化建议

- 引入 Playwright 或 Cypress 做真实浏览器端到端测试。
- 把自动化脚本接入 CI，并把 MySQL 测试库改为临时容器。
- 增加 Dify mock server，覆盖 streaming、超时、停止生成和附件上传成功链路。
- 为 CSV 导入增加更严格的字段级错误报告和样例文件。
- 为生产安全增加 JWT 过期、CORS、上传 MIME 嗅探和更细粒度限流测试。
