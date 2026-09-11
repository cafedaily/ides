# .structure/ 开发指导手册 v1.1

> 给团队成员和未来的自己。
> 智能体契约见 [AGENT.md](AGENT.md)。

---

## 目录

1. [设计原则](#1-设计原则)
2. [快速上手](#2-快速上手)
3. [项目阶段机](#3-项目阶段机)
4. [目录结构](#4-目录结构)
5. [从空目录开始](#5-从空目录开始)
6. [已有项目全景分析](#6-已有项目全景分析)
7. [子模块状态](#7-子模块状态)
8. [人工介入门禁](#8-人工介入门禁)
9. [模块锁](#9-模块锁)
10. [日常工作流](#10-日常工作流)
11. [变更日志](#11-变更日志)
12. [任务队列](#12-任务队列)
13. [多工具集成](#13-多工具集成)
14. [防止信息腐烂](#14-防止信息腐烂)
15. [FAQ](#15-faq)

---

## 1. 设计原则

1. **从空目录起步不丢人** — `.structure/` 支持零模块启动
2. **人工介入是常态** — 所有介入必须落盘到 `human-gates/`
3. **阶段即护栏** — 每个阶段有准入/退出条件和 owner
4. **门禁即合同** — 未记录 = 未批准
5. **模块后置生成** — 架构不清前不建子模块 `.structure/`
6. **渐进式披露** — tree.md 是目录，STATUS.md 是正文
7. **只写代码和 git 读不出来的东西**

---

## 2. 快速上手

### 第一次看这个项目？

```
1. .structure/state.json     → 什么阶段
2. .structure/tree.md        → 有哪些模块
3. .structure/debts.md       → 已知问题
4. .structure/coupling.md    → 不能单独改的地方
```

### 要改某个模块？

```
1. tree.md → 找到模块 → 看状态
2. {module}/.structure/STATUS.md → 边界、真相、不要假设
3. coupling.md → 连锁影响
4. 获取模块锁（PHASE_4+）
5. 开始改代码
```

### 改完之后？

```
1. 跑测试
2. 写 changelog
3. 更新 tree.md 状态标记
4. 更新 STATUS.md 当前真相
5. 释放模块锁
6. git add . && git commit
```

---

## 3. 项目阶段机

```
PHASE_0_EMPTY              空目录
   │  初始化
   ▼
PHASE_1_REQUIREMENTS       需求确认          ← 人类主导
   │  ⛔ G1: 需求冻结
   ▼
PHASE_2_ARCHITECTURE       架构设计          ← 人机协作
   │  ⛔ G2: 架构批准
   ▼
PHASE_3_MODULE_DESIGN      模块能力确认       ← 人机协作
   │  ⛔ G3: 模块树批准
   │  ⛔ G4..Gn: 每模块能力确认
   ▼
PHASE_4_IMPLEMENTATION     模块开发          ← 智能体自治（受锁约束）
   │
   ▼
PHASE_5_EVOLUTION          演化/扩展          ← 回到 P2 或 P3
```

### 阶段规则

- 只能**顺序推进**，不能跳级（bootstrap 除外）
- 每次跃迁由一个 **Gate 记录**固化
- 回退需要写 ADR + 门禁记录
- `state.json.phase` 是唯一的阶段真相源

### 项目形态适配

| 起始形态 | 路径 |
|---|---|
| 纯空目录 | P0 → P1 → P2 → P3 → P4 |
| 已有项目，无 .structure/ | 全景分析 → 直接 P4（bootstrap） |
| 已有 .structure/ v1.0 | 迁移：补 state.json，设为 P4 |
| 单模块小项目 | P1 → P2 → P3（1 模块）→ P4 |

---

## 4. 目录结构

```
project/
├── AGENTS.md                      工具无关的 AI 入口（指针）
├── CLAUDE.md                      Claude Code 入口
├── .cursor/rules/structure.mdc    Cursor 适配
├── .clinerules/structure.md       Cline 适配
├── .github/copilot-instructions.md  Copilot 适配
│
├── .structure/                    项目级状态
│   ├── AGENT.md                      智能体契约
│   ├── STRUCTURE.md                  本手册
│   ├── INDEX.md                      入口索引
│   ├── state.json                    阶段、门禁状态
│   ├── manifest.yaml                 模块树 + 权限 + 耦合
│   ├── tree.md                       模块地图
│   ├── overview.md                   项目概况
│   ├── files.md                      文件清单
│   ├── dataflow.md                   数据流
│   ├── coupling.md                   耦合关系
│   ├── api.md                        HTTP 接口
│   ├── debts.md                      已知欠账
│   ├── tests.md                      测试状态
│   ├── changelog/                    变更日志
│   ├── tasks/BACKLOG.md              任务队列
│   ├── human-gates/                  人工介入日志
│   │   ├── INDEX.md
│   │   └── G0-bootstrap-*.md
│   ├── phases/                       阶段跃迁记录
│   │   └── P0-to-P4-*.yaml
│   └── scripts/                      自动化脚本
│       ├── init_from_existing.py        全景分析
│       ├── advance_phase.py             阶段跃迁
│       ├── record_gate.py              记录门禁
│       ├── scaffold_modules.py          生成子模块骨架
│       ├── verify_structure.py          校验完整性
│       ├── acquire_lock.py              模块锁管理
│       ├── render_context.py            上下文拼装
│       ├── mcp_server.py               MCP 服务器
│       └── pre_commit_hook.py          Git 钩子
│
├── {module}/.structure/           子模块状态
│   └── STATUS.md
└── ...
```

---

## 5. 从空目录开始

### 方式一：交互式

```bash
mkdir my-project && cd my-project && git init
python .structure/scripts/init_from_existing.py  # 会检测为空目录
# 按提示走 P0 → P1
```

### 方式二：脚本

```bash
python .structure/scripts/advance_phase.py --to PHASE_1_REQUIREMENTS --bootstrap
```

然后与智能体对话，产出 `requirements/goals.md`、`constraints.md` 等。

---

## 6. 已有项目全景分析

**这是 .structure/ v1.1 最重要的新功能。**

```bash
python .structure/scripts/init_from_existing.py [项目根目录]
```

脚本会：
1. 扫描目录树，识别所有源文件
2. 按目录分组为候选模块
3. 分析 import/require 依赖
4. 统计行数、语言分布
5. 生成全套 `.structure/` 草稿

**所有生成的文件都是草稿**——需要人类审阅：

```
1. 审阅 manifest.yaml        → 模块划分合理吗？
2. 审阅每个 STATUS.md        → 补充边界、真相、假设
3. 决定初始阶段              → P4（成熟项目）或 P2（需重构）
4. 签批 G0                   → python .structure/scripts/record_gate.py --approve G0
5. git add .structure/ && git commit
```

---

## 7. 子模块状态

每个子模块的 `.structure/STATUS.md` 包含：

| 章节 | 内容 |
|---|---|
| 是什么 | 一两句话 |
| 边界 | 做什么 / **不做什么** |
| 当前真相 | 可执行的验证命令 |
| 不要假设 | 过去犯过的错 |
| 内部结构 | 文件列表 |
| 依赖 | 上下游 |
| 生命周期 | 关键事件时间线 |
| LOCK | 当前持锁者（临时章节） |

### 什么时候建新的 STATUS.md？

满足以下**任意两条**：
- 有独立生命周期
- 有清晰边界
- 代码量 > 500 行
- 有独立依赖关系

---

## 8. 人工介入门禁

### 为什么需要门禁？

智能体擅长执行，不擅长判断方向。门禁确保关键决策由人类做出。

### 门禁清单

| Gate | 什么时候 | 谁触发 |
|---|---|---|
| G1 | 需求定了 | 人类 |
| G2 | 架构定了 | 人类 |
| G3 | 模块树定了 | 人类 |
| G4..Gn | 每个模块边界定了 | 人类（逐个）|
| G5 | 下发具体任务 | 可选 |
| G6 | 跨模块大改 | 人类 |
| G7 | 合并到 main | 人类 |

### 记录门禁

```bash
# 审批
python .structure/scripts/record_gate.py --approve G2 --human alice@co.com --rationale "架构可行"

# 否决
python .structure/scripts/record_gate.py --reject G6 --rationale "方案不可行"
```

### 查看所有门禁

```bash
cat .structure/human-gates/INDEX.md
```

---

## 9. 模块锁

**PHASE_4+ 生效。一个模块只能有一个活跃智能体。**

```bash
# 获取
python .structure/scripts/acquire_lock.py --module backend --session abc12345 --task "加流式"

# 释放
python .structure/scripts/acquire_lock.py --release backend

# 查看
python .structure/scripts/acquire_lock.py --status

# 清理遗弃锁（>4h）
python .structure/scripts/acquire_lock.py --cleanup
```

---

## 10. 日常工作流

### 开始

```bash
cat .structure/state.json                # 什么阶段
cat .structure/tasks/BACKLOG.md          # 该做什么
ls .structure/changelog/ | tail -1       # 上次做到哪
python .structure/scripts/acquire_lock.py --status  # 有没有锁
```

### 做完

```bash
python tests/run.py                      # 跑测试
# 写 changelog、更新 tree.md、更新 STATUS.md
# 释放锁
git add . && git commit
```

---

## 11. 变更日志

文件：`.structure/changelog/YYYY-MM-DD_{slug}.md`

内容：做了什么、测试状态、模块状态变更、遗留。
规则：一轮一条、只写结果、和代码同 commit。

---

## 12. 任务队列

文件：`.structure/tasks/BACKLOG.md`

优先级：P0 阻塞 → P1 体验/安全 → P2 正常迭代 → P3 有空再说。

---

## 13. 多工具集成

### 三层架构

| 层 | 机制 | 作用 |
|---|---|---|
| **契约层** | AGENTS.md / CLAUDE.md / .mdc / .clinerules | 加载契约 |
| **注入层** | Hooks（SessionStart / UserPromptSubmit） | 按 phase 动态注入上下文 |
| **操作层** | MCP Server（structure-keeper） | 锁/gate/phase 工具化操作 |

### MCP 注册

```bash
# Claude Code
claude mcp add structure-keeper -- python .structure/scripts/mcp_server.py

# Cursor: 在 mcp.json 中添加
```

### Pre-commit Hook 安装

```bash
python .structure/scripts/pre_commit_hook.py --install
```

自动校验：state.json 合法、代码有对应 .structure/ 更新、阶段护栏。

### 工具入口文件

| 工具 | 文件 |
|---|---|
| Claude Code | `CLAUDE.md` |
| Cursor | `.cursor/rules/structure.mdc` |
| Cline | `.clinerules/structure.md` |
| Copilot | `.github/copilot-instructions.md` |
| Aider | `.aider.conf.yml` 中 `read: [.structure/AGENT.md]` |
| 通用 | `AGENTS.md`（根目录指针） |

---

## 14. 防止信息腐烂

### 防线

1. **和代码同 commit**
2. **可验证断言**（STATUS.md 当前真相可以跑）
3. **不写代码能读出来的东西**
4. **Pre-commit hook 强制校验**
5. **changelog 只增不改**

### 腐烂信号

- tree.md 的「上次变更」和 git log 不一致
- STATUS.md 的「当前真相」跑不过
- 超过三轮对话没有新 changelog

---

## 15. FAQ

### Q: 和 v1.0 有什么区别？

| | v1.0 | v1.1 |
|---|---|---|
| 起始 | 假定已有模块 | 支持空目录 |
| 阶段 | 无 | 6 阶段状态机 |
| 人类介入 | 隐含 | HITL Gates 显式化 |
| 模块生成 | 初始化即生成 | P3 后 scaffold |
| 工具集成 | 无 | AGENTS.md + MCP + Hooks |
| 校验 | 无 | Pre-commit hook + verify |

### Q: 已有项目怎么引入？

```bash
python .structure/scripts/init_from_existing.py
```

### Q: 多个 AI 工具能共存吗？

能。AGENTS.md 是通用入口，各工具读自己的适配文件。
MCP server 是通用的操作层，Claude Code 和 Cursor 都支持。

### Q: 门禁太重了？

G5（任务下发）是可选的。小项目可以只用 G0（bootstrap）+ G7（合并）。

---

## 版本

- v1.0: 模块树 + 锁 + 渐进披露
- **v1.1: 阶段机 + HITL + 全景分析 + 多工具集成 + MCP（当前）**
