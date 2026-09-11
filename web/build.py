#!/usr/bin/env python3
"""把 src/ 拼成单文件 index.html。

不是通用打包器：只按固定顺序拼，剥掉什么都不剥，因为源码本来就是脚本，
没有 import/export。规模长到需要真打包器的时候换 esbuild，别扩展这个。

它做了一件真打包器不会替你做的事：**检查顶层重名**。拼接会把所有文件塞进
同一个作用域，重名的后果是运行时 SyntaxError，而且报错里没有文件名。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")

CSS = ["app.css", "extra.css", "graph.css"]
JS = [
    "yangdata.js",     # 导出格式 —— 和 yang/jsonl.py 必须同步改
    "01_state.js",     # 状态、工具、语音
    "02_db.js",        # IndexedDB
    "03_api.js",       # 后端（可选）
    "04_agent.js",     # 智能体
    "05_today.js",     # 今天 / 想法 / 念头 / 凉了的
    "06_idea.js",      # 一个想法
    "07_data.js",      # 数据页
    "graph_view.js",   # 图谱
    "09_boot.js",      # 记念头 / 凉之前 / 启动
]

TOP = re.compile(
    r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)|^(?:const|let|var)\s+([A-Za-z_$][\w$]*)",
    re.M)


def collisions(parts):
    seen, bad = {}, []
    for name, code in parts:
        for m in TOP.finditer(code):
            ident = m.group(1) or m.group(2)
            if ident in seen and seen[ident] != name:
                bad.append((ident, seen[ident], name))
            seen[ident] = name
    return bad


def main(destination=None):
    css = "".join(open(os.path.join(SRC, f), encoding="utf-8").read()
                  for f in CSS if os.path.exists(os.path.join(SRC, f)))
    parts = []
    for f in JS:
        p = os.path.join(SRC, f)
        if not os.path.exists(p):
            print("缺文件：%s" % f, file=sys.stderr)
            return 1
        parts.append((f, open(p, encoding="utf-8").read()))

    bad = collisions(parts)
    if bad:
        for ident, a, b in bad:
            print("顶层重名：%s 同时出现在 %s 和 %s" % (ident, a, b), file=sys.stderr)
        return 1

    body = open(os.path.join(SRC, "body.html"), encoding="utf-8").read()
    js = "\n".join("/* ---- %s ---- */\n%s" % (n, c) for n, c in parts)
    out = ('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width,initial-scale=1,'
           'viewport-fit=cover">\n<title>养想法</title>\n'
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
           'family=ZCOOL+XiaoWei&family=Noto+Sans+SC:wght@300;400;500&display=swap">\n'
           '<style>\n' + css + '\n</style>\n</head>\n<body>\n' + body +
           '\n<script>\n"use strict";\n' + js + '\n</script>\n</body>\n</html>\n')
    dst = destination or os.path.join(HERE, "index.html")
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    # newline="\n"：不写就是平台默认，Windows 上会把每个换行变成 CRLF，
    # 同一份 src 在两台机器上拼出来的 index.html 字节数不一样。产物要可复现。
    open(dst, "w", encoding="utf-8", newline="\n").write(out)
    print("写了 %s（%d 字节，%d 个源文件）" % (dst, len(out), len(JS)))
    return 0


if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--output")
    sys.exit(main(parser.parse_args().output))
