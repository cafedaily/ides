"""OpenAI 兼容端点的代理。

前端把 prompt 发给 /api/chat，后端从库里读模型配置，替它转发到
配好的那个 OpenAI 兼容地址（Ollama、Groq、DeepSeek、vLLM、……）。

这样做而不是前端直连，有两个原因：
1. 绕过 CORS——浏览器不让 JS 直接调大部分外部 API；
2. API key 留在服务端，不用塞进前端代码里。
"""
import json
import urllib.request
import urllib.error

from . import db as _db


def _model(c, action=None):
    conf = _db.kv_get(c, "conf", {})
    models = conf.get("models") if isinstance(conf, dict) else None
    if not models:
        return None, None

    if not action or not isinstance(conf, dict):
        return models[0], None

    route = conf.get("route")
    if not isinstance(route, dict) or action not in route:
        return models[0], None

    mid = route.get(action)
    if not mid:
        return models[0], None

    for m in models:
        if isinstance(m, dict) and m.get("id") == mid:
            return m, None

    return None, "动作 %s 配的模型 ID %s 不存在。请在「数据」页重新选择模型。" % (action, mid)


def complete(c, body):
    m, err = _model(c, body.get("action"))
    if err:
        return {"ok": False, "error": err}
    if not m:
        return {"ok": False, "error": "没有配模型。在「数据」页加一个。"}

    base = (m.get("base") or "").rstrip("/")
    key = m.get("key") or ""
    model = m.get("model") or m.get("name") or ""
    if not base:
        return {"ok": False, "error": "模型缺 base URL。"}

    messages = body.get("messages") or []
    if not messages:
        return {"ok": False, "error": "没有 messages。"}

    want_json = body.get("json", False)

    payload = {
        "model": model,
        "messages": messages,
        "temperature": body.get("temperature", 0.7),
        "max_tokens": body.get("max_tokens", 800),
    }
    if want_json:
        payload["response_format"] = {"type": "json_object"}

    url = base + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key

    data = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode()[:500]
        except Exception:
            pass
        return {"ok": False, "error": "模型返回 HTTP %d：%s" % (e.code, detail)}
    except urllib.error.URLError as e:
        return {"ok": False, "error": "连不上模型：%s" % e.reason}
    except Exception as e:
        return {"ok": False, "error": "调模型出错：%s" % e}

    choices = result.get("choices") or []
    if not choices:
        return {"ok": False, "error": "模型没有返回结果。"}

    text = choices[0].get("message", {}).get("content", "")
    return {"ok": True, "text": text}
