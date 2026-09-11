# .structure/ — 项目状态索引

> 代码会变，这里只写**不容易从代码本身读出来的东西**。

## 入口

| 文件 | 读者 | 内容 |
|---|---|---|
| [STRUCTURE.md](STRUCTURE.md) | **人** | 开发指导手册 v1.1 |
| [AGENT.md](AGENT.md) | **AI** | 智能体契约（系统提示词） |
| [AGENTS.md](../AGENTS.md) | **所有 AI 工具** | 工具无关的入口指针 |

## 运行时状态

| 文件 | 内容 |
|---|---|
| [state.json](state.json) | 当前阶段、最近门禁 |
| [manifest.yaml](manifest.yaml) | 模块树 + 权限 + 耦合 |
| [tree.md](tree.md) | 模块地图（一屏全貌） |

## 项目知识

| 文件 | 内容 |
|---|---|
| [overview.md](overview.md) | 项目概况、数字、技术栈 |
| [files.md](files.md) | 文件清单：行数、职责、依赖 |
| [dataflow.md](dataflow.md) | 端到端数据流 |
| [coupling.md](coupling.md) | 耦合关系（红线/黄线） |
| [api.md](api.md) | HTTP 接口 |
| [debts.md](debts.md) | 已知欠账 |
| [tests.md](tests.md) | 测试状态 |

## 流程

| 目录 | 内容 |
|---|---|
| [human-gates/](human-gates/) | 人工介入日志（门禁记录） |
| [phases/](phases/) | 阶段跃迁记录 |
| [changelog/](changelog/) | 变更日志 |
| [tasks/](tasks/) | 任务队列 |

## 子模块

| 模块 | STATUS.md | 职责 |
|---|---|---|
| 后端 | [yang/.structure/STATUS.md](../yang/.structure/STATUS.md) | 算法、存储、HTTP、LLM 代理 |
| 前端 | [web/.structure/STATUS.md](../web/.structure/STATUS.md) | UI、离线存储、智能体调用 |
| 测试 | [tests/.structure/STATUS.md](../tests/.structure/STATUS.md) | 94 条测试、跨语言对照 |

## 自动化脚本

| 脚本 | 用途 |
|---|---|
| `scripts/init_from_existing.py` | 已有项目全景分析 |
| `scripts/advance_phase.py` | 阶段跃迁 |
| `scripts/record_gate.py` | 记录人工门禁 |
| `scripts/scaffold_modules.py` | 生成子模块骨架 |
| `scripts/verify_structure.py` | 校验完整性 |
| `scripts/acquire_lock.py` | 模块锁管理 |
| `scripts/render_context.py` | 上下文拼装 |
| `scripts/mcp_server.py` | MCP 服务器 |
| `scripts/pre_commit_hook.py` | Git pre-commit 钩子 |
