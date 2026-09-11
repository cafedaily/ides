# LLM 接入 + 全局安装运行时

- **日期**: 2026-09-11
- **会话**: 1ac2b9d9（续）
- **触发**: 用户要求全局安装 Python/Node 正式版，之后要求按钮问题走 LLM

## 做了什么

### 全局安装运行时
- 下载并安装 Python 3.14.7（python.org amd64.exe，InstallAllUsers=1 PrependPath=1）
- 下载并安装 Node.js v24.21.0 LTS（nodejs.org MSI）
- 修了 `tests/test_jsonl.py`：Node v24 Windows 上 ESM `import()` 需要 `file://` URL，
  用 `pathlib.Path(JS).as_uri()` 转换

### LLM 后端代理
- 新建 `yang/chat.py`（63 行）：从 DB 读 conf.models[0]，urllib 转发到 OpenAI
  兼容的 /v1/chat/completions
- 改了 `yang/api.py`：加 `POST /api/chat` 路由
- 改了 `web/src/04_agent.js`：`_initAI()` 在 window.claude 不可用时，
  创建通过 `/api/chat` 调模型的 AI 对象

### 文档
- 更新 README.md：目录加 chat.py、接口表加 /api/chat、前后端配合加 LLM 段落、
  欠账删旧 #7（已解决）换新 #7 #8

## git 提交

未提交（无 git 仓库）。

## 测试

改动前：92 pass / 0 fail / 2 skip
改动后：94 pass / 0 fail / 0 skip

## 影响了哪些模块

- 后端/接口: 🆕 chat.py，api.py 加路由
- 前端/智能体: 🔧 _initAI() 接入后端代理
- 测试/跨语言: ✅ 从 skip 变 pass
- 运行环境: Python + Node 全局安装

## 遗留

- `/api/chat` 不流式 → debts.md #7
- 只用 models[0] 不看 conf.route → debts.md #8
