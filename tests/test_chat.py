import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yang import chat, db


class FakeResp:
    def __init__(self, text):
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._text.encode()


def fresh(tmp_path, conf):
    c = db.connect(str(tmp_path / "chat.db"))
    db.kv_set(c, "conf", conf)
    c.commit()
    return c


def body(action=None):
    b = {"messages": [{"role": "user", "content": "hi"}]}
    if action is not None:
        b["action"] = action
    return b


def capture_call(text="ok"):
    calls = []
    old = chat.urllib.request.urlopen

    def fake(req, timeout=60):
        calls.append({
            "url": req.full_url,
            "headers": dict(req.header_items()),
            "payload": json.loads(req.data.decode()),
            "timeout": timeout,
        })
        return FakeResp(json.dumps({"choices": [{"message": {"content": text}}]}))

    chat.urllib.request.urlopen = fake
    return calls, old


def restore_urlopen(old):
    chat.urllib.request.urlopen = old


def test_chat_uses_first_model_without_action_or_route(tmp_path):
    c = fresh(tmp_path, {"models": [
        {"id": "slow", "name": "Slow", "base": "https://slow.example/v1", "model": "slow-model"},
        {"id": "fast", "name": "Fast", "base": "https://fast.example/v1", "model": "fast-model"},
    ]})
    calls, old = capture_call()
    try:
        r = chat.complete(c, body())
    finally:
        restore_urlopen(old)

    assert r == {"ok": True, "text": "ok"}
    assert calls[0]["url"] == "https://slow.example/v1/chat/completions"
    assert calls[0]["payload"]["model"] == "slow-model"


def test_chat_routes_ask_and_name_to_configured_models(tmp_path):
    c = fresh(tmp_path, {
        "models": [
            {"id": "general", "name": "General", "base": "https://general.example/v1", "model": "general-model"},
            {"id": "asker", "name": "Asker", "base": "https://ask.example/v1", "model": "ask-model"},
            {"id": "namer", "name": "Namer", "base": "https://name.example/v1", "model": "name-model"},
        ],
        "route": {"ask": "asker", "name": "namer"},
    })
    calls, old = capture_call()
    try:
        r1 = chat.complete(c, body("ask"))
        r2 = chat.complete(c, body("name"))
    finally:
        restore_urlopen(old)

    assert r1["ok"] and r2["ok"]
    assert calls[0]["url"] == "https://ask.example/v1/chat/completions"
    assert calls[0]["payload"]["model"] == "ask-model"
    assert calls[1]["url"] == "https://name.example/v1/chat/completions"
    assert calls[1]["payload"]["model"] == "name-model"


def test_chat_preserves_existing_route_keys(tmp_path):
    c = fresh(tmp_path, {
        "models": [
            {"id": "ask", "name": "Ask", "base": "https://ask.example/v1", "model": "ask-model"},
            {"id": "angle", "name": "Angle", "base": "https://angle.example/v1", "model": "angle-model"},
            {"id": "collide", "name": "Collide", "base": "https://collide.example/v1", "model": "collide-model"},
            {"id": "rewrite", "name": "Rewrite", "base": "https://rewrite.example/v1", "model": "rewrite-model"},
        ],
        "route": {"ask": "ask", "angle": "angle", "collide": "collide", "rewrite": "rewrite"},
    })
    calls, old = capture_call()
    try:
        for action in ["ask", "angle", "collide", "rewrite"]:
            r = chat.complete(c, body(action))
            assert r["ok"]
    finally:
        restore_urlopen(old)

    assert [call["payload"]["model"] for call in calls] == [
        "ask-model", "angle-model", "collide-model", "rewrite-model"
    ]


def test_chat_unknown_or_unrouted_action_falls_back_to_first_model(tmp_path):
    c = fresh(tmp_path, {
        "models": [
            {"id": "default", "name": "Default", "base": "https://default.example/v1", "model": "default-model"},
            {"id": "asker", "name": "Asker", "base": "https://ask.example/v1", "model": "ask-model"},
        ],
        "route": {"ask": "asker"},
    })
    calls, old = capture_call()
    try:
        r = chat.complete(c, body("name"))
    finally:
        restore_urlopen(old)

    assert r["ok"]
    assert calls[0]["url"] == "https://default.example/v1/chat/completions"
    assert calls[0]["payload"]["model"] == "default-model"


def test_chat_invalid_configured_model_id_is_clear_error(tmp_path):
    c = fresh(tmp_path, {
        "models": [
            {"id": "default", "name": "Default", "base": "https://default.example/v1", "model": "default-model"},
        ],
        "route": {"ask": "missing"},
    })
    calls, old = capture_call()
    try:
        r = chat.complete(c, body("ask"))
    finally:
        restore_urlopen(old)

    assert not r["ok"]
    assert "ask" in r["error"]
    assert "missing" in r["error"]
    assert "不存在" in r["error"]
    assert calls == []
