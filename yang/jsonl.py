"""yang.jsonl v3 —— 和前端 `yangdata.js` 必须逐字节一致的那一半。

改这里就得改 `web/src/yangdata.js`，反过来也一样。两边算出来的指纹不一样，
是最难查的一类 bug，所以 `tests/test_jsonl.py` 里有一条跨语言对照。

AES-GCM 不在标准库里。加密文件需要 `cryptography`；没装就明说读不了，
不自己手搓密码学。
"""
import base64
import hashlib
import hmac
import json
import os
import time

FMT = "yang.jsonl"
V = 3
KDF_ITER = 210000
MAX = {"title": 200, "seed": 2000, "now": 20000, "why": 20000,
       "q": 1000, "a": 20000, "grew": 500, "recs": 20000}
KINDS = ("ask", "angle", "collide", "note")
T0 = 1420070400000          # 2015-01-01


# ---------- 编码 ----------
def b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def unb64(s):
    if not isinstance(s, str):
        return None
    try:
        return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
    except Exception:
        return None


def canon(x):
    """和 JS 的 canon 同构：键排序、无空白、非 ASCII 不转义。"""
    if x is None or isinstance(x, (bool, int, float, str)):
        return json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    if isinstance(x, list):
        return "[" + ",".join(canon(v) for v in x) + "]"
    ks = sorted(x)
    return "{" + ",".join(json.dumps(k, ensure_ascii=False, separators=(",", ":"))
                          + ":" + canon(x[k]) for k in ks) + "}"


