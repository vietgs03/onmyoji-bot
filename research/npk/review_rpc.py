#!/usr/bin/env python3
"""review_rpc.py - In ngu canh source cho tung RPC de duyet tay (ham goi + callback)."""
import json, os, re, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src_decompiled")
cat = json.load(open(os.path.join(HERE, "data", "rpc_catalog.json")))


def body(path, name, n=14):
    p = os.path.join(SRC, path)
    if not os.path.exists(p):
        return ""
    L = open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(L):
        if re.match(r"\s*def %s\(" % re.escape(name), l):
            out = [L[i]]
            for l2 in L[i + 1:i + n]:
                if re.match(r"\s*def |# line", l2):
                    break
                out.append(l2)
            return "\n".join(out)
    return ""


def callers(name):
    r = subprocess.run(["grep", "-rn", "--include=*.py", r"\.%s(" % name, SRC], capture_output=True, text=True)
    lines = [l.replace(SRC + "/", "") for l in r.stdout.splitlines() if "callServer" not in l][:3]
    return lines


for name in sys.argv[1:]:
    v = cat.get(name, {})
    print("=" * 90)
    print(name, v.get("class"))
    for f, fn in v.get("sites", [])[:1]:
        print(body(f, fn))
    for cf in v.get("cb_files", [])[:1]:
        for suf in ("_cb", "_callback", "_return", "_reply"):
            b = body(cf, name + suf, 10)
            if b:
                print("--cb--"); print(b); break
    for c in callers(name):
        print("  caller:", c[:160])
