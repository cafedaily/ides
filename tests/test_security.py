import http.client
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yang import api, auth, db, server, store

TOKEN = "T003_SYNTHETIC_STRONG_TOKEN_0123456789abcdef"
ORIGIN = "https://ideas.example.test"


def make_policy():
    return auth.AuthPolicy(token=TOKEN, production=True, public_origin=ORIGIN,
                           session_cookie_name="yang_test_session",
                           session_ttl_seconds=3600, secure_cookie=True)


def start(tmp_path, policy=None):
    dbp = str(tmp_path / "s.db")
    c = db.connect(dbp)
    store.load_state(c, {"conf": {"models": [{"id": "m1", "name": "M1", "base": "https://llm.example", "key": "SECRETKEY"}]}}, "replace")
    c.close()
    web = tmp_path / "web"
    web.mkdir(exist_ok=True)
    (web / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")
    H = server.make(dbp, str(web), policy=policy or make_policy(), host="127.0.0.1")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def urlopen(req):
    try:
        r = urllib.request.urlopen(req, timeout=5)
        return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def get(base, path, headers=None):
    return urlopen(urllib.request.Request(base + path, headers=headers or {}))


def post(base, path, obj, headers=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    return urlopen(urllib.request.Request(base + path, data=json.dumps(obj).encode(), headers=h, method="POST"))


def body(raw):
    return json.loads(raw.decode())


def test_production_rejects_absent_or_weak_token():
    for env in ({"YANG_PRODUCTION": "1"}, {"YANG_PRODUCTION": "1", "YANG_AUTH_TOKEN": "short"}):
        try:
            auth.load_policy_from_env(env, host="0.0.0.0")
            assert False
        except auth.AuthConfigError:
            pass
    p = auth.load_policy_from_env({"YANG_PRODUCTION": "1", "YANG_AUTH_TOKEN": TOKEN}, host="0.0.0.0")
    assert p.production and p.has_token


def test_loopback_without_token_keeps_existing_local_behavior(tmp_path):
    srv, base = start(tmp_path, auth.AuthPolicy())
    try:
        code, _, raw = get(base, "/api/health")
        assert code == 200 and body(raw)["ok"]
        code, _, raw = get(base, "/api/state")
        assert code == 200 and "conf" in body(raw)
    finally:
        srv.shutdown()


def test_private_routes_require_auth_and_health_is_public_redacted(tmp_path):
    srv, base = start(tmp_path)
    try:
        code, _, raw = get(base, "/api/health")
        h = body(raw)
        assert code == 200 and "ideas" not in h and "graph_at" not in h
        code, _, _ = get(base, "/api/state")
        assert code == 401
        code, _, raw = get(base, "/api/session")
        assert code == 401
    finally:
        srv.shutdown()


def test_login_cookie_bearer_logout_and_origin(tmp_path):
    srv, base = start(tmp_path)
    try:
        code, _, _ = post(base, "/api/login?token=" + TOKEN, {})
        assert code == 400
        code, headers, raw = post(base, "/api/login", {"token": TOKEN}, {"Origin": ORIGIN})
        assert code == 200 and body(raw)["authenticated"] is True
        cookie = headers["Set-Cookie"]
        assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Secure" in cookie
        code, _, raw = get(base, "/api/session", {"Cookie": cookie})
        assert code == 200 and body(raw)["authenticated"] is True
        code, _, raw = get(base, "/api/state", {"Authorization": "Bearer " + TOKEN})
        assert code == 200 and "ideas" in body(raw)
        code, _, _ = post(base, "/api/rebuild", {}, {"Cookie": cookie, "Origin": "https://evil.example"})
        assert code == 403
        code, _, _ = post(base, "/api/rebuild", {}, {"Authorization": "Bearer " + TOKEN, "Origin": "https://evil.example"})
        assert code == 200
        code, headers, raw = post(base, "/api/logout", {}, {"Origin": ORIGIN})
        assert code == 200 and "Max-Age=0" in headers["Set-Cookie"]
    finally:
        srv.shutdown()


def test_login_throttles_failed_attempts(tmp_path):
    srv, base = start(tmp_path)
    try:
        last = None
        for _ in range(6):
            last = post(base, "/api/login", {"token": "wrong"}, {"Origin": ORIGIN})[0]
        assert last in (401, 429)
        code, headers, _ = post(base, "/api/login", {"token": "wrong"}, {"Origin": ORIGIN})
        assert code == 429 and int(headers["Retry-After"]) > 0
    finally:
        srv.shutdown()


def test_state_redacts_preserves_and_clears_model_keys(tmp_path):
    srv, base = start(tmp_path)
    try:
        bearer = {"Authorization": "Bearer " + TOKEN}
        code, _, raw = get(base, "/api/state", bearer)
        st = body(raw)
        m = st["conf"]["models"][0]
        assert "key" not in m and m["keyConfigured"] is True
        st["conf"]["models"][0].pop("keyConfigured")
        code, _, _ = post(base, "/api/state", st, bearer)
        assert code == 200
        code, _, raw = get(base, "/api/state", bearer)
        assert body(raw)["conf"]["models"][0]["keyConfigured"] is True
        st = body(raw)
        st["conf"]["models"][0]["key"] = ""
        st["conf"]["models"][0].pop("keyConfigured")
        code, _, _ = post(base, "/api/state", st, bearer)
        assert code == 200
        code, _, raw = get(base, "/api/state", bearer)
        assert body(raw)["conf"]["models"][0]["keyConfigured"] is True
        st = body(raw)
        st["conf"]["models"][0]["clear_key"] = True
        st["conf"]["models"][0].pop("keyConfigured")
        code, _, _ = post(base, "/api/state", st, bearer)
        assert code == 200
        code, _, raw = get(base, "/api/state", bearer)
        assert body(raw)["conf"]["models"][0]["keyConfigured"] is False
    finally:
        srv.shutdown()


def test_plain_export_never_leaks_keys(tmp_path):
    srv, base = start(tmp_path)
    try:
        code, _, raw = get(base, "/api/export", {"Authorization": "Bearer " + TOKEN})
        assert code == 200
        txt = body(raw)["text"]
        assert "SECRETKEY" not in txt
        assert "keyDropped" in txt
    finally:
        srv.shutdown()


def test_production_secure_cookie_cannot_be_disabled_by_env():
    p = auth.load_policy_from_env({
        "YANG_PRODUCTION": "1",
        "YANG_AUTH_TOKEN": TOKEN,
        "YANG_AUTH_SECURE_COOKIE": "0",
    }, host="0.0.0.0")
    assert p.production and p.secure_cookie is True


def test_malformed_content_length_rejected_and_connection_closed(tmp_path):
    srv, base = start(tmp_path)
    try:
        host, port = base.split("//", 1)[1].split(":")
        conn = http.client.HTTPConnection(host, int(port), timeout=5)
        conn.putrequest("POST", "/api/login")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", "abc")
        conn.endheaders()
        resp = conn.getresponse()
        assert resp.status == 400
        resp.read()
        assert resp.getheader("Connection") == "close"
        try:
            conn.request("GET", "/api/health")
            again = conn.getresponse()
            assert again.status != 200
        except Exception:
            pass
        conn.close()
    finally:
        srv.shutdown()


def test_unsupported_transfer_encoding_rejected_and_connection_closed(tmp_path):
    srv, base = start(tmp_path)
    try:
        host, port = base.split("//", 1)[1].split(":")
        conn = http.client.HTTPConnection(host, int(port), timeout=5)
        conn.putrequest("POST", "/api/login")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Transfer-Encoding", "chunked")
        conn.endheaders()
        resp = conn.getresponse()
        assert resp.status == 400
        assert "Transfer-Encoding" in resp.read().decode()
        assert resp.getheader("Connection") == "close"
        conn.close()
    finally:
        srv.shutdown()


def test_static_path_is_contained(tmp_path):
    srv, base = start(tmp_path)
    try:
        code, _, raw = get(base, "/")
        assert code == 200 and b"hi" in raw
        code, _, _ = get(base, "/..%2fsecret.txt")
        assert code == 404
    finally:
        srv.shutdown()


def test_non_loopback_without_token_refused_unless_unsafe_flag():
    try:
        server.serve("x.db", ".", host="0.0.0.0", port=0)
        assert False
    except auth.AuthConfigError:
        pass
    # Construction path used by CLI unsafe development flag should not require a token.
    H = server.make("x.db", ".", host="0.0.0.0", unsafe_no_auth=True)
    assert H


def test_api_dispatch_health_keeps_legacy_counts(tmp_path):
    c = db.connect(str(tmp_path / "a.db"))
    h = api.dispatch(c, "GET", "/api/health", {}, None)
    assert "ideas" in h and "graph_at" in h
