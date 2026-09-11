"""想法的读写，以及「拆成带维度的片段」——图谱唯一的输入。"""
import copy
import time
import json
import threading
from collections import OrderedDict
from .graph_engine import GraphCache

from . import db as _db
from .graph import build, path
from .terms import extract

KINDS = ("ask", "angle", "collide", "note")


def now_ms():
    return int(time.time() * 1000)


# ---------- 配置里的密钥 ----------
def _model_id(m):
    if not isinstance(m, dict):
        return ""
    return str(m.get("id") or "")


def _merge_conf_keys(c, conf):
    """Preserve existing model keys by id unless the incoming model explicitly clears them."""
    incoming = copy.deepcopy(conf)
    if not isinstance(incoming, dict):
        return incoming
    existing = _db.kv_get(c, "conf", None) or {}
    old_by_id = {}
    for m in existing.get("models", []) if isinstance(existing, dict) else []:
        mid = _model_id(m)
        if mid and isinstance(m, dict) and m.get("key"):
            old_by_id[mid] = m.get("key")
    for m in incoming.get("models", []) or []:
        if not isinstance(m, dict):
            continue
        mid = _model_id(m)
        if m.get("clear_key") is True:
            m["key"] = ""
        elif mid and ("key" not in m or m.get("key") == "") and old_by_id.get(mid):
            m["key"] = old_by_id[mid]
        m.pop("clear_key", None)
        m.pop("keyConfigured", None)
    return incoming


def redacted_conf(conf):
    """Return conf without model keys, adding keyConfigured metadata."""
    if conf is None:
        return None
    out = copy.deepcopy(conf)
    if not isinstance(out, dict):
        return out
    for m in out.get("models", []) or []:
        if not isinstance(m, dict):
            continue
        configured = bool(m.get("key"))
        m.pop("key", None)
        m.pop("clear_key", None)
        m["keyConfigured"] = configured
    return out


# ---------- 读 ----------
def ideas(c):
    out = []
    for r in c.execute("SELECT * FROM ideas ORDER BY updated DESC"):
        g = [dict(x) for x in c.execute(
            "SELECT kind,q,a,at,by,with_id FROM grew WHERE idea_id=? ORDER BY at", (r["id"],))]
        for x in g:
            x["with"] = x.pop("with_id") or ""
        out.append({"id": r["id"], "title": r["title"], "seed": r["seed"],
                    "now": r["now"], "created": r["created"], "grew": g})
    return out


def sparks(c):
    return [dict(r) for r in c.execute("SELECT * FROM sparks ORDER BY at DESC")]


def cold(c):
    return [dict(r) for r in c.execute("SELECT * FROM cold ORDER BY at DESC")]


def state(c, include_keys=False):
    conf = _db.kv_get(c, "conf", None)
    return {"revision": _db.kv_get(c, "revision", 0), "ideas": ideas(c), "sparks": sparks(c), "cold": cold(c),
            "conf": conf if include_keys else redacted_conf(conf)}


# ---------- 写 ----------
def put_idea(c, i):
    t = now_ms()
    c.execute("""INSERT INTO ideas(id,title,seed,now,created,updated) VALUES(?,?,?,?,?,?)
                 ON CONFLICT(id) DO UPDATE SET title=excluded.title, seed=excluded.seed,
                 now=excluded.now, updated=excluded.updated""",
              (i["id"], i["title"], i.get("seed", ""), i.get("now", ""),
               int(i.get("created", t)), t))
    c.execute("DELETE FROM grew WHERE idea_id=?", (i["id"],))
    for g in i.get("grew", []):
        c.execute("INSERT INTO grew(idea_id,kind,q,a,at,by,with_id) VALUES(?,?,?,?,?,?,?)",
                  (i["id"], g["kind"], g["q"], g["a"], int(g["at"]),
                   g.get("by", ""), g.get("with", "")))


def put_spark(c, s):
    c.execute("""INSERT INTO sparks(id,text,at) VALUES(?,?,?)
                 ON CONFLICT(id) DO UPDATE SET text=excluded.text, at=excluded.at""",
              (s["id"], s["text"], int(s["at"])))


