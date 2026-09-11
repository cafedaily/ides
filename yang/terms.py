"""把候选词条压成每篇的关键词，带权重和「出现在哪个维度」。

维度就是这段话在应用里的身份：最初那句、现在它是什么、追问、换个角度、
碰一下、随手记、为什么凉了、还没成形的念头。同一个词出现在不同维度上，
是后面找「桥」的全部依据。
"""
import math
from collections import Counter, defaultdict

from . import entity
from .text import GENERIC, NUM_HEAD, candidates

# 维度权重：标题和「现在它是什么」是他反复改过的，比一次性的回答更能代表这个想法
DIM_W = {
    "title": 1.7, "now": 1.35, "seed": 1.2,
    "ask": 1.0, "angle": 1.0, "collide": 1.0, "note": 0.9,
    "why": 1.3, "spark": 1.1,
}
DIMS = tuple(DIM_W)

TOP_N = 24
MIN_W = 0.04
GENERIC_W = 0.45      # 时间/数量词降一档：它们能把任何两件事连起来，那就不算连接


def _doc_terms(doc, entities=None):
    """一篇里每个词条的加权词频，以及它出现过的维度。"""
    tf = Counter()
    dims = defaultdict(Counter)
    for p in doc["pieces"]:
        dim = p["dim"]
        w = DIM_W.get(dim, 1.0)
        for term, c in candidates(p["text"], entities).items():
            tf[term] += c * w
            dims[term][dim] += c
    return tf, dims


def extract(docs, top_n=TOP_N, min_w=MIN_W, entities=None):
    """docs: [{id, kind, title, pieces:[{dim,text}]}] → {doc_id: [term dict]}

    先扫一遍全语料认实体（`entity.discover`），再逐篇抽词。两遍是必须的：
    「定期见面」在每篇里只说一次，逐篇的眼光看不见它，只有把所有篇放在一起
    才能看出这四个字总是一起出现。`entities` 传进来就跳过第一遍，给测试和
    需要固定词表的场合用。

    IDF 用平滑过的：语料只有几十篇，不平滑的话一个只出现一次的词会被吹到天上。
    """
    if entities is None:
        entities = entity.discover(
            p["text"] for d in docs for p in d["pieces"])
    raw = {}
    df = Counter()
    for d in docs:
        tf, dims = _doc_terms(d, entities)
        raw[d["id"]] = (tf, dims)
        for t in tf:
            df[t] += 1

    n = max(1, len(docs))
    out = {}
    for d in docs:
        tf, dims = raw[d["id"]]
        if not tf:
            out[d["id"]] = []
            continue
        scored = []
        for t, f in tf.items():
            # 只在一篇里出现过的两字词，多半是噪声；三字以上或英文词留着
            if df[t] < 2 and len(t) <= 2 and not t.isascii():
                continue
            idf = math.log((n + 1) / (df[t] + 1)) + 1.0
            scored.append((t, (1 + math.log(f)) * idf))
        if not scored:
            # 按规则筛完什么都不剩时，原样留下。一篇抽不出词条就永远进不了图——
            # 既搜不到也串不上。宁可留着噪声，也不要一个隐形的想法。
            scored = [(t, 1.0) for t in tf]
        norm = math.sqrt(sum(w * w for _, w in scored)) or 1.0
        items = []
        for t, w in scored:
            weak = t in GENERIC or (len(t) == 2 and t[0] in NUM_HEAD)
            wn = (w / norm) * (GENERIC_W if weak else 1.0)
            if wn < min_w:
                continue
            items.append({
                "term": t, "w": round(wn, 5), "tf": round(tf[t], 3),
                "df": df[t], "dims": dict(dims[t]),
            })
        items.sort(key=lambda x: -x["w"])
        out[d["id"]] = items[:top_n]
    return out
