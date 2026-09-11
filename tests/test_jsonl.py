import copy
import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yang import demo, jsonl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, "web", "src", "yangdata.js")


def st():
    s = demo.state()
    s["conf"] = {"models": [{"id": "m0", "name": "本地 qwen2.5:14b", "kind": "ollama",
                             "base": "http://localhost:11434/v1", "key": "sk-secret-abc",
                             "model": "qwen2.5:14b"}],
                 "route": {"ask": "m0"}, "sharp": "normal", "len": "one",
                 "seeGrew": True, "seeOthers": True}
    return s


# ---------- 往返 ----------
def test_roundtrip_plain():
    txt = jsonl.export(st())
    r = jsonl.parse(txt)
    assert r["ok"], r["errors"]
    back = jsonl.to_state(r["recs"])
    assert len(back["ideas"]) == 6 and len(back["sparks"]) == 3 and len(back["cold"]) == 3


def test_plain_export_drops_the_key():
    txt = jsonl.export(st())
    assert "sk-secret-abc" not in txt
    r = jsonl.parse(txt)
    conf = jsonl.to_state(r["recs"])["conf"]
    assert conf["models"][0]["key"] == "" and conf["models"][0]["keyDropped"] is True
    assert any("钥匙" in w for w in r["warnings"])


def test_collide_with_survives():
    txt = jsonl.export(st())
    back = jsonl.to_state(jsonl.parse(txt)["recs"])
    cats = [i for i in back["ideas"] if i["id"] == "i-cats"][0]
    assert cats["grew"][0]["with"] == "i-rain", "星图的线就是从这个字段来的"


# ---------- 加盐签名 ----------
def test_salt_differs_every_export():
    a = json.loads(jsonl.export(st()).split("\n")[0])
    b = json.loads(jsonl.export(st()).split("\n")[0])
    assert a["salt"] != b["salt"] and a["digest"] != b["digest"]


def test_one_changed_character_is_caught():
    txt = jsonl.export(st()).replace("晴天锁门", "阴天锁门")
    r = jsonl.parse(txt)
    assert not r["ok"] and "指纹对不上" in r["errors"][0]["msg"]


def test_deleting_a_line_is_caught():
    lines = jsonl.export(st()).strip().split("\n")
    r = jsonl.parse("\n".join([lines[0]] + lines[2:]))
    assert not r["ok"]


def test_recomputed_file_digest_still_caught_by_line_tag():
    """把整份指纹重算一遍也没用——每行还有自己的指纹，而且会指出是第几行。"""
    lines = jsonl.export(st()).strip().split("\n")
    head = json.loads(lines[0])
    salt = jsonl.unb64(head["salt"])
    bad = json.loads(lines[2])
    bad["title"] = "被改过的标题"
    body = [lines[1], json.dumps(bad, ensure_ascii=False, separators=(",", ":"))] + lines[3:]
    head["digest"] = jsonl.file_tag(salt, body)
    r = jsonl.parse(json.dumps(head, ensure_ascii=False, separators=(",", ":"))
                    + "\n" + "\n".join(body))
    assert not r["ok"]
    assert "这一行的指纹对不上" in r["errors"][0]["msg"]
    assert r["errors"][0]["line"] == 3


def test_canon_ignores_key_order():
    assert jsonl.canon({"b": 1, "a": {"d": 2, "c": 3}}) == jsonl.canon({"a": {"c": 3, "d": 2}, "b": 1})


# ---------- 版本与格式 ----------
def test_future_version_refused_by_number():
    lines = jsonl.export(st()).strip().split("\n")
    h = json.loads(lines[0]); h["v"] = 99
    r = jsonl.parse(json.dumps(h, ensure_ascii=False) + "\n" + "\n".join(lines[1:]))
    assert not r["ok"] and "v99" in r["errors"][0]["msg"]


def test_not_our_format():
    r = jsonl.parse('{"hello":1}\n')
    assert not r["ok"] and jsonl.FMT in r["errors"][0]["msg"]


def test_empty_file():
    assert not jsonl.parse("")["ok"]


def test_garbage_first_line():
    assert not jsonl.parse("这不是 JSON\n")["ok"]


