# 前端 (`web/`) 状态

> 最后更新：2026-09-11

## 是什么

单文件 Web 前端。`build.py` 把 `src/` 下的 JS/CSS/HTML 拼成一个 `index.html`。
没有 npm、没有框架、没有构建工具——所有 JS 共享全局作用域，按文件名序号加载。

## 边界

**做什么**：
- 渲染今天页、想法详情页、数据页、图谱页
- IndexedDB 离线持久化
- 后端探测 + fetch 封装
- LLM 智能体（追问、换角度、碰一下、分叉、起名、推荐）
- JSONL 导出导入（前端侧校验）
- 模型配置 UI

**不做什么**：
- 不做分词/TF-IDF/图谱计算——这些在后端
- 不直接调 OpenAI API——通过 `/api/chat` 走后端代理
- 不做路由框架——`09_boot.js` 手写的 hash 路由
- 不做服务端渲染——纯客户端

## 当前真相

- [ ] `python web/build.py` → 生成 `web/index.html`，无报错
- [ ] 所有 JS 通过全局变量通信（S, API, AI, render 等）
- [ ] `04_agent.js` 的 `_initAI()` 依次尝试：window.claude → 后端 /api/chat → 内置题库
- [ ] 后端在线时按钮显示 `追问 · {model}`，不在线显示 `追问 · 题库`
- [ ] 模型配置存在后端 DB 的 `kv` 表 `conf` 字段里，不在 localStorage
- [ ] 拼接顺序 = 加载顺序 = 文件名的数字前缀顺序
- [ ] yangdata.js 不参与数字排序，在最前面加载

## 不要假设

- ✗ 用了 React/Vue/Svelte 等框架 → 纯原生 JS，全局作用域
- ✗ 有 npm/node_modules/package.json → 没有，零依赖
- ✗ build.py 是 webpack/vite → 是字符串拼接（读文件 + 合并）
- ✗ AI 对象来自 window.claude → 独立运行时来自后端代理 `/api/chat`
- ✗ 模型配置在 localStorage → 在后端 DB
- ✗ 每个 JS 文件是独立模块 → 共享全局作用域，顺序敏感
- ✗ 可以随意改文件名 → 文件名数字前缀决定加载顺序

## 内部结构

| 文件 | 行 | 职责 |
|---|--:|---|
| yangdata.js | 279 | 导出格式（与 jsonl.py 同构） |
| 01_state.js | 136 | 全局状态 S、工具函数、语音输入 |
| 02_db.js | 53 | IndexedDB 持久化 |
| 03_api.js | 59 | 后端探测 + fetch + 防抖推送 |
| 04_agent.js | 192 | LLM 智能体 |
| 05_today.js | 259 | 今天页 |
| 06_idea.js | 254 | 想法详情页 |
| 07_data.js | 290 | 数据页（导出导入、模型配置） |
| graph_view.js | 232 | 图谱页 |
| 09_boot.js | 141 | 启动：路由、导航、渲染 |
| body.html | 15 | HTML 骨架 |
| app.css | 185 | 主样式 |
| extra.css | 73 | 补充样式 |
| graph.css | 35 | 图谱页样式 |

## 依赖

- **上游**（我用谁）：后端 HTTP API（`/api/*`）
- **下游**（谁用我）：用户浏览器
- **红线耦合**：
  - yangdata.js ↔ jsonl.py（同构实现）
  - 03_api.js ↔ api.py 路由

## 生命周期

| 日期 | 事件 | changelog |
|---|---|---|
| 2026-09-09 | 初建 | changelog/2026-09-09_entity-layer.md |
| 2026-09-11 | 04_agent.js 接入后端 LLM 代理 | changelog/2026-09-11_llm-chat-proxy.md |