def put_cold(c, x):
    c.execute("""INSERT INTO cold(id,title,why,at) VALUES(?,?,?,?)
                 ON CONFLICT(id) DO UPDATE SET title=excluded.title, why=excluded.why, at=excluded.at""",
              (x["id"], x["title"], x["why"], int(x["at"])))


def load_state(c, st, mode="merge"):
    """把一份（已经校验过的）状态放进库。merge 只补不删。"""
    if mode not in ("merge", "replace"):
        raise ValueError("mode must be merge or replace")
    if mode == "replace":
        for t in ("grew", "ideas", "sparks", "cold"):
            c.execute("DELETE FROM " + t)
    for i in st.get("ideas", []):
        put_idea(c, i)
    for s in st.get("sparks", []):
        put_spark(c, s)
    for x in st.get("cold", []):
        put_cold(c, x)
    if st.get("conf"):
        _db.kv_set(c, "conf", _merge_conf_keys(c, st["conf"]))
    _db.kv_set(c, "revision", _db.kv_get(c, "revision", 0) + 1)
    c.commit()


# ---------- 拆成带维度的片段 ----------
def docs(c):
    out = []
    for i in ideas(c):
        pieces = [{"dim": "title", "text": i["title"]}]
        if i["seed"]:
            pieces.append({"dim": "seed", "text": i["seed"]})
        if i["now"]:
            pieces.append({"dim": "now", "text": i["now"]})
        for g in i["grew"]:
            dim = g["kind"] if g["kind"] in KINDS else "note"
            pieces.append({"dim": dim, "text": g["q"] + "\n" + g["a"]})
        out.append({"id": i["id"], "kind": "idea", "title": i["title"], "pieces": pieces})
    for x in cold(c):
        out.append({"id": x["id"], "kind": "cold", "title": x["title"],
                    "pieces": [{"dim": "title", "text": x["title"]},
                               {"dim": "why", "text": x["why"]}]})
    for s in sparks(c):
        out.append({"id": s["id"], "kind": "spark",
                    "title": s["text"][:24], "pieces": [{"dim": "spark", "text": s["text"]}]})
    return out


# ---------- 图谱 ----------
_GRAPH_LOCK = threading.RLock()
_GRAPH_CACHES = OrderedDict()


def graph(c, force=False):
    # Bound caches to four database identities; in-memory connections stay distinct.
    filename = c.execute("PRAGMA database_list").fetchone()[2]
    identity = filename or c
    with _GRAPH_LOCK:
        cache = _GRAPH_CACHES.pop(identity, None) or GraphCache()
        _GRAPH_CACHES[identity] = cache
        while len(_GRAPH_CACHES) > 4:
            _GRAPH_CACHES.popitem(last=False)
        owned_transaction = not c.in_transaction
        if owned_transaction:
            c.execute("BEGIN")
        try:
            documents = docs(c)
            conf = _db.kv_get(c, "conf", {}) or {}
        finally:
            if owned_transaction:
                c.rollback()
        return cache.update(documents, conf.get("graph", {}), force=force)


def graph_metrics(c):
    identity = c.execute("PRAGMA database_list").fetchone()[2] or c
    with _GRAPH_LOCK:
        cache = _GRAPH_CACHES.get(identity)
        return dict(cache.metrics) if cache else {}


def rebuild(c):
    g = graph(c)
    existing = {(row["doc_id"],row["term"]): (row["w"],row["tf"],row["df"],row["dims"])
                for row in c.execute("SELECT * FROM doc_terms")}
    wanted = {}
    for did, items in g["terms"].items():
        for item in items:
            wanted[(did,item["term"])] = (item["w"],item["tf"],item["df"],json.dumps(item["dims"],ensure_ascii=False))
    for key in existing.keys() - wanted.keys():
        c.execute("DELETE FROM doc_terms WHERE doc_id=? AND term=?", key)
    for key, value in wanted.items():
        if existing.get(key) != value:
            c.execute("INSERT OR REPLACE INTO doc_terms(doc_id,term,w,tf,df,dims) VALUES(?,?,?,?,?,?)", (*key,*value))
    _db.kv_set(c, "graph_at", now_ms())
    c.commit()
    return g


def connect_two(c, a, b):
    return path(graph(c)["terms"], a, b)
