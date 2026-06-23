# 前端应用

Vue 3 + Vite 前端，包含用户问答台、历史记录和多租户管理后台。

## 技术栈优势

- `Vue 3`：组合式 API 便于把问答台、后台表格、弹窗、分页、选择器等状态逻辑拆分维护。
- `Vite`：开发服务器启动快，热更新轻量，适合 MVP 阶段频繁调整页面和交互。
- `Vue Router`：前台问答、历史记录和管理后台路由清晰隔离，后台页面可通过路由元信息绑定权限。
- `Axios`：统一封装 `/api` 请求、JWT 注入、租户编码请求头和 401 登录失效处理。
- `轻量组件化`：项目自有 `AppTable`、`AppPagination`、`AppSelect`、`EllipsisText` 等组件，减少重复页面代码，同时避免过早引入笨重 UI 框架。
- `内置国际化`：`src/i18n.js` 直接维护中英文文案，满足演示和多租户后台的双语展示需求。

## 启动

以下命令默认从项目根目录执行。

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3000`。Vite 会将 `/api` 代理到 `http://127.0.0.1:8000`。

## 页面

- `/`：用户问答，展示来源、风险等级、办事路径、反馈
- `/history`：当前租户和浏览器用户的历史记录
- `/project-docs`：项目说明文档中心，在线查看 README、架构、部署、知识库和排障文档；该路由独立访问，不显示在顶部主导航中
- `/docs`：兼容旧入口，自动重定向到 `/project-docs`
- `/admin/login`：管理后台登录
- `/admin`：统计、Dify/RAGFlow 在线状态
- `/admin/tenants`：租户管理
- `/admin/sources`：来源管理
- `/admin/vector-versions`：Milvus 向量库版本管理、版本激活、归档和批量入库质量报告查看
- `/admin/logs`：问答日志
- `/admin/feedbacks`：反馈管理
- `/admin/packages`：知识包管理
- `/admin/tests`：验收测试问题
- `/admin/accounts`：账号权限
- `/admin/system-config`：查询方案、LangChain、Milvus、Dify/RAGFlow 和本地模型配置

## 国际化

前端内置中文和英文切换，当前实现位于 `src/i18n.js`。

## 构建

```bash
npm run build
```

更多操作说明见项目根目录 `docs/DOCUMENTATION_INDEX.md` 和 `docs/OPERATION.md`。
