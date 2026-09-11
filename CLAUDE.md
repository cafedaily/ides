# CLAUDE.md — Claude Code 项目指令

## .structure/ 协议

本项目使用 `.structure/` 管理 AI 开发状态。启动时必读：

1. `.structure/state.json` → 当前阶段
2. `.structure/tree.md` → 模块地图
3. `.structure/tasks/BACKLOG.md` → 待做任务
4. `.structure/changelog/` 最新一条 → 上次做到哪

完整契约见 `.structure/AGENT.md`。

## 硬规则

- **一模块一锁**：写代码前先在 STATUS.md 写入 LOCK 章节
- **完成必更新**：代码和 `.structure/` 在同一个 commit
- **防幻觉**：改代码前读目标模块的 STATUS.md → 「不要假设」
- **不要全读 .structure/**：只读你需要的那个模块

## 技术栈

- Python 后端（纯标准库，无第三方依赖）
- 原生 JS 前端（无 npm，文件拼接构建）
- SQLite 存储
- 94 条测试，`python tests/run.py` 全过

## 常用命令

```bash
python tests/run.py          # 跑测试
python web/build.py          # 构建前端
python -m yang serve         # 启动服务
python -m yang demo          # 加载演示语料
```

## 红线耦合

改 `yang/jsonl.py` 必须同步改 `web/src/yangdata.js`（同构实现）。
验证：`python tests/run.py`（跨语言对照测试会抓住不同步）。
