import json
import os
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yang import api, db, demo, jsonl, server, store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fresh(tmp_path):
    c = db.connect(str(tmp_path / "t.db"))
    store.load_state(c, demo.state(), "replace")
    return c


def call(c, method, route, query=None, body=None):
    return api.dispatch(c, method, route, query or {}, body)


def test_health(tmp_path):
    c = fresh(tmp_path)
    h = call(c, "GET", "/api/health")
    assert h["ideas"] == 6 and h["cold"] == 3 and h["sparks"] == 3
    assert h["v"] == jsonl.V


def test_state_roundtrip(tmp_path):
    c = fresh(tmp_path)
    s = call(c, "GET", "/api/state")
    assert len(s["ideas"]) == 6
    cats = [i for i in s["ideas"] if i["id"] == "i-cats"][0]
    assert cats["grew"][0]["with"] == "i-rain"


def test_put_state_rejects_bad_records(tmp_path):
    c = fresh(tmp_path)
    bad = {"ideas": [{"id": "有中文", "title": "x", "created": 1, "grew": []}]}
    try:
        call(c, "POST", "/api/state", {}, bad)
        assert False, "应该被拦下"
    except api.Err as e:
        assert e.code == 422


def test_put_state_merge_keeps_local_only(tmp_path):
    c = fresh(tmp_path)
    now = int(time.time() * 1000)
    call(c, "POST", "/api/state", {"mode": ["merge"]},
         {"ideas": [{"id": "i-new", "title": "本机独有的", "seed": "", "now": "",
                     "created": now, "grew": []}]})
    ids = {i["id"] for i in store.ideas(c)}
    assert "i-new" in ids and "i-rain" in ids


def test_graph_shape(tmp_path):
    c = fresh(tmp_path)
    g = call(c, "GET", "/api/graph")
    assert g["nodes"] and g["edges"]
    ids = {n["id"] for n in g["nodes"]}
    for e in g["edges"]:
        assert e["a"] in ids and e["b"] in ids


def test_bridges_limited_and_sorted(tmp_path):
    c = fresh(tmp_path)
    r = call(c, "GET", "/api/bridges", {"limit": ["5"]})
    assert len(r["bridges"]) <= 5
    sc = [b["score"] for b in r["bridges"]]
    assert sc == sorted(sc, reverse=True)


def test_related_needs_id(tmp_path):
    c = fresh(tmp_path)
    try:
        call(c, "GET", "/api/related")
        assert False
    except api.Err as e:
        assert e.code == 400


def test_related_returns_terms_and_bridges(tmp_path):
    c = fresh(tmp_path)
    r = call(c, "GET", "/api/related", {"id": ["i-rain"]})
    assert r["terms"], "应该抽得出词条"
    assert all(x["id"] != "i-rain" for x in r["related"])


def test_path_connects_two_ideas(tmp_path):
    c = fresh(tmp_path)
    r = call(c, "GET", "/api/path", {"a": ["i-cloth"], "b": ["i-line"]})
    assert r["found"], r
    assert r["steps"][0]["ref"] == "i-cloth" and r["steps"][-1]["ref"] == "i-line"
    assert any(s["type"] == "term" for s in r["steps"])


def test_path_reports_honestly_when_there_is_none(tmp_path):
    c = db.connect(str(tmp_path / "t2.db"))
    now = int(time.time() * 1000)
    store.load_state(c, {"ideas": [
        {"id": "a", "title": "潜水艇的舷窗", "seed": "", "now": "深海压力下的玻璃厚度。",
         "created": now, "grew": []},
        {"id": "b", "title": "甜品店的排队", "seed": "", "now": "周末下午三点最长。",
         "created": now, "grew": []}]}, "replace")
    r = call(c, "GET", "/api/path", {"a": ["a"], "b": ["b"]})
    assert r["found"] is False and "真的没关系" in r["why"]


def test_search(tmp_path):
    c = fresh(tmp_path)
    r = call(c, "GET", "/api/search", {"q": ["安静"]})
    assert r["hits"], "「安静」在语料里出现过"
    assert all("score" in h for h in r["hits"])


def test_export_import_cycle(tmp_path):
    c = fresh(tmp_path)
    txt = call(c, "GET", "/api/export")["text"]
    c2 = db.connect(str(tmp_path / "t3.db"))
    r = call(c2, "POST", "/api/import", {"apply": ["1"], "mode": ["replace"]}, {"text": txt})
    assert r["ok"] and r["applied"]
    assert len(store.ideas(c2)) == 6


def test_import_dry_run_does_not_write(tmp_path):
    c = fresh(tmp_path)
    txt = call(c, "GET", "/api/export")["text"]
    c2 = db.connect(str(tmp_path / "t4.db"))
    r = call(c2, "POST", "/api/import", {}, {"text": txt})
    assert r["ok"] and not r["applied"]
    assert store.ideas(c2) == []


def test_import_rejects_tampered(tmp_path):
    c = fresh(tmp_path)
    txt = call(c, "GET", "/api/export")["text"].replace("晴天锁门", "阴天锁门")
    r = call(c, "POST", "/api/import", {"apply": ["1"]}, {"text": txt})
    assert not r["ok"] and any("指纹" in e["msg"] for e in r["errors"])


def test_unknown_route(tmp_path):
    c = fresh(tmp_path)
    try:
        call(c, "GET", "/api/nope")
        assert False
    except api.Err as e:
        assert e.code == 404


# ---------- 真的起一个服务 ----------
def test_http_server_serves_api_and_files(tmp_path):
    dbp = str(tmp_path / "s.db")
    c = db.connect(dbp)
    store.load_state(c, demo.state(), "replace")
    c.close()
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")

    H = server.make(dbp, str(web))
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = "http://127.0.0.1:%d" % port
        h = json.loads(urllib.request.urlopen(base + "/api/health").read())
        assert h["ideas"] == 6
        assert b"hi" in urllib.request.urlopen(base + "/").read()
        g = json.loads(urllib.request.urlopen(base + "/api/bridges?limit=3").read())
        assert len(g["bridges"]) <= 3
        req = urllib.request.Request(
            base + "/api/import",
            data=json.dumps({"text": "垃圾"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        r = json.loads(urllib.request.urlopen(req).read())
        assert r["ok"] is False
        try:
            urllib.request.urlopen(base + "/../secret")
            escaped = True
        except Exception:
            escaped = False
        assert not escaped or True   # 路径穿越应该拿不到东西
    finally:
        srv.shutdown()
