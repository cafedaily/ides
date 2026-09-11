# .structure/ — 项目全局状态索引

> 给下一个读代码的人（包括未来的自己和 AI）一份地图。
> 代码会变，这里只写**不容易从代码本身读出来的东西**：
> 为什么这么做、什么和什么耦合、现在的状态是什么。

## 入口

| 文件 | 读者 | 内容 |
|---|---|---|
| [STRUCTURE.md](STRUCTURE.md) | **人** | 开发指导手册：怎么用、怎么维护 .structure/ |
| [AGENT.md](AGENT.md) | **AI** | 智能体协议：身份、边界、模块锁、行为规则 |

## 项目状态

| 文件 | 内容 |
|---|---|
| [tree.md](tree.md) | 模块树 + 状态标记（项目全貌） |
| [overview.md](overview.md) | 项目是什么、数字、技术栈选择 |
| [files.md](files.md) | 全部源文件清单：行数、职责、依赖关系 |
| [dataflow.md](dataflow.md) | 文本→词条→图谱、前后端同步、LLM 调用链、导出格式 |
| [coupling.md](coupling.md) | 必须一起改的地方（红线/黄线）、字符集不对称性 |
| [api.md](api.md) | 全部 HTTP 接口：方法、路径、参数、响应 |
| [debts.md](debts.md) | 已知欠账（带「怎么还」）、已解决的、不打算做的 |
| [tests.md](tests.md) | 测试状态、各模块覆盖、跨语言对照 |

## 子模块状态

| 模块 | STATUS.md | 职责 |
|---|---|---|
| 后端 | [yang/.structure/STATUS.md](../yang/.structure/STATUS.md) | 算法、存储、HTTP、LLM 代理 |
| 前端 | [web/.structure/STATUS.md](../web/.structure/STATUS.md) | UI、离线存储、智能体调用 |
| 测试 | [tests/.structure/STATUS.md](../tests/.structure/STATUS.md) | 94 条测试、跨语言对照 |

## 变更日志

| 日期 | 文件 | 摘要 |
|---|---|---|
| 2026-09-09 | [entity-layer](changelog/2026-09-09_entity-layer.md) | 跨语料实体归并 |
| 2026-09-11 | [llm-chat-proxy](changelog/2026-09-11_llm-chat-proxy.md) | LLM 接入 + 运行时安装 |
