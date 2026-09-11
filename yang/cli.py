import argparse
import json
import os
import sys

from . import auth, db, jsonl, server, store

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_DB = os.environ.get("YANG_DB", os.path.join(os.path.expanduser("~"), ".yang", "yang.db"))
DEFAULT_WEB = os.environ.get("YANG_WEB", os.path.join(ROOT, "web"))


def main(argv=None):
    p = argparse.ArgumentParser("yang", description="养想法：本地库 + 关键词图谱")
    p.add_argument("--db", default=DEFAULT_DB)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="建库")
    a = sub.add_parser("import", help="导入一份 .jsonl 导出")
    a.add_argument("file")
    a.add_argument("--pass", dest="pw", default=None)
    a.add_argument("--mode", choices=["merge", "replace"], default="merge")
    a.add_argument("--dry", action="store_true", help="只验不写")
    e = sub.add_parser("export", help="导出到 stdout 或文件")
    e.add_argument("-o", "--out", default=None)
    e.add_argument("--pass", dest="pw", default=None)
    g = sub.add_parser("graph", help="建图并打印概况")
    g.add_argument("--json", action="store_true")
    b = sub.add_parser("bridges", help="列出跨维度的桥")
    b.add_argument("-n", type=int, default=10)
    c = sub.add_parser("path", help="看两个想法能不能串起来")
    c.add_argument("a")
    c.add_argument("b")
    s = sub.add_parser("serve", help="起服务")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8730)
    s.add_argument("--web", default=DEFAULT_WEB)
    s.add_argument("--unsafe-dev-no-auth", action="store_true",
                   help="只给临时开发用：允许无认证绑定非本机地址")

    ns = p.parse_args(argv)
    conn = db.connect(ns.db)

    if ns.cmd == "init":
        print("建好了：%s" % os.path.abspath(ns.db))

    elif ns.cmd == "import":
        r = jsonl.parse(open(ns.file, encoding="utf-8").read(), ns.pw)
        if r.get("needPass"):
            print("这份文件是加密的，加 --pass。"); return 2
        for w in r.get("warnings", []):
            print("· " + w)
        if not r["ok"]:
            print("没通过，%d 处问题：" % len(r["errors"]))
            for x in r["errors"][:20]:
                print("  %s%s" % (("第 %d 行：" % x["line"]) if x["line"] else "", x["msg"]))
            return 1
        print("验过了：%s" % json.dumps(r["counts"], ensure_ascii=False))
        if ns.dry:
            print("（--dry，没写库）"); return 0
        store.load_state(conn, jsonl.to_state(r["recs"]), ns.mode)
        store.rebuild(conn)
        print("导好了，图也重建了。")

    elif ns.cmd == "export":
        txt = jsonl.export(store.state(conn, include_keys=bool(ns.pw)), ns.pw)
        if ns.out:
            open(ns.out, "w", encoding="utf-8").write(txt)
            print("写到 %s（%d 字节）" % (ns.out, len(txt)))
        else:
            sys.stdout.write(txt)

    elif ns.cmd == "graph":
        gr = store.rebuild(conn)
        if ns.json:
            print(json.dumps({k: gr[k] for k in ("nodes", "edges", "sim", "cooc", "bridges")},
                             ensure_ascii=False))
            return 0
        nt = sum(1 for n in gr["nodes"] if n["type"] == "term")
        print("想法/念头/凉了的  %d" % (len(gr["nodes"]) - nt))
        print("词条              %d" % nt)
        print("想法—词条 边      %d" % len(gr["edges"]))
        print("词条共现          %d" % len(gr["cooc"]))
        print("想法相似          %d" % len(gr["sim"]))
        print("跨维度的桥        %d" % len(gr["bridges"]))
        if gr["sim"]:
            print("\n最像的两个：")
            for e in gr["sim"][:3]:
                print("  %.3f  %s ↔ %s  共有：%s" % (e["sim"], e["a"], e["b"], " ".join(e["shared"])))

    elif ns.cmd == "bridges":
        gr = store.graph(conn)
        if not gr["bridges"]:
            print("现在一条桥都没有。想法太少，或者它们真的没关系。")
        for x in gr["bridges"][:ns.n]:
            print("\n「%s」  ×%.2f  score %.4f" % (x["term"], x["bonus"], x["score"]))
            print("  %s（%s）" % (x["a_title"], "/".join(x["a_dims"])))
            print("    %s" % x["a_say"]["text"])
            print("  %s（%s）" % (x["b_title"], "/".join(x["b_dims"])))
            print("    %s" % x["b_say"]["text"])

    elif ns.cmd == "path":
        pth = store.connect_two(conn, ns.a, ns.b)
        if not pth:
            print("串不起来。这两个想法之间没有一条由共同词条连成的路。")
            return 1
        t = {d["id"]: d["title"] for d in store.docs(conn)}
        parts = []
        for nid in pth["nodes"]:
            k, ref = nid.split(":", 1)
            parts.append(("「%s」" % t.get(ref, ref)) if k == "idea" else ref)
        print(" → ".join(parts))
        print("%d 跳，代价 %.2f" % (pth["hops"], pth["cost"]))

    elif ns.cmd == "serve":
        conn.close()
        try:
            server.serve(ns.db, ns.web, ns.host, ns.port, unsafe_no_auth=ns.unsafe_dev_no_auth)
        except auth.AuthConfigError as e:
            print("启动被拒绝：%s" % e, file=sys.stderr)
            return 2
        return 0

    conn.commit()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
