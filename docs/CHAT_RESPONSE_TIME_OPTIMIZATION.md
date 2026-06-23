# 问答耗时记录与优化方案

最后梳理日期：2026-06-23

本文说明系统如何记录每次问答耗时、可以在哪里查看耗时数据，以及当 LangChain、Milvus 或 Dify 链路变慢时如何排查和优化。

## 记录口径

当前 `response_time` 记录的是完整接口耗时，单位为毫秒。计时从后端收到请求开始，到回答生成、质量评估、问答日志落库完成并准备返回前结束。

覆盖接口：

- `POST /api/chat`
- `POST /api/chat-with-file`

完整接口耗时包含：

- 参数校验、租户解析、用户输入脱敏
- 前置问题判断，例如问候、系统角色说明、非业务高风险问题拦截
- LangChain 链路中的 Milvus 检索、rerank、Prompt 组装和模型调用
- Dify 链路中的工作流调用和附件转交
- 答案质量报告生成
- MySQL 问答日志写入

因此，`response_time` 不是单纯的大模型响应耗时，而是用户实际等待一次问答结果的总耗时。

## 数据写入位置

每次成功生成回答后，后端会把耗时写入：

- MySQL 表：`slc_chat_logs.response_time`
- 返回给前端的字段：`response_time`
- 答案质量报告：`evaluation.metrics.response_time_ms`
- 答案质量维度：`evaluation.dimensions[key=latency]`

后端实现位置：

- `backend/app/routers/chat.py`：使用 `time.perf_counter()` 记录接口完整耗时，并在 `_persist_chat_log()` 中统一写入日志和返回体。
- `backend/app/services/quality_reports.py`：将耗时纳入答案质量报告，慢请求会生成优化建议。
- `backend/app/services/dify_service.py`：服务内部仍保留链路阶段耗时，最终返回给用户和落库的耗时以路由层完整接口耗时为准。

## 查看位置

用户端：

- 首页回答卡片会显示 `本次用时`。
- 历史记录会显示每条问答的 `response_time`。

管理员端：

- `问答日志` 页面可以查看单条问答响应时间。
- `概览 Dashboard` 会展示平均响应耗时。
- 答案质量报告中会展示 `问答耗时` 维度，以及慢请求对应的建议。

数据库：

```sql
SELECT id, provider, risk_level, response_time, created_at
FROM slc_chat_logs
ORDER BY created_at DESC
LIMIT 20;
```

慢请求排查：

```sql
SELECT provider, COUNT(*) AS total, AVG(response_time) AS avg_ms, MAX(response_time) AS max_ms
FROM slc_chat_logs
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY provider
ORDER BY avg_ms DESC;
```

## 慢请求分级

| 耗时 | 状态 | 处理建议 |
| --- | --- | --- |
| `<= 3000ms` | 正常 | 一般不需要处理。 |
| `3001ms - 10000ms` | 可接受 | 观察 P95、P99，优先优化高频问题。 |
| `10001ms - 30000ms` | 建议优化 | 检查 Milvus 检索、rerank、Prompt 长度、模型响应或 Dify 工作流。 |
| `> 30000ms` | 高优先级排查 | 需要查看外部服务超时、网络、模型服务和知识库检索配置。 |

质量报告中的 `latency` 维度使用同一套分级。超过 `10000ms` 时，报告会根据 `provider` 给出 LangChain、Dify 或通用排查建议。

## 优化方案

### 1. 提高前置判断命中率

简单问候、系统角色介绍、非业务高风险问题应尽量由 `precheck` 直接返回，避免进入 Milvus 和大模型调用。

重点检查：

- `backend/app/services/question_guard.py`
- 常用问候和系统角色说明是否覆盖真实用户表达
- 非系统相关高风险问题是否返回防范性预置回复

预期效果：

- 问候类问题通常可以在数百毫秒内返回。
- 减少无效模型调用成本。

### 2. 控制 Milvus 检索规模

LangChain 链路慢时，优先检查 Milvus 召回量和切片配置。

建议配置：

- `VECTOR_TOP_K` 不宜过大，常规问答建议从 `5` 到 `8` 开始。
- `VECTOR_CHUNK_SIZE` 需要兼顾语义完整度和 Prompt 长度。
- `VECTOR_CHUNK_OVERLAP` 不宜过大，避免重复内容进入上下文。

如果召回结果长期过多但有效来源少，应优化知识库切分和 `manifest.csv` 元数据，而不是单纯提高 `VECTOR_TOP_K`。

### 3. 谨慎启用 rerank

rerank 可以提升召回质量，但会增加耗时。建议：

- 线上先观察不开 rerank 的命中率和质量报告。
- 只在召回结果质量不稳定、相似文档较多时启用。
- 本地模型路径未准备好时，不要启用 `LOCAL_RERANKER_ENABLED`。

相关配置：

- `LOCAL_RERANKER_ENABLED`
- `LOCAL_RERANKER_MODEL_PATH`
- 管理端「系统配置」里的本地模型配置

### 4. 缩短 Prompt 和上下文

如果模型生成耗时偏高，通常和 Prompt、召回片段、用户补充信息过长有关。

建议：

- 保留必要来源和结论结构，减少重复提示词。
- 对 `known_facts`、`verification_focus` 做长度控制。
- 管理端默认回答格式保持清晰，但不要强制输出过长模板。

### 5. 优化模型服务

LangChain 使用 OpenAI-compatible 接口或本地模型时，需要关注模型服务自身响应。

建议：

- 检查 `LANGCHAIN_BASE_URL`、`LANGCHAIN_MODEL`、`LANGCHAIN_TIMEOUT_SECONDS`。
- 本地 `bge-m3`、`bge-reranker-large` 首次加载较慢，可在服务启动后做预热。
- Docker 环境确认模型目录挂载到容器内相对路径，例如 `backend/models/...`。

### 6. 优化 Dify 工作流

Dify 慢请求常见原因是工作流节点过多、外部知识库检索慢或超时时间过长。

建议：

- 删除无用节点和重复 LLM 节点。
- 检查 Dify 内部知识库检索 TopK。
- 检查 `DIFY_TIMEOUT_SECONDS` 是否过大或过小。
- 附件问答走 `chat-with-file` 时，确认附件解析链路是否必要。

### 7. 使用合适的查询方案

管理员可以在「系统配置」中控制用户问答链路：

- `langchain_first`：优先使用 LangChain/Milvus，失败后 Dify 兜底。
- `dify_first`：优先 Dify，失败后 LangChain 兜底。
- `langchain_only`：只使用 LangChain。
- `dify_only`：只使用 Dify。
- `vector_only`：只使用向量知识库命中保护，不调用外部模型。

如果目标是降低平均耗时，可以先观察各 `provider` 的平均耗时，再调整查询方案。

### 8. 建立慢日志运营机制

建议定期统计：

- 平均响应耗时
- P95 / P99 耗时
- 各 `provider` 的慢请求占比
- 高风险问题的耗时
- 命中 `kb_no_match` 的问题占比

当前系统已有单条耗时、平均耗时和质量报告。生产环境可继续增加慢日志导出、告警和按租户统计。

## 验证方式

后端语法和质量报告测试：

```bash
cd backend
python -m py_compile app/routers/chat.py app/services/quality_reports.py app/services/dify_service.py
pytest tests/test_quality_reports.py
```

前端构建：

```bash
npm --prefix frontend run build
```

文档中心白名单检查：

```bash
cd backend
python - <<'PY'
from app.routers.project_docs import DOCUMENTS, _resolve_document_path
for doc in DOCUMENTS:
    _resolve_document_path(doc)
print(len(DOCUMENTS))
PY
```
