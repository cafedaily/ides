"""标准库 HTTP 服务。没有框架，起不来的可能性最小。

默认只听 127.0.0.1——这台机器以外的任何人都连不上。要改成对外，
必须显式 --host，并且它会当着你的面说一句这意味着什么。
"""
import json
import mimetypes
import os
import posixpath
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import api, db

MAX_BODY = 64 * 1024 * 1024


def make(dbpath, webroot):
    conn_path = dbpath

    class H(BaseHTTPRequestHandler):
        server_version = "yang"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *a):
            print("  %s %s" % (self.command, self.path.split("?")[0]))

        def _json(self, code, obj):
            raw = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _api(self, method):
            u = urllib.parse.urlsplit(self.path)
            q = urllib.parse.parse_qs(u.query)
            body = None
            if method == "POST":
                n = int(self.headers.get("Content-Length") or 0)
                if n > MAX_BODY:
                    return self._json(413, {"error": "请求体太大。"})
                raw = self.rfile.read(n) if n else b""
                try:
                    body = json.loads(raw.decode() or "null")
                except Exception:
                    return self._json(400, {"error": "请求体不是 JSON。"})
            c = db.connect(conn_path)
            try:
                out = api.dispatch(c, method, u.path, q, body)
                c.commit()
                self._json(200, out)
            except api.Err as e:
                self._json(e.code, {"error": e.msg})
            except Exception as e:                     # 不把栈吐给浏览器，但打在终端上
                import traceback
                traceback.print_exc()
                self._json(500, {"error": "服务端出错了：%s" % e})
            finally:
                c.close()

        def _static(self):
            u = urllib.parse.urlsplit(self.path)
            p = urllib.parse.unquote(u.path)
            if p in ("/", ""):
                p = "/index.html"
            p = posixpath.normpath(p).lstrip("/")
            full = os.path.join(webroot, p)
            if not os.path.abspath(full).startswith(os.path.abspath(webroot)) \
                    or not os.path.isfile(full):
                return self._json(404, {"error": "没有这个文件：/" + p})
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
            with open(full, "rb") as f:
                raw = f.read()
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


def serve(dbpath, webroot, host="127.0.0.1", port=8730):
    H = make(dbpath, webroot)
    srv = ThreadingHTTPServer((host, port), H)
    where = "http://%s:%d/" % ("localhost" if host == "127.0.0.1" else host, port)
    print("库    %s" % os.path.abspath(dbpath))
    print("网页  %s" % os.path.abspath(webroot))
    print("地址  %s" % where)
    if host not in ("127.0.0.1", "localhost"):
        print("！ 你把它开在了 %s——这台机器以外的人也能连上，而且没有任何认证。"
              "只在你信得过的网里这么干。" % host)
    print("Ctrl-C 停。")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n停了。")
