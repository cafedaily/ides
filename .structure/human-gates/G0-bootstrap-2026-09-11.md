# Gate G0 — Bootstrap Existing Project

- **Gate**: G0-bootstrap
- **Timestamp**: 2026-09-11T00:00:00+08:00
- **Human**: @oomg9258
- **Decision**: APPROVED
- **Scope**: 全项目 — 已有代码库引入 .structure/ v1.1 harness

## Rationale

项目已有完整的后端、前端、测试，94 条测试全过。
直接从 PHASE_0 跳到 PHASE_4_IMPLEMENTATION，跳过 P1-P3
是因为架构已经由实际代码确定，不需要重新设计。

## 跳过的门禁

- G1 (需求冻结): 需求已由代码实现确认
- G2 (架构批准): 架构已稳定运行
- G3 (模块树批准): 模块树从代码目录结构推导
- G4..Gn (模块能力确认): 各模块已有 STATUS.md

## 先决条件

- [x] 测试全过 (94 pass, 0 fail, 0 skip)
- [x] 模块树已建 (tree.md)
- [x] 子模块 STATUS.md 已建 (yang/, web/, tests/)
- [x] 欠账已记录 (debts.md)
- [x] 耦合关系已记录 (coupling.md)

## Resulting State Change

- state.json.phase: PHASE_0_EMPTY → PHASE_4_IMPLEMENTATION (bootstrap skip)
- manifest.yaml: 从 tree.md 推导写入
- bootstrap: true (标记为已有项目引导，非正常阶段流转)
