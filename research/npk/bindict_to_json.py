#!/usr/bin/env python3
"""Parse every *.bin bindict blob dumped from RAM into JSON (uses NeoXtractor-v3 BindictParser)."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bindict"))
from parser import BindictParser

def conv(o):
    if isinstance(o, dict): return {str(k): conv(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set, frozenset)): return [conv(x) for x in o]
    if isinstance(o, bytes): return o.hex()
    return o

src = sys.argv[1]; dst = sys.argv[2]; os.makedirs(dst, exist_ok=True)
ok = bad = 0; fails = []
for fn in sorted(os.listdir(src)):
    if not fn.endswith(".bin"): continue
    data = open(os.path.join(src, fn), "rb").read()
    r = BindictParser()._parse_dictionary_data(data)
    if r is None:
        bad += 1; fails.append(fn); continue
    s = json.dumps(conv(r), ensure_ascii=False, indent=1, sort_keys=False, default=str)
    unk = s.count("<unknown_marker")
    if unk: fails.append(f"{fn} unknown_markers={unk}")
    open(os.path.join(dst, fn[:-4] + ".json"), "w").write(s)
    ok += 1
print(f"ok={ok} fail={bad}")
for f in fails: print("  ", f)
