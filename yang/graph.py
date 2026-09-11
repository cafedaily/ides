"""关键词图谱：想法—词条 二部图，以及从它推出来的三样东西。

1. 词条之间的共现（NPMI），说明哪些词总一起出现；
2. 想法之间的相似（余弦），说明哪两个想法在讲同一件事；
3. **桥**——同一个词，在 A 里出现在一个维度，在 B 里出现在另一个维度。
   「为什么凉了」里的一个词，出现在另一个还活着的想法的「现在它是什么」里，
   这种连接最值钱：一个已经死过一次的教训，正好长在一个还没死的东西上。

维度加成是个**启发式**，不是什么原理。写在这儿是为了能被质疑和调。
"""
import heapq
import math
from collections import defaultdict

from .terms import extract
from .text import evidence

SAME_DIM = 1.0
CROSS_DIM = 1.35
FROM_WHY = 1.7          # 一头是「为什么凉了」
MIN_BRIDGE = 0.006
PER_PAIR = 2            # 同一对想法最多上榜两条，免得一个热词把榜单占满
MIN_SIM = 0.05
MIN_NPMI = 0.15
TOP_SIM = 6


def build(docs):
    """docs: [{id, kind, title, pieces}] → 图。kind ∈ idea|cold|spark"""
    terms = extract(docs)
    by_id = {d["id"]: d for d in docs}

    nodes, edges = [], []
    for d in docs:
        nodes.append({"id": "idea:" + d["id"], "type": d["kind"],
                      "label": d["title"], "ref": d["id"],
                      "n_terms": len(terms[d["id"]])})
    seen_t = {}
    for did, items in terms.items():
        for it in items:
            k = "term:" + it["term"]
            if k not in seen_t:
                seen_t[k] = {"id": k, "type": "term", "label": it["term"],
                             "ref": it["term"], "docs": 0, "w": 0.0}
                nodes.append(seen_t[k])
            seen_t[k]["docs"] += 1
            seen_t[k]["w"] = round(seen_t[k]["w"] + it["w"], 5)
            edges.append({"a": "idea:" + did, "b": k, "type": "has",
                          "w": it["w"], "dims": it["dims"]})

    return {"nodes": nodes, "edges": edges, "terms": terms,
            "cooc": cooccurrence(terms), "sim": similarity(terms),
            "bridges": bridges(terms, by_id)}


def cooccurrence(terms, min_npmi=MIN_NPMI):
    """NPMI：两个词一起出现，是不是超出了「它们各自都很常见」能解释的程度。"""
    n = max(1, len(terms))
    doc_of = defaultdict(set)
    for did, items in terms.items():
        for it in items:
            doc_of[it["term"]].add(did)
    pairs = defaultdict(int)
    for did, items in terms.items():
        ts = sorted({it["term"] for it in items})
        for i in range(len(ts)):
            for j in range(i + 1, len(ts)):
                pairs[(ts[i], ts[j])] += 1
    out = []
    for (a, b), c in pairs.items():
        if c < 2:
            continue
        pa, pb, pab = len(doc_of[a]) / n, len(doc_of[b]) / n, c / n
        if pab <= 0 or pab >= 1:
            continue
        npmi = math.log(pab / (pa * pb)) / (-math.log(pab))
        if npmi >= min_npmi:
            out.append({"a": a, "b": b, "n": c, "npmi": round(npmi, 4)})
    out.sort(key=lambda x: -x["npmi"])
    return out


def similarity(terms, min_sim=MIN_SIM, top=TOP_SIM):
    """余弦。权重已经在 extract 里归一化过了，所以点积就是余弦。"""
    vec = {d: {it["term"]: it["w"] for it in items} for d, items in terms.items()}
    ids = list(vec)
    out = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = vec[ids[i]], vec[ids[j]]
            if len(b) < len(a):
                a, b = b, a
            s = sum(w * b.get(t, 0.0) for t, w in a.items())
            if s >= min_sim:
                shared = sorted((t for t in a if t in b),
                                key=lambda t: -(a[t] * b[t]))[:5]
                out.append({"a": ids[i], "b": ids[j], "sim": round(s, 4), "shared": shared})
    out.sort(key=lambda x: -x["sim"])
    keep, cnt = [], defaultdict(int)
    for e in out:                       # 每个想法最多留 top 条，免得图糊成一坨
        if cnt[e["a"]] >= top and cnt[e["b"]] >= top:
            continue
        keep.append(e)
        cnt[e["a"]] += 1
        cnt[e["b"]] += 1
    return keep


def _dim_bonus(da, db):
    if "why" in da or "why" in db:
        if not (da & db) or ("why" in da) != ("why" in db):
            return FROM_WHY
    return SAME_DIM if (da & db) else CROSS_DIM


def bridges(terms, by_id, min_score=MIN_BRIDGE, limit=60):
    """一个词把两个想法串起来，而且串的是**不同的两个维度**。"""
    where = defaultdict(list)
    for did, items in terms.items():
        for it in items:
            where[it["term"]].append((did, it))
    out = []
    for term, hits in where.items():
        if len(hits) < 2:
            continue
        for i in range(len(hits)):
            for j in range(i + 1, len(hits)):
                (da_id, ia), (db_id, ib) = hits[i], hits[j]
                sa, sb = set(ia["dims"]), set(ib["dims"])
                bonus = _dim_bonus(sa, sb)
                score = ia["w"] * ib["w"] * bonus
                if score < min_score:
                    continue
                out.append({
                    "term": term, "a": da_id, "b": db_id,
                    "score": round(score, 5), "bonus": bonus,
                    "a_dims": sorted(sa), "b_dims": sorted(sb),
                    "a_title": by_id[da_id]["title"], "b_title": by_id[db_id]["title"],
                    "a_say": _say(by_id[da_id], term), "b_say": _say(by_id[db_id], term),
                })
    out.sort(key=lambda x: -x["score"])
    keep, per = [], defaultdict(int)
    for x in out:
        k = frozenset((x["a"], x["b"]))
        if per[k] >= PER_PAIR:
            continue
        per[k] += 1
        keep.append(x)
        if len(keep) >= limit:
            break
    return keep


def _say(doc, term):
    for p in doc["pieces"]:
        e = evidence(p["text"], term)
        if e:
            return {"dim": p["dim"], "text": e}
    return {"dim": "", "text": ""}


def path(terms, a, b, max_hops=6):
    """A 和 B 一个共同词都没有时，还能不能连上？

    在「想法—词条」二部图上跑 Dijkstra，边的代价是 1/权重。
    走出来的路径长这样：想法 → 词 → 想法 → 词 → 想法。
    中间每一跳都是真实出现过的词，不是编的。
    """
    adj = defaultdict(list)
    for did, items in terms.items():
        for it in items:
            w = max(it["w"], 1e-4)
            adj["idea:" + did].append(("term:" + it["term"], 1.0 / w))
            adj["term:" + it["term"]].append(("idea:" + did, 1.0 / w))
    src, dst = "idea:" + a, "idea:" + b
    if src not in adj or dst not in adj:
        return None
    dist = {src: 0.0}
    prev = {}
    pq = [(0.0, 0, src)]
    while pq:
        d, hops, u = heapq.heappop(pq)
        if u == dst:
            node, out = dst, []
            while node in prev:
                out.append(node)
                node = prev[node]
            out.append(src)
            out.reverse()
            return {"cost": round(d, 4), "hops": len(out) - 1, "nodes": out}
        if d > dist.get(u, 1e18) or hops > max_hops:
            continue
        for v, c in adj[u]:
            nd = d + c
            if nd < dist.get(v, 1e18):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, hops + 1, v))
    return None
