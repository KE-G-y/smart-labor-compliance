# Debug Session: milvus-offline-status

Status: OPEN

## Problem

后台仪表盘显示 Milvus 服务 offline，但知识库入库已成功完成并激活。

## Constraints

- 在获得运行时证据前不修改业务逻辑。
- 不主动启动服务、服务器、数据库或后台进程。
- 优先读取现有容器状态、数据库配置、后端接口返回和日志。

## Hypotheses

1. Milvus 容器实际在线，但后端健康检查使用了错误地址或协议。
2. 前端显示的是后端 API 返回的旧状态，后端进程没有重启导致配置未更新。
3. 后台健康检查接口仍连接基础 collection 或旧 collection，而不是当前激活的 `bge_m3_hybrid_500_50_v2`。
4. Milvus 服务本身健康，但健康检查因为 `langchain-milvus` hybrid/ORM 兼容问题误判失败。
5. 前端字段映射或状态判断逻辑把“可检索但有警告”显示成 offline。

## Evidence Log

- Pending.
