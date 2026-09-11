"""路由。每个函数收 (conn, query, body) 返回可以 json 化的东西。"""
import json

from . import chat as _chat
from . import db as _db
from . import jsonl, store, sync, quality, semantic
from .graph import path as _path
from .terms import extract


class Err(Exception):
    def __init__(self, code, msg, details=None):
        super().__init__(msg)
        self.code = code
        self.msg = msg
        self.details = details or {}


def health(c, q, b):
    return {"ok": True, "app": "养想法", "fmt": jsonl.FMT, "v": jsonl.V,
            "ideas": len(store.ideas(c)), "sparks": len(store.sparks(c)),
            "cold": len(store.cold(c)), "graph_at": _db.kv_get(c, "graph_at", 0)}


def public_health(c, q, b):
    return {"ok": True, "app": "养想法", "fmt": jsonl.FMT, "v": jsonl.V}


def private_health(c, q, b):
    return health(c, q, b)


def session(c, q, b):
    return {"ok": True, "authenticated": True}


def get_state(c, q, b):
    return store.state(c)


def put_state(c, q, b):
    if not isinstance(b, dict):
        raise Err(400, "要一个 JSON 对象。")
    mode = (q.get("mode") or ["merge"])[0]
    if mode not in ("merge", "replace"):
        raise Err(400, "mode 只能是 merge 或 replace。")
    try:
        sync.validate_state(b)
    except (ValueError, TypeError) as exc:
        raise Err(422, str(exc))
    store.load_state(c, b, mode)
    return {"ok": True, "mode": mode, **private_health(c, q, b)}


def sync_state(c, q, b):
    try:
        return sync.apply(c,b)
    except sync.Conflict as exc:
        raise Err(409,"其他会话已保存修改，请先处理冲突。", {"revision":exc.revision})
    except (ValueError,TypeError) as exc:
        raise Err(422,str(exc))


def graph(c, q, b):
    g = store.graph(c)
    return {"nodes": g["nodes"], "edges": g["edges"],
            "sim": g["sim"], "cooc": g["cooc"], "bridges": g["bridges"]}


def bridges(c, q, b):
    lim = _int(q, "limit", 20, 1, 200)
    g = store.graph(c)
    return {"bridges": g["bridges"][:lim], "n_docs": len(g["terms"])}


def related(c, q, b):
    i = (q.get("id") or [""])[0]
    if not i:
        raise Err(400, "要一个 id。")
    g = store.graph(c)
    sims = [e for e in g["sim"] if e["a"] == i or e["b"] == i]
    out = [{"id": (e["b"] if e["a"] == i else e["a"]), "sim": e["sim"], "shared": e["shared"]}
           for e in sims]
    br = [x for x in g["bridges"] if x["a"] == i or x["b"] == i][:10]
    return {"id": i, "related": out, "bridges": br,
            "terms": g["terms"].get(i, [])}


def connect(c, q, b):
    a = (q.get("a") or [""])[0]
    z = (q.get("b") or [""])[0]
    if not a or not z:
        raise Err(400, "要两个 id：a 和 b。")
    docs = store.docs(c)
    title = {d["id"]: d["title"] for d in docs}
    p = _path(store.graph(c)["terms"], a, z)
    if not p:
        return {"found": False,
                "why": "这两个想法之间没有一条由共同词条连成的路。它们现在真的没关系。"}
    steps = []
    for nid in p["nodes"]:
        kind, ref = nid.split(":", 1)
        steps.append({"type": kind, "ref": ref,
                      "label": title.get(ref, ref) if kind == "idea" else ref})
    return {"found": True, "hops": p["hops"], "cost": p["cost"], "steps": steps}


