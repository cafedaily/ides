# 数据流

## 文本 → 词条 → 图谱

```
原始文本（想法的各个片段，按维度分）
    │
    ▼
text.py: runs_of()
    │  汉字连续段（标点断开）
    ▼
entity.py: discover()          ← 扫全语料一次
    │  跨语料 n-gram 计数
    │  → 出现够多 → 边界干净 → 凝固度 → 最大化
    │  输出：实体集合（如 {"定期见面的理由", "下雨天开门"}）
    ▼
text.py: candidates()          ← 逐段
    │  先匹配实体（最长优先），再对剩余部分做滑动二元组
    │  → 长度提升（二元→三元→四元）
    │  → 停用词/虚词/量词规则过滤
    │  输出：[{term, dims, evidence}]
    ▼
terms.py: extract()
    │  TF-IDF（文档=一个想法的所有片段）
    │  维度权重（title 1.7×, now 1.35×, …）
    │  每篇留 top-24
    │  输出：{doc_id: [{term, w, tf, df, dims}]}
    ▼
graph.py: build()
    │  二部图 idea↔term
    │  共现 NPMI（term↔term）
    │  余弦相似（idea↔idea，每个最多 6 条）
    │  桥打分（跨维度 1.35×，why 1.7×）
    │  输出：{nodes, edges, sim, cooc, bridges, terms}
    ▼
store.py: rebuild()
    │  写入 doc_terms 表 + 更新 graph_at
    ▼
api.py → server.py → 前端
```

## 前端 ↔ 后端同步

```
浏览器 IndexedDB (S)                    SQLite (yang.db)
    │                                       │
    │  启动时 GET /api/health               │
    │  ───────────────────────────►          │
    │                                       │
    │  如果后端在：                          │
    │  GET /api/state                       │
    │  ◄───────────────────────────         │
    │  浏览器只有种子 → 直接替换            │
    │  已有自己的数据 → 按 id 合并          │
    │                                       │
    │  每次 save() 防抖 900ms：             │
    │  POST /api/state?mode=merge           │
    │  ───────────────────────────►          │
    │  推全量（ideas + sparks + cold + conf）│
    │                                       │
    │  后端不在 → 纯本地模式，无影响        │
```

## LLM 调用链

```
用户点「追问我」/「换角度」/「碰一下」/「分叉」
    │
    ▼
04_agent.js: say(prompt)
    │  AI 对象来自：
    │  1. window.claude.use("sample")（Claude 嵌入式）
    │  2. API._post("/api/chat", {messages})（后端代理）
    │  3. null → fallbackQ() 退回内置题库
    │
    ▼ (路径 2)
api.py: do_chat()
    │
    ▼
chat.py: complete()
    │  从 kv("conf") 读 models[0]
    │  拼 OpenAI /v1/chat/completions 请求
    │  urllib.request 转发
    │  返回 {ok, text}
    │
    ▼
前端拿到文本 → 显示问题 → 用户作答 → 记入 grew[]
```

## 导出/导入

```
                    Python (jsonl.py)
                         ↕ 同构
                    JS (yangdata.js)

yang.jsonl v3 格式：
  第 1 行：文件头 {"t":"head", "fmt":"yang.jsonl", "v":3, "salt":…, "tag":…}
  第 2~N 行：记录  {"t":"idea"|"spark"|"cold"|"conf", …, "tag":…}
  最后一行：尾部  {"t":"tail", "tag":…}

  每行有加盐 HMAC tag → 单行篡改检测
  文件级 tag → 删行/加行检测
  可选 AES-GCM-256 加密

  跨语言对照测试：Python 写 → JS 读 ✓，JS 写 → Python 读 ✓
```
