#!/usr/bin/env python3
"""零依赖的跑测器。

整个仓库不依赖第三方，测试也不该例外——装不上 pytest 的机器同样要能验证它。
测试文件本身是普通的 test_* 函数，pytest 也照样能跑。

支持一个 fixture：`tmp_path`（pathlib.Path，每个测试一个新目录，跑完删掉）。

跳过用 `raise unittest.SkipTest("原因")`。标准库自带，pytest 也认它，所以两边
不用各写一套。**跳过必须和通过分开报**：跨语言那两条在没装 node 的机器上会
自己 return，过去它们照样打绿勾——一台机器上「72 通过」里其实有两条根本没跑，
而那两条正是 README 说的「最难查的一类 bug」的唯一防线。
"""
import importlib.util
import inspect
import os
import pathlib
import shutil
import sys
import tempfile
import traceback
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

GREEN, RED, YEL, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
if not sys.stdout.isatty():
    GREEN = RED = YEL = DIM = OFF = ""

# 中文 Windows 的控制台是 GBK，编不出 ✓ ✗ ⊘ ─，整个跑测器会在打印第一行结果时
# 抛 UnicodeEncodeError——测试全过，报告却崩了。编不出来就退回 ASCII。
# 不强行改成 UTF-8：那会把控制台真正编得出的中文一起赔进去。
def _mark(ch, alt):
    try:
        ch.encode(sys.stdout.encoding or "ascii")
        return ch
    except (UnicodeEncodeError, LookupError):
        return alt


OK, BAD, SKIP, RULE = _mark("✓", "+"), _mark("✗", "x"), _mark("⊘", "-"), _mark("─", "-")


def load(path):
    name = "t_" + os.path.basename(path)[:-3]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_one(fn):
    """→ (状态, 详情)。状态 ∈ pass|skip|fail。"""
    needs = list(inspect.signature(fn).parameters)
    tmp = None
    try:
        if "tmp_path" in needs:
            tmp = tempfile.mkdtemp(prefix="yang-t-")
            fn(pathlib.Path(tmp))
        else:
            fn()
        return "pass", ""
    except unittest.SkipTest as e:
        return "skip", str(e)
    except Exception:
        return "fail", traceback.format_exc()
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    only = argv[1] if len(argv) > 1 else ""
    files = sorted(f for f in os.listdir(HERE)
                   if f.startswith("test_") and f.endswith(".py"))
    npass = nfail = 0
    fails, skips = [], []
    for f in files:
        if only and only not in f:
            continue
        try:
            mod = load(os.path.join(HERE, f))
        except Exception:
            print("%s%s 加载不了%s" % (RED, f, OFF))
            print(traceback.format_exc())
            nfail += 1
            continue
        tests = [(n, v) for n, v in vars(mod).items()
                 if n.startswith("test_") and callable(v)]
        print("\n%s%s%s" % (DIM, f, OFF))
        for name, fn in tests:
            status, detail = run_one(fn)
            if status == "pass":
                npass += 1
                print("  %s%s%s %s" % (GREEN, OK, OFF, name))
            elif status == "skip":
                skips.append((f, name, detail))
                print("  %s%s%s %s %s(%s)%s" % (YEL, SKIP, OFF, name, DIM, detail, OFF))
            else:
                nfail += 1
                fails.append((f, name, detail))
                print("  %s%s%s %s" % (RED, BAD, OFF, name))
    for f, name, err in fails:
        print("\n%s%s %s::%s%s" % (RED, RULE * 3, f, name, OFF))
        print(err.rstrip())
    tail = "%d 通过, %d 失败" % (npass, nfail)
    if skips:
        # 跳过单独说一遍，不混进通过数里。没跑过的东西不算验证过。
        tail += ", %s%d 跳过%s" % (YEL, len(skips), OFF)
        for f, name, why in skips:
            tail += "\n  %s %s::%s —— %s" % (SKIP, f, name, why)
    print("\n" + tail)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
