# .structure/ 协议（Cline 适配）

本项目使用 `.structure/` 管理 AI 开发状态。
完整契约见 `.structure/AGENT.md`。

## 启动时

1. 读 `.structure/state.json`
2. 读 `.structure/tree.md`
3. 读要改的模块的 `{module}/.structure/STATUS.md`

## 规则

- 一模块一锁，无锁不写
- 完成必更新：changelog + tree.md + STATUS.md + 释放锁
- 和代码同 commit
- 改代码前读 STATUS.md 的「不要假设」

## 模块权限

见 `.structure/manifest.yaml`。每个模块有 `write_scope` 和 `forbidden`。