# ---------- 字段校验 ----------
def ck(rec):
    return [e["msg"] for e in jsonl.check_record(rec, 7)]


def test_cold_must_carry_why():
    now = int(time.time() * 1000)
    assert any("最值钱" in m for m in ck({"t": "cold", "id": "c9", "title": "x", "why": "", "at": now}))


def test_unknown_kind_lists_the_valid_ones():
    now = int(time.time() * 1000)
    msgs = ck({"t": "idea", "id": "a", "title": "t", "seed": "", "now": "", "created": now,
               "grew": [{"kind": "梦到", "q": "q", "a": "a", "at": now}]})
    assert any("ask / angle / collide / note" in m for m in msgs)


def test_bad_id_refused():
    now = int(time.time() * 1000)
    assert any("id 不对" in m for m in ck({"t": "idea", "id": "有中文", "title": "t", "seed": "",
                                          "now": "", "created": now, "grew": []}))


def test_absurd_timestamp_refused():
    assert any("时间不对" in m for m in ck({"t": "cold", "id": "c1", "title": "t",
                                          "why": "w", "at": 99999999999999}))


def test_javascript_url_refused():
    assert any("http/https" in m for m in
               ck({"t": "conf", "models": [{"name": "x", "base": "javascript:alert(1)"}]}))


def test_duplicate_id_refused():
    s = st()
    s["ideas"].append(copy.deepcopy(s["ideas"][0]))
    r = jsonl.parse(jsonl.export(s))
    assert not r["ok"] and any("不止一次" in e["msg"] for e in r["errors"])


# ---------- 跨语言 ----------
def _node():
    """没有 node 就跳过——**不能当通过**。这两条是「两边指纹不一致」这类 bug
    的唯一防线，把它们记成绿勾，等于在报告里撒谎。"""
    from shutil import which
    import unittest
    n = which("node")
    if not n:
        raise unittest.SkipTest("没装 node，跨语言对照没跑")
    if not os.path.exists(JS):
        raise unittest.SkipTest("找不到 web/src/yangdata.js")
    return n


def test_python_reads_what_javascript_wrote(tmp_path):
    """两边的签名必须逐字节一致。这条测试就是为了这个存在的。"""
    node = _node()
    out = tmp_path / "from_js.jsonl"
    script = tmp_path / "e.mjs"
    script.write_text("""
globalThis.btoa=s=>Buffer.from(s,'binary').toString('base64');
globalThis.atob=s=>Buffer.from(s,'base64').toString('binary');
await import(%s);
const fs=await import('fs');
const st=JSON.parse(fs.readFileSync(%s,'utf8'));
const e=await globalThis.YD.exportJSONL(st,{});
fs.writeFileSync(%s, e.text);
""" % (json.dumps(pathlib.Path(JS).as_uri()), json.dumps(str(tmp_path / "st.json")), json.dumps(str(out))),
        encoding="utf-8")
    (tmp_path / "st.json").write_text(json.dumps(st(), ensure_ascii=False), encoding="utf-8")
    p = subprocess.run([node, str(script)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    r = jsonl.parse(out.read_text(encoding="utf-8"))
    assert r["ok"], r["errors"]
    assert len(r["recs"]) == 13


def test_javascript_reads_what_python_wrote(tmp_path):
    node = _node()
    f = tmp_path / "from_py.jsonl"
    f.write_text(jsonl.export(st()), encoding="utf-8")
    script = tmp_path / "v.mjs"
    script.write_text("""
globalThis.btoa=s=>Buffer.from(s,'binary').toString('base64');
globalThis.atob=s=>Buffer.from(s,'base64').toString('binary');
await import(%s);
const fs=await import('fs');
const r=await globalThis.YD.parseJSONL(fs.readFileSync(%s,'utf8'),{});
if(!r.ok){ console.error(JSON.stringify(r.errors)); process.exit(1); }
console.log(r.recs.length);
""" % (json.dumps(pathlib.Path(JS).as_uri()), json.dumps(str(f))), encoding="utf-8")
    p = subprocess.run([node, str(script)], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert p.stdout.strip() == "13"
