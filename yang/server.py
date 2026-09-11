"""标准库 HTTP 服务。默认只听 127.0.0.1。"""
import json
import mimetypes
import os
import posixpath
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import api, auth, db

MAX_BODY = 64 * 1024 * 1024
SOCKET_TIMEOUT = 15
_LOGIN_THROTTLE = auth.FailureThrottle(limit=5, window_seconds=60, max_keys=2048)


def _peer_key(handler):
    return handler.client_address[0] if handler.client_address else "unknown"


def _safe_policy(host="127.0.0.1", unsafe_no_auth=False):
    if unsafe_no_auth:
        env = dict(os.environ)
        env[auth.PRODUCTION_ENV] = "0"
        return auth.load_policy_from_env(env, host="127.0.0.1")
    return auth.load_policy_from_env(host=host)


def make(dbpath, webroot, policy=None, host="127.0.0.1", unsafe_no_auth=False):
    conn_path = dbpath
    auth_policy = policy or _safe_policy(host, unsafe_no_auth=unsafe_no_auth)
    require_auth = auth_policy.has_token or auth_policy.production
    web_root_path = Path(webroot).resolve()

    class H(BaseHTTPRequestHandler):
        server_version = "yang"
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(SOCKET_TIMEOUT)

        def log_message(self, fmt, *a):
            print("  %s %s" % (self.command, self.path.split("?")[0]))

        def _json(self, code, obj, headers=None):
            raw = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(raw)

        def _read_json_body(self):
            vals = self.headers.get_all("Content-Length") or []
            if len(vals) > 1:
                raise api.Err(400, "Content-Length 不对。")
            text = vals[0].strip() if vals else "0"
            try:
                n = int(text)
            except Exception:
                raise api.Err(400, "Content-Length 不对。")
            if n < 0:
                raise api.Err(400, "Content-Length 不对。")
            if n > MAX_BODY:
                raise api.Err(413, "请求体太大。")
            raw = self.rfile.read(n) if n else b""
            try:
                return json.loads(raw.decode() or "null")
            except Exception:
                raise api.Err(400, "请求体不是 JSON。")

        def _has_bearer(self):
            return auth_policy.validate_bearer(self.headers.get("Authorization"))

        def _has_cookie(self):
            return auth_policy.verify_session_cookie(self.headers.get("Cookie"))

        def _authenticated(self):
            if not require_auth:
                return True
            return self._has_bearer() or self._has_cookie()

        def _origin_ok_for_cookie_mutation(self):
            if self._has_bearer():
                return True
            if not self._has_cookie():
                return True
            return auth.origin_allowed(self.headers.get("Origin"), auth_policy.public_origin)

        def _login(self, query, body):
            if query:
                return self._json(400, {"error": "登录口令只能放在 JSON 请求体里。"})
            retry = _LOGIN_THROTTLE.retry_after(_peer_key(self))
            if retry > 0:
                return self._json(429, {"error": "尝试太频繁，请稍后再试。"}, {"Retry-After": str(retry)})
            if not isinstance(body, dict) or set(body) - {"token"} or not isinstance(body.get("token"), str):
                _LOGIN_THROTTLE.record_failure(_peer_key(self))
                return self._json(401, {"error": "认证失败。"})
            if not auth_policy.validate_token(body.get("token")):
                retry = _LOGIN_THROTTLE.record_failure(_peer_key(self))
                headers = {"Retry-After": str(retry)} if retry > 0 else None
                return self._json(401, {"error": "认证失败。"}, headers)
            _LOGIN_THROTTLE.reset(_peer_key(self))
            return self._json(200, {"ok": True, "authenticated": True},
                              {"Set-Cookie": auth_policy.make_session_cookie()})

        def _logout(self):
            return self._json(200, {"ok": True, "authenticated": False},
                              {"Set-Cookie": auth_policy.clear_session_cookie()})

        def _api(self, method):
            u = urllib.parse.urlsplit(self.path)
            q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
            body = None
            try:
                if method == "POST":
                    body = self._read_json_body()
                if (method, u.path) == ("POST", "/api/login"):
                    if not auth_policy.has_token:
                        return self._json(503, {"error": "认证未配置。"})
                    if not auth.origin_allowed(self.headers.get("Origin"), auth_policy.public_origin):
                        return self._json(403, {"error": "来源不允许。"})
                    return self._login(q, body)
                if (method, u.path) == ("POST", "/api/logout"):
                    if not auth.origin_allowed(self.headers.get("Origin"), auth_policy.public_origin):
                        return self._json(403, {"error": "来源不允许。"})
                    return self._logout()
                route_key = (method, u.path)
                if route_key == ("GET", "/api/health") and not self._authenticated():
                    return self._json(200, api.public_health(None, None, None))
                if route_key not in api.PUBLIC_ROUTES and not self._authenticated():
                    return self._json(401, {"error": "需要认证。"})
                if route_key in api.MUTATION_ROUTES and not self._origin_ok_for_cookie_mutation():
                    return self._json(403, {"error": "来源不允许。"})
                c = db.connect(conn_path)
                try:
                    out = api.dispatch(c, method, u.path, q, body)
                    c.commit()
                    self._json(200, out)
                finally:
                    c.close()
            except api.Err as e:
                self._json(e.code, {"error": e.msg})
            except Exception:
                traceback.print_exc()
                self._json(500, {"error": "服务端出错了。"})

        def _static(self):
            u = urllib.parse.urlsplit(self.path)
            p = urllib.parse.unquote(u.path)
            if p in ("/", ""):
                p = "/index.html"
            rel = posixpath.normpath(p).lstrip("/")
            try:
                full = (web_root_path / rel).resolve()
                full.relative_to(web_root_path)
            except Exception:
                return self._json(404, {"error": "没有这个文件。"})
            if not full.is_file():
                return self._json(404, {"error": "没有这个文件。"})
            ctype = mimetypes.guess_type(str(full))[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
            raw = full.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path.startswith("/api/"):
                return self._api("GET")
            self._static()

        def do_POST(self):
            if self.path.startswith("/api/"):
                return self._api("POST")
            self._json(404, {"error": "只有 /api/ 收 POST。"})

    return H


def serve(dbpath, webroot, host="127.0.0.1", port=8730, unsafe_no_auth=False):
    policy = _safe_policy(host, unsafe_no_auth=unsafe_no_auth)
    if not policy.has_token and not auth.is_loopback_host(host) and not unsafe_no_auth:
        raise auth.AuthConfigError("非本机地址启动必须设置强 YANG_AUTH_TOKEN。")
    H = make(dbpath, webroot, policy=policy, host=host, unsafe_no_auth=unsafe_no_auth)
    srv = ThreadingHTTPServer((host, port), H)
    where = "http://%s:%d/" % ("localhost" if host == "127.0.0.1" else host, port)
    print("库    %s" % os.path.abspath(dbpath))
    print("网页  %s" % os.path.abspath(webroot))
    print("地址  %s" % where)
    if host not in ("127.0.0.1", "localhost"):
        print("！ 你把它开在了 %s——这台机器以外的人也能连上。请确认认证已配置。" % host)
    print("Ctrl-C 停。")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n停了。")
