# 耦合关系：必须一起改的地方

## 红线：改一处就必须同时改另一处

| 改这个 | 就必须同时改 | 验证方式 |
|---|---|---|
| `yang/jsonl.py` | `web/src/yangdata.js` | `test_jsonl.py` 跨语言对照（Python↔JS 互读） |
| `yang/text.py` 字符集 | `tests/test_text.py` + `tests/test_entity.py` | `make test` |
| `yang/entity.py` 判据 | `tests/test_entity.py` | `make test` |
| `yang/api.py` 路由 | `web/src/03_api.js` 对应方法 | `test_api.py` |
| `yang/api.py` 新增路由 | `ROUTES` 字典 | 不在 ROUTES 里就 404 |

## 黄线：改了最好一起检查

| 改这个 | 检查 | 原因 |
|---|---|---|
| `yang/terms.py` 权重/top-N | 图谱上的桥和相似 | 权重变 → 桥排序变 |
| `yang/graph.py` 桥打分公式 | `test_graph.py` | 打分变 → 排序变 → 断言可能挂 |
| `web/src/04_agent.js` prompt | LLM 输出质量 | prompt 变 → 回答风格变 |
| `web/src/01_state.js` S 结构 | `02_db.js` 的 IndexedDB 读写 | 字段不一致会丢数据 |
| `yang/demo.py` 语料 | 多条测试的硬编码断言 | 语料变 → 桥/词条/实体结果变 |

## 字符集（`yang/text.py` 顶部）

以下集合是**闭合词类的穷举**，改动频率低但影响面大：

| 集合 | 用途 | 不对称性 |
|---|---|---|
| `STOP2` | 两字都是功能词 → 整个二元组丢掉 | — |
| `NO_HEAD` / `NO_TAIL` | 二元组头/尾虚词 | 头禁 ⊃ 尾禁 |
| `DET` | 数词/指示词（量词规则的触发条件） | — |
| `MEASURE` | 量词 | 只砍实体头不砍尾 |
| `ENT_HEAD_BAN` | 实体头部禁字（介词、副词、连词） | 远大于尾禁 |
| `ENT_TAIL_BAN` | 实体尾部禁字（介词、方位词） | 远小于头禁 |
| `LOC` | 方位词（`里中内外处`） | — |

不对称性的原因：`理由` `机会` `功能` `数据` 都以介词字结尾（`由` `会` `能` `据`），
所以尾禁不能照搬头禁。详见 `tests/test_entity.py` 的边界测试。
