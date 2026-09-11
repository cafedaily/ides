# 跨语料实体归并

- **日期**: 2026-09-09
- **会话**: 1ac2b9d9
- **触发**: 用户要求迁移工作并继续构建，选择了「实体消歧（欠账 #1）」

## 做了什么

- 新建 `yang/entity.py`（145 行）：跨语料 n-gram 计数 → 边界清洗 → 凝固度 → 最大化
- 改了 `yang/text.py`：加入 DET/MEASURE/ENT_HEAD_BAN/ENT_TAIL_BAN 字符集、
  `runs_of()`、实体感知的 `candidates()`
- 改了 `yang/terms.py`：调用 entity.discover() 再传给 candidates()
- 新建 `tests/test_entity.py`（20 条测试）
- 追加 `tests/test_text.py` 2 条量词规则测试
- 改了 `tests/test_jsonl.py`：跳过时 raise SkipTest 而不是 return
- 改了 `tests/run.py`：GBK 降级、skip 计数分离
- 改了 `web/build.py`：`newline="\n"` 跨平台
- 重写了 README.md 的实体归并章节和欠账清单
- 安装了便携版 Python 3.12 到临时目录（已被全局安装替代）

## git 提交

未提交（无 git 仓库）。

## 测试

改动前：无法运行（没有 Python）
改动后：92 pass / 0 fail / 2 skip（跳过的是跨语言对照，没有 node）

## 影响了哪些模块

- 后端/核心算法: 🆕 entity.py，text.py 大改
- 后端/接口: terms.py 集成 entity
- 测试/单元: 新增 test_entity.py
- 构建: run.py 改了报告格式

## 关键决策

1. **凝固度而不是邻接熵**：小语料（几十篇）上熵估不准，凝固度只要两个计数
2. **量词只砍头不砍尾**：`一个定期见面` 的 `个` 该砍，`下雨天开门` 的 `门` 不能砍
3. **头禁字集远大于尾禁字集**：`理由` `机会` `功能` 都以介词字结尾
4. **左邻从语料查**：`一个定期见面的理由` 有 9 字超过 MAX_LEN=8，`一` 在窗口外
