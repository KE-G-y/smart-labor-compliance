# Debug Session: normal-query-no-match

Status: OPEN

## Problem

用户正常咨询劳动合规问题时，页面显示“外部模型已尝试调用但回退 knowledge_base_no_match”，没有检索到答案。

## Constraints

- 在获得运行时证据前不修改业务逻辑。
- 不主动启动服务、服务器、数据库或后台进程。
- 优先读取现有配置、数据库状态、Milvus 集合和后端检索链路。

## Hypotheses

1. 问答链路使用的租户、collection 或 active vector version 与已成功入库的数据不一致。
2. Milvus 集合中存在数据，但检索表达式 `metadata["tenant_id"] == ...` 与写入的 metadata 不匹配，导致过滤后为空。
3. 混合检索或 dense fallback 实际抛错/返回空，`_has_knowledge_evidence()` 因吞掉异常而表现为未命中。
4. 用户问题包含的上下文没有进入向量检索 query，导致泛化问题无法召回具体 FAQ/政策片段。
5. 预检阈值过严或只判断“是否有任意来源”，但 source 转换失败，导致有检索结果仍被判定无证据。

## Evidence Log

- Pending.
