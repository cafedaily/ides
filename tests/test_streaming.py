import json
import os
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yang import auth, db, server, store

TOKEN = "T001_SYNTHETIC_STRONG_TOKEN_0123456789abcdef"
ORIGIN = "https://ideas.example.test"


class UpstreamState:
    def __init__(self, mode="barrier"):
        self.mode = mode
        self.first_sent = threading.Event()
        self.release = threading.Event()
        self.payloads = []


def start_upstream(state):
    class U(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n)
            state.payloads.append(json.loads(raw.decode()))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if state.mode == "malformed":
                self.wfile.write(b"data: {not-json}\n\n")
                self.wfile.flush()
                return
            if state.mode == "upstream_error_frame":
                self.wfile.write(b"data: {\"error\":{\"message\":\"SECRET raw upstream\"}}\n\n")
                self.wfile.flush()
                return
            first = {"choices":[{"delta":{"content":"你"}}]}
            self.wfile.write(("data: " + json.dumps(first, ensure_ascii=False) + "\n\n").encode())
            self.wfile.flush()
            state.first_sent.set()
            state.release.wait(5)
            second = {"choices":[{"delta":{"content":"好"}, "finish_reason":"stop"}]}
            self.wfile.write(("data: " + json.dumps(second, ensure_ascii=False) + "\n\n").encode())
            self.wfile.flush()

    srv = ThreadingHTTPServer(("127.0.0.1", 0), U)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv, "http://127.0.0.1:%d/v1" % srv.server_address[1]


def start_yang(tmp_path, upstream_base):
    dbp = str(tmp_path / "s.db")
    c = db.connect(dbp)
    store.load_state(c, {"conf": {"models": [{"id":"m1", "name":"M1", "base":upstream_base, "model":"m", "key":"UPSTREAM_SECRET"}]}}, "replace")
    c.close()
    web = tmp_path / "web"
    web.mkdir(exist_ok=True)
    (web / "index.html").write_text("hi", encoding="utf-8")
    policy = auth.AuthPolicy(token=TOKEN, production=True, public_origin=ORIGIN,
                             session_cookie_name="yang_test_session", secure_cookie=True)
    H = server.make(dbp, str(web), policy=policy, host="127.0.0.1")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def stream_req(base, body, headers=None):
    h = {"Content-Type":"application/json", "Authorization":"Bearer " + TOKEN}
    h.update(headers or {})
    return urllib.request.Request(base + "/api/chat", data=json.dumps(body).encode(), headers=h, method="POST")


def read_event(resp):
    buf = b""
    while b"\n\n" not in buf:
      b = resp.read(1)
      if not b:
          break
      buf += b
    text = buf.decode("utf-8")
    data = "\n".join(line[5:].lstrip() for line in text.splitlines() if line.startswith("data:"))
    return json.loads(data)


def test_stream_first_delta_arrives_before_upstream_completion_barrier(tmp_path):
    state = UpstreamState("barrier")
    up, upbase = start_upstream(state)
    srv, base = start_yang(tmp_path, upbase)
    try:
        body = {"stream": True, "messages":[{"role":"user", "content":"hi"}], "action":"ask"}
        resp = urllib.request.urlopen(stream_req(base, body, {"Origin": ORIGIN}), timeout=5)
        assert resp.headers["Content-Type"].startswith("text/event-stream")
        assert resp.headers["Cache-Control"] == "no-store"
        assert resp.headers["X-Accel-Buffering"] == "no"
        first = read_event(resp)
        assert first == {"type":"delta", "text":"你"}
        assert state.first_sent.is_set()
        assert state.payloads[0]["stream"] is True
        assert state.payloads[0]["messages"][0]["content"] == "hi"
        # The second delta cannot be available until the controlled barrier opens.
        time.sleep(0.15)
        state.release.set()
        second = read_event(resp)
        done = read_event(resp)
        assert second == {"type":"delta", "text":"好"}
        assert done == {"type":"done"}
        resp.close()
    finally:
        srv.shutdown(); up.shutdown()


def test_stream_rejects_private_auth_and_origin_before_upstream(tmp_path):
    state = UpstreamState("barrier")
    up, upbase = start_upstream(state)
    srv, base = start_yang(tmp_path, upbase)
    try:
        body = {"stream": True, "messages":[{"role":"user", "content":"hi"}]}
        try:
            urllib.request.urlopen(stream_req(base, body, {"Authorization":"Bearer wrong"}), timeout=5)
            assert False
        except Exception as e:
            assert getattr(e, "code", None) == 401
        cookie = auth.make_session_cookie(TOKEN, cookie_name="yang_test_session").split(";", 1)[0]
        h = {"Content-Type":"application/json", "Cookie":cookie, "Origin":"https://evil.example"}
        req = urllib.request.Request(base + "/api/chat", data=json.dumps(body).encode(), headers=h, method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False
        except Exception as e:
            assert getattr(e, "code", None) == 403
        assert state.payloads == []
    finally:
        srv.shutdown(); up.shutdown()


def test_stream_malformed_upstream_frame_returns_sanitized_error(tmp_path):
    state = UpstreamState("malformed")
    up, upbase = start_upstream(state)
    srv, base = start_yang(tmp_path, upbase)
    try:
        body = {"stream": True, "messages":[{"role":"user", "content":"hi"}]}
        resp = urllib.request.urlopen(stream_req(base, body, {"Origin": ORIGIN}), timeout=5)
        ev = read_event(resp)
        assert ev["type"] == "error"
        assert "无法解析" in ev["error"]
        assert "UPSTREAM_SECRET" not in ev["error"]
        resp.close()
    finally:
        srv.shutdown(); up.shutdown()


def test_stream_upstream_error_frame_is_sanitized(tmp_path):
    state = UpstreamState("upstream_error_frame")
    up, upbase = start_upstream(state)
    srv, base = start_yang(tmp_path, upbase)
    try:
        body = {"stream": True, "messages":[{"role":"user", "content":"hi"}]}
        resp = urllib.request.urlopen(stream_req(base, body, {"Origin": ORIGIN}), timeout=5)
        ev = read_event(resp)
        assert ev == {"type":"error", "error":"模型流返回错误。"}
        assert "SECRET" not in ev["error"]
        resp.close()
    finally:
        srv.shutdown(); up.shutdown()


def test_stream_invalid_input_is_json_400(tmp_path):
    state = UpstreamState("barrier")
    up, upbase = start_upstream(state)
    srv, base = start_yang(tmp_path, upbase)
    try:
        body = {"stream": True, "messages":[{"role":"hacker", "content":"hi"}]}
        try:
            urllib.request.urlopen(stream_req(base, body, {"Origin": ORIGIN}), timeout=5)
            assert False
        except Exception as e:
            assert getattr(e, "code", None) == 400
            raw = e.read().decode()
            assert "role" in raw
        assert state.payloads == []
    finally:
        srv.shutdown(); up.shutdown()
