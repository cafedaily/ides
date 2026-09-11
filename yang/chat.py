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


class ChatInputError(Exception):
    pass


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


def _clean_messages(messages):
    if not isinstance(messages, list) or not messages:
        raise ChatInputError("没有 messages。")
    out = []
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise ChatInputError("messages[%d] 不是对象。" % i)
        role = msg.get("role")
        content = msg.get("content")
        if role not in ("system", "user", "assistant", "tool"):
            raise ChatInputError("messages[%d].role 不支持。" % i)
        if not isinstance(content, str):
            raise ChatInputError("messages[%d].content 必须是字符串。" % i)
        out.append({"role": role, "content": content})
    return out


def _num(body, key, default, lo, hi):
    val = body.get(key, default)
    try:
        if isinstance(default, int):
            n = int(val)
        else:
            n = float(val)
    except Exception:
        raise ChatInputError("%s 不是有效数字。" % key)
    if n < lo or n > hi:
        raise ChatInputError("%s 超出范围。" % key)
    return n


def _prepare(c, body, stream=False):
    if not isinstance(body, dict):
        raise ChatInputError("要一个 JSON 对象。")
    m, err = _model(c, body.get("action"))
    if err:
        raise ChatInputError(err)
    if not m:
        raise ChatInputError("没有配模型。在「数据」页加一个。")
    if not isinstance(m, dict):
        raise ChatInputError("模型配置不对。")

    base = (m.get("base") or "").rstrip("/")
    key = m.get("key") or ""
    model = m.get("model") or m.get("name") or ""
    if not base:
        raise ChatInputError("模型缺 base URL。")
    if not model:
        raise ChatInputError("模型缺 model。")

    payload = {
        "model": model,
        "messages": _clean_messages(body.get("messages")),
        "temperature": _num(body, "temperature", 0.7, 0, 2),
        "max_tokens": _num(body, "max_tokens", 800, 1, 200000),
    }
    if body.get("json", False):
        payload["response_format"] = {"type": "json_object"}
    if stream:
        payload["stream"] = True

    url = base + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    data = json.dumps(payload, ensure_ascii=False).encode()
    return urllib.request.Request(url, data=data, headers=headers, method="POST")


def _safe_upstream_error(prefix="模型调用失败"):
    return prefix + "。"


def complete(c, body):
    try:
        req = _prepare(c, body, stream=False)
    except ChatInputError as e:
        return {"ok": False, "error": str(e)}

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": "模型返回 HTTP %d。" % e.code}
    except urllib.error.URLError:
        return {"ok": False, "error": "连不上模型。"}
    except Exception:
        return {"ok": False, "error": _safe_upstream_error("调模型出错")}

    choices = result.get("choices") if isinstance(result, dict) else None
    if not choices:
        return {"ok": False, "error": "模型没有返回结果。"}

    text = choices[0].get("message", {}).get("content", "")
    return {"ok": True, "text": text}


def _iter_sse_data(resp):
    data_lines = []
    while True:
        line = resp.readline()
        if line == b"":
            if data_lines:
                yield b"\n".join(data_lines).decode("utf-8")
            return
        if line.endswith(b"\n"):
            line = line[:-1]
        if line.endswith(b"\r"):
            line = line[:-1]
        if line == b"":
            if data_lines:
                yield b"\n".join(data_lines).decode("utf-8")
                data_lines = []
            continue
        if line.startswith(b":"):
            continue
        if line.startswith(b"data:"):
            val = line[5:]
            if val.startswith(b" "):
                val = val[1:]
            data_lines.append(val)


def _delta_text(obj):
    choices = obj.get("choices") if isinstance(obj, dict) else None
    if not choices:
        return ""
    ch = choices[0] if isinstance(choices[0], dict) else {}
    delta = ch.get("delta") if isinstance(ch.get("delta"), dict) else {}
    text = delta.get("content")
    if text is None:
        msg = ch.get("message") if isinstance(ch.get("message"), dict) else {}
        text = msg.get("content")
    return text if isinstance(text, str) else ""


def stream_events(c, body):
    """Return (ok, generator-or-error) for OpenAI-compatible streaming chat."""
    try:
        req = _prepare(c, body, stream=True)
    except ChatInputError as e:
        return False, str(e)

    def gen():
        resp = None
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            saw_done = False
            for data in _iter_sse_data(resp):
                if data.strip() == "[DONE]":
                    saw_done = True
                    yield {"type": "done"}
                    break
                try:
                    obj = json.loads(data)
                except Exception:
                    yield {"type": "error", "error": "模型返回了无法解析的流。"}
                    return
                if isinstance(obj, dict) and obj.get("error"):
                    yield {"type": "error", "error": "模型流返回错误。"}
                    return
                text = _delta_text(obj)
                if text:
                    yield {"type": "delta", "text": text}
                choices = obj.get("choices") if isinstance(obj, dict) else None
                if choices and isinstance(choices[0], dict) and choices[0].get("finish_reason"):
                    saw_done = True
                    yield {"type": "done"}
                    break
            if not saw_done:
                yield {"type": "done"}
        except urllib.error.HTTPError as e:
            yield {"type": "error", "error": "模型返回 HTTP %d。" % e.code}
        except urllib.error.URLError:
            yield {"type": "error", "error": "连不上模型。"}
        except GeneratorExit:
            raise
        except Exception:
            yield {"type": "error", "error": _safe_upstream_error("调模型出错")}
        finally:
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass

    return True, gen()
