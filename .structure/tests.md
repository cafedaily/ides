# 测试状态

> 最后运行：2026-09-11 — **94 通过，0 失败，0 跳过**

## 运行

```bash
python tests/run.py           # 零依赖跑测器
pytest tests/ -q              # 或用 pytest，同一组测试
make test                     # Makefile 快捷方式（需要 make）
```

## 各模块覆盖

| 模块 | 测试文件 | 条数 | 覆盖要点 |
|---|---|--:|---|
| text.py | test_text.py | 14 | 二元组对齐、长度提升、功能词过滤、量词规则（有/无数词）、Latin、空输入 |
| entity.py | test_entity.py | 20 | 实体发现（演示语料验证）、头尾修剪不对称、凝固度门槛、句子拒绝、候选匹配、空/纯英文语料 |
| terms.py | test_terms.py | 10 | 每篇有词、权重归一、排序、维度记录、df、标题加权、噪声保留、空文档、top-N |
| graph.py | test_graph.py | 14 | 桥（活↔死、spark↔死、跨维度加成）、证据、碰一下、相似对称、路径、NPMI、空语料 |
| jsonl.py | test_jsonl.py | 20 | 明文往返、加密、篡改检测（单字符/删行/重算）、格式校验、跨语言对照（Python↔JS） |
| api.py | test_api.py | 16 | 全部 HTTP 路由、合并/替换、校验拒绝、路径遍历防护 |

## 跨语言对照

`test_jsonl.py` 的最后两条测试是导出格式的**唯一跨语言防线**：
- Python 写 → Node 读 ✓
- Node 写 → Python 读 ✓

它们会起一个真的 `node` 进程。Windows + Node v24 需要 ESM `import()` 用
`file://` URL（`pathlib.Path(JS).as_uri()`），裸 `D:\...` 路径会报
`ERR_UNSUPPORTED_ESM_URL_SCHEME`。

## 跑测器特性（`tests/run.py`）

- 零第三方依赖，pytest 也能跑
- 支持 `tmp_path` fixture
- 跳过用 `raise unittest.SkipTest("原因")`
- 跳过和通过分开报，不混进通过数
- GBK 控制台自动降级：`✓` → `+`，`✗` → `x`，`⊘` → `-`
