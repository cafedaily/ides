# 文件清单

> 每个文件一行：路径、行数、职责、依赖谁、被谁依赖。

## Python 后端 (`yang/`)

| 文件 | 行 | 职责 | 依赖 | 被依赖 |
|---|--:|---|---|---|
| `text.py` | 180 | 分词：滑动二元组、长度提升、停用词、词边界规则、字符集 | — | entity, terms |
| `entity.py` | 145 | 跨语料实体归并：计数→边界清洗→凝固度→最大化 | text | terms |
| `terms.py` | 80 | TF-IDF + 维度权重，每篇留 top-24 | text, entity | graph, api, store |
| `graph.py` | 178 | 二部图：共现 NPMI、余弦相似、桥打分、Dijkstra 路径 | terms | store, api |
| `db.py` | 40 | SQLite 连接、schema、kv 存取 | — | store, api, chat |
| `store.py` | 100 | 想法 CRUD、状态读写、拆片段、rebuild | db, graph, terms | api |
| `jsonl.py` | 309 | 导出格式 v3：逐行签名、加密、校验（与 yangdata.js 同构） | — | api, store |
| `chat.py` | 63 | OpenAI 兼容端点代理：读模型配置、转发、返回 | db | api |
| `api.py` | 134 | HTTP 路由：13 个端点 | chat, db, jsonl, store, graph, terms | server |
| `server.py` | 98 | 标准库 ThreadingHTTPServer，静态文件 + API 分发 | api, db | cli |
| `demo.py` | 86 | 演示语料（12 篇，故意埋跨维度重合） | — | cli, tests |
| `cli.py` | 109 | 命令行入口：init/import/export/graph/bridges/path/serve | db, store, server, jsonl, demo | __main__ |
| `__init__.py` | 2 | 包标识 + 版本号 | — | — |
| `__main__.py` | 3 | `python -m yang` 入口 | cli | — |

## JS 前端 (`web/src/`)

拼接顺序即加载顺序，所有文件共享同一个全局作用域。

| 文件 | 行 | 职责 | 依赖 | 被依赖 |
|---|--:|---|---|---|
| `yangdata.js` | 279 | 导出格式（与 jsonl.py 同构）：签名、加密、校验 | — | 07_data |
| `01_state.js` | 136 | 全局状态 S、工具函数、语音输入 | — | 全部后续 |
| `02_db.js` | 53 | IndexedDB 持久化 | 01 | 05, 06, 07 |
| `03_api.js` | 59 | 后端探测 + fetch 封装 + 防抖推送 | — | 04, 05, 07 |
| `04_agent.js` | 192 | LLM 智能体：追问、换角度、碰一下、分叉、起名、推荐 | 01, 03 | 05, 06 |
| `05_today.js` | 259 | "今天动哪一个"首页 + 念头列表 | 01~04 | 09 |
| `06_idea.js` | 254 | 想法详情页：成长记录、操作面板 | 01~04 | 09 |
| `07_data.js` | 290 | 数据页：导出导入、模型配置、同步状态 | 01~03, yangdata | 09 |
| `graph_view.js` | 232 | 图谱页：桥列表、节点搜索 | 01, 03 | 09 |
| `09_boot.js` | 141 | 启动：路由、导航、渲染分发 | 01~07, graph_view | — |
| `body.html` | 15 | HTML 骨架 | — | build.py |
| `app.css` | 185 | 主样式 | — | build.py |
| `extra.css` | 73 | 补充样式 | — | build.py |
| `graph.css` | 35 | 图谱页样式 | — | build.py |

## 测试 (`tests/`)

| 文件 | 行 | 覆盖 | 条数 |
|---|--:|---|--:|
| `run.py` | 104 | 零依赖跑测器（也可用 pytest） | — |
| `test_text.py` | 62 | 分词、停用词、量词规则 | 14 |
| `test_entity.py` | 115 | 实体发现、边界修剪、凝固度、候选匹配 | 20 |
| `test_terms.py` | 57 | TF-IDF、维度权重、top-N | 10 |
| `test_graph.py` | 94 | 桥、相似、路径、共现、空语料 | 14 |
| `test_jsonl.py` | 156 | 签名、篡改检测、跨语言（Python↔JS） | 20 |
| `test_api.py` | 150 | HTTP 路由、导入导出、路径遍历 | 16 |

**合计：94 条，全过，0 跳过。**

## 构建与配置

| 文件 | 行 | 职责 |
|---|--:|---|
| `web/build.py` | 69 | 把 src/ 拼成单文件 index.html + 顶层重名检查 |
| `Makefile` | 27 | make test / web / demo / serve / graph / bridges |
| `pyproject.toml` | 20 | 包元数据、可选依赖、pytest 配置 |
| `README.md` | 202 | 项目文档 |

## 生成物（不入版本控制）

| 文件 | 来源 |
|---|---|
| `web/index.html` | `web/build.py` 从 src/ 拼出 |
| `yang.db` | 运行时 SQLite 数据库 |
| `**/__pycache__/` | Python 字节码缓存 |