def _sha(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.digest()


def line_tag(salt, obj):
    o = {k: v for k, v in obj.items() if k != "h"}
    return _sha(salt, b"r", canon(o).encode()).hex()[:16]


def file_tag(salt, lines):
    return _sha(salt, b"f", "\n".join(lines).encode()).hex()


# ---------- 记录 ----------
def records(state, keep_keys=False):
    out = []
    for i in state.get("ideas", []):
        out.append({"t": "idea", "id": i["id"], "title": i["title"],
                    "seed": i.get("seed", ""), "now": i.get("now", ""),
                    "created": int(i["created"]),
                    "grew": [{"kind": g["kind"], "q": g["q"], "a": g["a"],
                              "at": int(g["at"]), "by": g.get("by", "")}
                             | ({"with": g["with"]} if g.get("with") else {})
                             for g in i.get("grew", [])]})
    for s in state.get("sparks", []):
        out.append({"t": "spark", "id": s["id"], "text": s["text"], "at": int(s["at"])})
    for x in state.get("cold", []):
        out.append({"t": "cold", "id": x["id"], "title": x["title"],
                    "why": x["why"], "at": int(x["at"])})
    conf = state.get("conf")
    if conf:
        c = json.loads(json.dumps(conf, ensure_ascii=False))
        for m in c.get("models", []):
            if not keep_keys:
                m["key"] = ""
                m["keyDropped"] = True
        c["t"] = "conf"
        out.append(c)
    return out


def export(state, password=None):
    salt = os.urandom(16)
    recs = records(state, keep_keys=bool(password))
    key = _derive(password, salt) if password else None
    lines, counts = [], {"idea": 0, "spark": 0, "cold": 0, "conf": 0}
    for r in recs:
        counts[r["t"]] = counts.get(r["t"], 0) + 1
        if key:
            iv = os.urandom(12)
            ct = _seal(key, iv, salt, canon(r).encode())
            e = {"t": "enc", "iv": b64(iv), "ct": b64(ct)}
            e["h"] = line_tag(salt, e)
            lines.append(json.dumps(e, ensure_ascii=False, separators=(",", ":")))
        else:
            r["h"] = line_tag(salt, r)
            lines.append(json.dumps(r, ensure_ascii=False, separators=(",", ":")))
    head = {"t": "head", "fmt": FMT, "v": V, "app": "养想法",
            "at": int(time.time() * 1000),
            "enc": "aes-gcm-256" if key else "none",
            "salt": b64(salt), "counts": counts, "keys": bool(password),
            "digest": file_tag(salt, lines)}
    if key:
        head["kdf"] = {"name": "PBKDF2", "hash": "SHA-256", "iter": KDF_ITER}
    return json.dumps(head, ensure_ascii=False, separators=(",", ":")) + "\n" \
        + "\n".join(lines) + "\n"


# ---------- 加密（可选依赖） ----------
def _aead():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return AESGCM
    except Exception:
        return None


def _derive(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, KDF_ITER, 32)


def _seal(key, iv, salt, pt):
    A = _aead()
    if not A:
        raise RuntimeError("要写加密文件得先装 cryptography：pip install cryptography")
    return A(key).encrypt(iv, pt, salt)


def _open(key, iv, salt, ct):
    A = _aead()
    if not A:
        raise RuntimeError("这份文件是加密的，读它需要 cryptography：pip install cryptography")
    return A(key).decrypt(iv, ct, salt)


# ---------- 校验 ----------
def _is_id(v):
    return isinstance(v, str) and 1 <= len(v) <= 64 and all(
        ch.isalnum() and ch.isascii() or ch in "-_" for ch in v)


def _is_ts(v):
    return isinstance(v, int) and not isinstance(v, bool) and \
        T0 <= v <= int(time.time() * 1000) + 2 * 86400000


def _s(v, m):
    return isinstance(v, str) and len(v) <= m


def check_record(r, ln):
    e = []

    def bad(m):
        e.append({"line": ln, "msg": m})
    if not isinstance(r, dict):
        bad("这一行不是一条记录。")
        return e
    t = r.get("t")
    if t == "idea":
        if not _is_id(r.get("id")):
            bad("想法的 id 不对（只能是字母、数字、- 和 _，1–64 位）。")
        if not _s(r.get("title"), MAX["title"]) or not str(r.get("title", "")).strip():
            bad("想法缺标题，或标题超过 %d 字。" % MAX["title"])
        if not _s(r.get("seed", ""), MAX["seed"]):
            bad("「最初那句」不是文本，或超过 %d 字。" % MAX["seed"])
        if not _s(r.get("now", ""), MAX["now"]):
            bad("「现在它是什么」不是文本，或超过 %d 字。" % MAX["now"])
        if not _is_ts(r.get("created")):
            bad("想法的创建时间不是一个说得通的时间戳。")
        g = r.get("grew")
        if not isinstance(g, list):
            bad("生长记录不是一个列表。")
        elif len(g) > MAX["grew"]:
            bad("生长记录超过 %d 条。" % MAX["grew"])
        else:
            for k, x in enumerate(g):
                at = "第 %d 条生长记录" % (k + 1)
                if not isinstance(x, dict):
                    bad(at + "不是一条记录。")
                    continue
                if x.get("kind") not in KINDS:
                    bad(at + "的类型「%s」不认识，只能是 %s。" % (x.get("kind"), " / ".join(KINDS)))
                if not _s(x.get("q"), MAX["q"]) or not str(x.get("q", "")).strip():
                    bad(at + "没有问题原文。")
                if not _s(x.get("a"), MAX["a"]) or not str(x.get("a", "")).strip():
                    bad(at + "没有你的回答。")
                if not _is_ts(x.get("at")):
                    bad(at + "的时间不对。")
    elif t == "spark":
        if not _is_id(r.get("id")):
            bad("念头的 id 不对。")
        if not _s(r.get("text"), MAX["seed"]) or not str(r.get("text", "")).strip():
            bad("念头是空的，或超过 %d 字。" % MAX["seed"])
        if not _is_ts(r.get("at")):
            bad("念头的时间不对。")
    elif t == "cold":
        if not _is_id(r.get("id")):
            bad("凉了的想法 id 不对。")
        if not _s(r.get("title"), MAX["title"]) or not str(r.get("title", "")).strip():
            bad("凉了的想法缺标题。")
        if not _s(r.get("why"), MAX["why"]) or not str(r.get("why", "")).strip():
            bad("缺「为什么凉了」——这一句是这条记录里最值钱的部分，不能空。")
        if not _is_ts(r.get("at")):
            bad("时间不对。")
    elif t == "conf":
        ms = r.get("models")
        if ms is not None and not isinstance(ms, list):
            bad("模型配置不是一个列表。")
        for k, m in enumerate(ms or []):
            if not isinstance(m, dict):
                bad("第 %d 个模型不是一条配置。" % (k + 1))
                continue
            if not _s(m.get("name"), 120) or not m.get("name"):
                bad("第 %d 个模型没有名字。" % (k + 1))
            b = m.get("base", "")
            if b and not (isinstance(b, str) and b.lower().startswith(("http://", "https://"))):
                bad("第 %d 个模型的地址不是 http/https，不收。" % (k + 1))
    else:
        bad("不认识的记录类型「%s」。" % (t,))
    return e


def parse(text, password=None):
    """只读不写。返回 {ok, head, recs, counts, errors, warnings}。"""
    errors, warnings = [], []

    def fail(m):
        errors.append({"line": 0, "msg": m})
        return {"ok": False, "errors": errors, "warnings": warnings}

    if not isinstance(text, str) or not text.strip():
        return fail("文件是空的。")
    if len(text) > 40 * 1024 * 1024:
        return fail("文件超过 40MB，先确认没选错文件。")
    raw = [l for l in text.replace("\r\n", "\n").split("\n") if l.strip()]
    try:
        head = json.loads(raw[0])
    except Exception:
        return fail("第一行不是 JSON。这份文件多半不是养想法导出的。")
    if not isinstance(head, dict) or head.get("t") != "head" or head.get("fmt") != FMT:
        return fail("这不是养想法的导出文件（第一行没有 %s 的标记）。" % FMT)
    v = head.get("v")
    if not isinstance(v, int) or v < 1:
        return fail("文件没写版本号，不敢导。")
    if v > V:
        return fail("这份文件是更新版本的养想法导出的（v%d），这一版只认到 v%d。先升级再导入。" % (v, V))
    salt = unb64(head.get("salt", ""))
    if not salt or len(salt) < 16:
        return fail("文件里的盐值不对或缺失，验不了签名。")
    if head.get("enc") not in ("none", "aes-gcm-256"):
        return fail("不认识的加密方式「%s」。" % head.get("enc"))
    body = raw[1:]
    if len(body) > MAX["recs"]:
        return fail("记录超过 %d 条，先拆开再导。" % MAX["recs"])
    if file_tag(salt, body) != head.get("digest"):
        return fail("整份文件的指纹对不上。文件在导出之后被改过，或者传输时坏了。别导——找一份没动过的。")

    key = None
    if head["enc"] == "aes-gcm-256":
        if not password:
            return {"ok": False, "needPass": True, "head": head,
                    "errors": errors, "warnings": warnings}
        k = head.get("kdf") or {}
        if k.get("name") != "PBKDF2" or k.get("hash") != "SHA-256" \
                or not isinstance(k.get("iter"), int) or not 10000 <= k["iter"] <= 5000000:
            return fail("加密参数不对或被改过。")
        key = _derive(password, salt)

    recs, seen, counts = [], set(), {"idea": 0, "spark": 0, "cold": 0, "conf": 0}
    for i, ln_text in enumerate(body):
        ln = i + 2
        try:
            obj = json.loads(ln_text)
        except Exception:
            errors.append({"line": ln, "msg": "这一行不是 JSON。"})
            continue
        if not isinstance(obj, dict):
            errors.append({"line": ln, "msg": "这一行不是一条记录。"})
            continue
        if not hmac.compare_digest(str(obj.get("h", "")), line_tag(salt, obj)):
            errors.append({"line": ln, "msg": "这一行的指纹对不上，被改过。"})
            continue
        r = obj
        if obj.get("t") == "enc":
            if not key:
                errors.append({"line": ln, "msg": "这一行是加密的，但文件头说没加密。"})
                continue
            iv, ct = unb64(obj.get("iv", "")), unb64(obj.get("ct", ""))
            if not iv or len(iv) != 12 or not ct:
                errors.append({"line": ln, "msg": "加密块的格式不对。"})
                continue
            try:
                r = json.loads(_open(key, iv, salt, ct).decode())
            except RuntimeError as ex:
                return fail(str(ex))
            except Exception:
                return fail("口令不对，或者这份文件的加密内容被改过。"
                            "（AES-GCM 解不开就是解不开，没有「差一点」。）")
        elif key:
            errors.append({"line": ln, "msg": "文件头说加密了，但这一行是明文。"})
            continue
        es = check_record(r, ln)
        if es:
            errors.extend(es)
            continue
        if r["t"] != "conf":
            k2 = r["t"] + ":" + r["id"]
            if k2 in seen:
                errors.append({"line": ln, "msg": "id「%s」在文件里出现了不止一次。" % r["id"]})
                continue
            seen.add(k2)
        counts[r["t"]] = counts.get(r["t"], 0) + 1
        recs.append(r)

    for k in ("idea", "spark", "cold", "conf"):
        want = (head.get("counts") or {}).get(k)
        if isinstance(want, int) and want != counts[k]:
            warnings.append("文件头说有 %d 条 %s，实际读出 %d 条。" % (want, k, counts[k]))
    if head["enc"] == "none" and head.get("keys"):
        warnings.append("文件头说带了模型钥匙，但它没加密。不该这样导。")
    if head["enc"] == "none":
        warnings.append("这份是明文导出，模型钥匙没有带出来——导入后要重新填一次。")

    return {"ok": not errors, "head": head, "recs": recs, "counts": counts,
            "errors": errors, "warnings": warnings}


def to_state(recs):
    st = {"ideas": [], "sparks": [], "cold": [], "conf": None}
    for r in recs:
        if r["t"] == "idea":
            st["ideas"].append({k: r[k] for k in ("id", "title", "seed", "now", "created", "grew")})
        elif r["t"] == "spark":
            st["sparks"].append({k: r[k] for k in ("id", "text", "at")})
        elif r["t"] == "cold":
            st["cold"].append({k: r[k] for k in ("id", "title", "why", "at")})
        elif r["t"] == "conf":
            c = dict(r)
            c.pop("t", None)
            c.pop("h", None)
            st["conf"] = c
    return st
