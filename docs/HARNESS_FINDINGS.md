# Harness 0.2.1 实际项目测试发现

## 已确认

- 发布 tarball 可独立安装，项目及模块身份正确。
- 基线测试：项目 94 项；harness 43 项 Python 通过、1 项符号链接跳过、16 项 Node 通过；共享核心 31 项 Python 与 7 项 Node 通过。
- 真实 gpt-5.5 开发调用已完成 T-002：父 Agent、worker、接纳、两项验证、模块同步和任务完成均有持久记录。

## HARNESS-001：提交阶段误用了运行时限制

multi-agent profile 下，即使声明了变更影响并暂存知识更新，0.2.1 的 pre-commit 仍要求运行中的 work_item；提供已经完成的 work_item 又会因 done 状态被拒绝。这与“先验证并完成任务，再提交代码”的正常流程冲突。

已在 Agent 仓库的共享核心中修正：只有实际 runtime 操作要求活跃工作项；staged review 可以检查 done 工作项，并继续执行影响、scope、coupling 和知识更新检查。两项回归已通过，实际项目提交已在修正后的 hook 下成功。没有使用 --no-verify。

应用开发运行时和已安装 npm 包仍为原始 0.2.1；项目的提交 hook 使用修正后的本地共享核心。这是实际案例发现的兼容修复，应在关联案例时一并发布到 Agent 仓库。
