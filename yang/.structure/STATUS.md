# 后端 (`yang/`) 状态

> 最后更新：2026-09-11

## 是什么

Python 包。从原始中文文本出发，做分词→实体归并→TF-IDF→图谱→HTTP 服务→LLM 代理。
没有第三方依赖，纯标准库。

## 边界

**做什么**：
- 滑动二元组中文分词（不用词典）
- 跨语料实体发现与归并
- TF-IDF 抽词、图谱计算（共现、相似、桥、路径）
- SQLite 存储、想法 CRUD、rebuild
- HTTP API（13 路由 + LLM 代理）
- JSONL 导出格式（签名、加密、校验）
- CLI 入口

**不做什么**：
- 不做前端渲染——前端在 `web/src/`
- 不做词典维护——分词靠统计不靠词典
- 不做多用户/认证——单用户产品
- 不直接调 OpenAI API——通过 chat.py 代理，前端不碰 API key

## 当前真相

- [ ] `python -c "from yang import text, entity, terms, graph, db, store, jsonl, chat, api, server; print('ok')"` → ok
- [ ] `python tests/run.py` → 94 pass, 0 fail, 0 skip
- [ ] `POST /api/chat {"messages":[{"role":"user","content":"hi"}]}` → `{ok:true, text:"..."}`
- [ ] conf.models 从 DB 的 kv 表读（key="conf"），不从环境变量读
- [ ] chat.py 只用 models[0]，不看 conf.route
- [ ] jsonl.py 和 yangdata.js 是同构实现——改一个必须改另一个
- [ ] text.py 的字符集（STOP2, NO_HEAD, NO_TAIL, DET, MEASURE 等）是闭合穷举
- [ ] entity.py 的量词规则：头砍尾不砍，且只在左边有数词时砍

## 不要假设

- ✗ 分词用了 jieba/pkuseg 等词典分词器 → 纯滑动二元组 + 长度提升
- ✗ 第三方依赖可用（requests, httpx 等） → 纯标准库 urllib
- ✗ 前端直接调 OpenAI API → 走后端 /api/chat 代理
- ✗ models 配置在环境变量里 → 在 DB 的 kv 表 conf 字段里
- ✗ /api/chat 支持流式 → 不支持，一次性返回
- ✗ 量词在头和尾的处理是对称的 → 头砍尾不砍，且只在左边有数词时砍
- ✗ ENT_HEAD_BAN 和 ENT_TAIL_BAN 内容一样 → 头禁远大于尾禁（`理由` `功能` 结尾）
- ✗ ESM import() 接受 Windows 路径 → Node v24 要求 file:// URL

## 内部结构

| 文件 | 行 | 职责 |
|---|--:|---|
| text.py | 180 | 分词：滑动二元组、长度提升、停用词、字符集 |
| entity.py | 145 | 跨语料实体归并：计数→边界清洗→凝固度→最大化 |
| terms.py | 80 | TF-IDF + 维度权重，top-24 |
| graph.py | 178 | 二部图：共现 NPMI、余弦相似、桥打分、Dijkstra |
| db.py | 40 | SQLite 连接、schema、kv 存取 |
| store.py | 100 | 想法 CRUD、状态读写、rebuild |
| jsonl.py | 309 | 导出格式 v3（与 yangdata.js 同构） |
| chat.py | 63 | OpenAI 兼容端点代理 |
| api.py | 134 | HTTP 路由：13 端点 |
| server.py | 98 | ThreadingHTTPServer + 静态文件 |
| demo.py | 86 | 演示语料（12 篇） |
| cli.py | 109 | CLI 入口 |
| __init__.py | 2 | 包标识 + 版本号 |
| __main__.py | 3 | `python -m yang` 入口 |

## 依赖

- **上游**（我用谁）：无（纯标准库）
- **下游**（谁用我）：`web/src/` 通过 HTTP API 调用
- **红线耦合**：
  - jsonl.py ↔ yangdata.js（同构实现）
  - api.py 路由 ↔ 03_api.js 对应方法
  - text.py 字符集 ↔ test_text.py + test_entity.py

## 生命周期

| 日期 | 事件 | changelog |
|---|---|---|
| 2026-09-09 | 初建、entity.py 新建 | changelog/2026-09-09_entity-layer.md |
| 2026-09-11 | chat.py + /api/chat | changelog/2026-09-11_llm-chat-proxy.md |