def search(c, q, b):
    s = (q.get("q") or [""])[0].strip().lower()
    if not s:
        raise Err(400, "要一个 q。")
    docs = store.docs(c)
    title = {d["id"]: d["title"] for d in docs}
    conf = _db.kv_get(c, "conf", {}) or {}
    s = quality.Normalizer(conf.get("graph", {})).text(s).casefold()
    terms = store.graph(c)["terms"]
    hits = []
    for did, items in terms.items():
        m = [it for it in items if s in it["term"]]
        if m:
            hits.append({"id": did, "title": title[did],
                         "score": round(sum(x["w"] for x in m), 4),
                         "terms": [x["term"] for x in m[:5]]})
    hits.sort(key=lambda x: -x["score"])
    return {"q": s, "hits": hits[:30]}


def export(c, q, b):
    if q.get("pass"):
        raise Err(400,"加密导出口令请通过 POST 请求体提交。")
    pw = b.get("pass") if isinstance(b,dict) else None
    if pw is not None and (not isinstance(pw,str) or len(pw)<4):
        raise Err(422,"加密口令至少 4 个字符。")
    return {"text": jsonl.export(store.state(c, include_keys=bool(pw)), pw or None)}


def imp(c, q, b):
    if not isinstance(b, dict) or "text" not in b:
        raise Err(400, "要 {text: \"…\"}。")
    r = jsonl.parse(b["text"], b.get("pass"))
    if not r.get("ok"):
        return {"ok": False, "needPass": r.get("needPass", False),
                "errors": r.get("errors", []), "warnings": r.get("warnings", [])}
    out = {"ok": True, "counts": r["counts"], "warnings": r["warnings"], "applied": False}
    if (q.get("apply") or ["0"])[0] in ("1", "true"):
        mode = (q.get("mode") or ["merge"])[0]
        if mode not in ("merge","replace"):
            raise Err(400,"mode 只能是 merge 或 replace。")
        st = jsonl.to_state(r["recs"])
        try:
            sync.validate_state(st)
        except (ValueError,TypeError) as exc:
            raise Err(422,str(exc))
        store.load_state(c, st, mode)
        out["applied"] = True
        out["mode"] = mode
    return out


def rebuild(c, q, b):
    g = store.rebuild(c)
    return {"ok": True, "docs": len(g["terms"]),
            "terms": sum(len(v) for v in g["terms"].values()),
            "bridges": len(g["bridges"]), "sim": len(g["sim"])}


def semantic_related(c,q,b):
    if not isinstance(b,dict) or not isinstance(b.get("id"),str):
        raise Err(422,"请指定想法 id。")
    try:
        return semantic.related(c,b["id"])
    except ValueError as exc:
        raise Err(422,str(exc))


def do_chat(c, q, b):
    if not isinstance(b, dict):
        raise Err(400, "要一个 JSON 对象。")
    return _chat.complete(c, b)


def _int(q, k, d, lo, hi):
    try:
        v = int((q.get(k) or [d])[0])
    except Exception:
        return d
    return max(lo, min(hi, v))


ROUTES = {
    ("GET", "/api/health"): health,
    ("GET", "/api/session"): session,
    ("GET", "/api/state"): get_state,
    ("POST", "/api/state"): put_state,
    ("POST", "/api/sync"): sync_state,
    ("POST", "/api/semantic"): semantic_related,
    ("POST", "/api/export"): export,
    ("GET", "/api/graph"): graph,
    ("GET", "/api/bridges"): bridges,
    ("GET", "/api/related"): related,
    ("GET", "/api/path"): connect,
    ("GET", "/api/search"): search,
    ("GET", "/api/export"): export,
    ("POST", "/api/import"): imp,
    ("POST", "/api/rebuild"): rebuild,
    ("POST", "/api/chat"): do_chat,
}

PUBLIC_ROUTES = {
    ("GET", "/api/health"),
}

SESSION_ROUTES = {
    ("GET", "/api/session"),
}

MUTATION_ROUTES = {key for key in ROUTES if key[0] == "POST"}


def dispatch(conn, method, route, query, body):
    fn = ROUTES.get((method, route))
    if not fn:
        raise Err(404, "没有这个接口：%s %s" % (method, route))
    return fn(conn, query, body)
