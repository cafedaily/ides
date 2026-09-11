# AGENTS.md — AI Coding Agent 入口

> 工具无关。所有 coding agent 都从这里开始。

本仓库使用 `.structure/` 机制管理 AI 开发状态。

## 启动前必读

| 文件 | 内容 |
|---|---|
| `.structure/AGENT.md` | 智能体契约（完整版） |
| `.structure/state.json` | 当前阶段、最近门禁 |
| `.structure/tree.md` | 模块地图 |
| `.structure/human-gates/` 最近 3 条 | 人类最新意图 |

## 关键约束（硬规则）

1. **一模块一锁，无锁不写** — 获取锁见 `acquire_lock.py`
2. **执行完成必须更新 `.structure/`** — changelog + tree.md + STATUS.md + 释放锁
3. **渐进式披露** — 只读你需要的模块的 STATUS.md，不要全读
4. **阶段即护栏** — `state.json.phase` 决定你能做什么
5. **未记录的门禁 = 未批准** — 不得基于口头批准推进
6. **防幻觉** — 改代码前读 STATUS.md 的「不要假设」章节

## 模块权限

见 `.structure/manifest.yaml`。每个模块定义了 `write_scope` 和 `forbidden`。
你只能修改你持有锁的模块的 `write_scope` 内的文件。

## 按工具加载

| 工具 | 入口文件 | 备注 |
|---|---|---|
| Claude Code | `CLAUDE.md` | `@` 导入 `.structure/AGENT.md` |
| Cursor | `.cursor/rules/structure.mdc` | `alwaysApply: true` |
| Aider | `.aider.conf.yml` | `read:` 指定 |
| Cline | `.clinerules/structure.md` | 项目级规则 |
| OpenHands | `.openhands/microagents/repo.md` | Skills 触发 |
| Copilot | `.github/copilot-instructions.md` | 精简版约束 |

## MCP 集成

```bash
claude mcp add structure-keeper -- python .structure/scripts/mcp_server.py
```

提供工具：`get_phase`, `get_module_context`, `acquire_lock`, `release_lock`,
`record_gate`, `advance_phase`, `verify_structure`。
