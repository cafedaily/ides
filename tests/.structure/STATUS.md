# 测试 (`tests/`) 状态

> 最后更新：2026-09-11

## 是什么

94 条测试，覆盖后端全部模块。用自写的零依赖跑测器 `run.py`，也兼容 pytest。

## 边界

**做什么**：
- 单元测试：分词、实体、TF-IDF
- 集成测试：图谱计算、HTTP API（起临时 server）
- 跨语言对照：Python 写的 JSONL ↔ Node.js 读的 JSONL，互读互验

**不做什么**：
- 不测前端（没有 headless browser）
- 不测 chat.py 的实际 LLM 调用（没有 mock server）
- 不测性能/负载

## 当前真相

- [ ] `python tests/run.py` → 94 pass, 0 fail, 0 skip
- [ ] 跨语言测试需要 Node.js（已全局安装 v24.21.0）
- [ ] ESM `import()` 用 `pathlib.Path(JS).as_uri()` 适配 Windows
- [ ] run.py 输出 GBK 安全（Unicode 标记降级到 ASCII）
- [ ] test_api.py 自动起 server 在随机端口，测完关

## 不要假设

- ✗ 需要安装 pytest → run.py 是零依赖的，直接 `python tests/run.py`
- ✗ 跨语言测试在没 Node 时会报错 → 会跳过（SkipTest）
- ✗ test_api.py 连固定端口 → 随机端口
- ✗ 测试数据来自文件 → 来自 demo.py 的内存语料
- ✗ 可以 mock 数据库 → 用真实 SQLite（in-memory 或 tempfile）

## 内部结构

| 文件 | 行 | 覆盖 | 条数 |
|---|--:|---|--:|
| run.py | 104 | 跑测器 | — |
| test_text.py | 62 | 分词、停用词、量词规则 | 14 |
| test_entity.py | 115 | 实体发现、边界修剪、凝固度 | 20 |
| test_terms.py | 57 | TF-IDF、维度权重 | 10 |
| test_graph.py | 94 | 桥、相似、路径、共现 | 14 |
| test_jsonl.py | 156 | 签名、篡改检测、跨语言 | 20 |
| test_api.py | 150 | HTTP 路由、导入导出、路径遍历 | 16 |

## 依赖

- **上游**（我用谁）：`yang/` 全部模块、Node.js（跨语言测试）
- **下游**（谁用我）：CI（暂无）、开发者手动跑
- **红线耦合**：
  - demo.py 语料变 → 多条测试的硬编码断言会挂
  - text.py 字符集变 → test_text.py + test_entity.py 可能挂

## 生命周期

| 日期 | 事件 | changelog |
|---|---|---|
| 2026-09-09 | 初建、test_entity.py 新建 | changelog/2026-09-09_entity-layer.md |
| 2026-09-11 | test_jsonl.py ESM file:// 修复 | changelog/2026-09-11_llm-chat-proxy.md |
