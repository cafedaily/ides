# API 接口一览

全部在 `127.0.0.1:8730`，无认证。

## 数据接口

| 方法 | 路径 | 用途 | 请求体 | 响应 |
|---|---|---|---|---|
| GET | `/api/health` | 心跳 + 概况 | — | `{ok, app, fmt, v, ideas, sparks, cold, graph_at}` |
| GET | `/api/state` | 全量读 | — | `{ideas, sparks, cold, conf}` |
| POST | `/api/state?mode=merge\|replace` | 全量写 | `{ideas, sparks, cold, conf}` | `{ok, mode, ...health}` |
| POST | `/api/rebuild` | 重建图谱缓存 | — | `{ok, docs, terms, bridges, sim}` |

## 图谱接口

| 方法 | 路径 | 用途 | 参数 | 响应 |
|---|---|---|---|---|
| GET | `/api/graph` | 全量图谱 | — | `{nodes, edges, sim, cooc, bridges}` |
| GET | `/api/bridges?limit=N` | 桥列表 | limit (默认 20) | `{bridges, n_docs}` |
| GET | `/api/related?id=X` | 相关想法 | id | `{id, related, bridges, terms}` |
| GET | `/api/path?a=X&b=Y` | 两个想法间的路径 | a, b | `{found, hops, cost, steps}` 或 `{found:false, why}` |
| GET | `/api/search?q=X` | 按词搜索 | q | `{q, hits}` |

## 导入导出

| 方法 | 路径 | 用途 | 请求体/参数 | 响应 |
|---|---|---|---|---|
| GET | `/api/export?pass=X` | 导出 jsonl | pass (可选加密) | `{text}` |
| POST | `/api/import?apply=1&mode=X` | 导入 | `{text, pass?}` | `{ok, counts, warnings, applied}` |

## LLM 代理

| 方法 | 路径 | 用途 | 请求体 | 响应 |
|---|---|---|---|---|
| POST | `/api/chat` | 转发到 OpenAI 兼容模型 | `{messages, json?, temperature?, max_tokens?}` | `{ok, text}` 或 `{ok:false, error}` |

模型配置从 `conf.models[0]` 读取（存在 kv 表里）。
字段：`base`（端点 URL）、`model`（模型名）、`key`（API key）。
