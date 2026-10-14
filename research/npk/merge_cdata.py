#!/usr/bin/env python3
"""Merge RAM-dumped game data into one JSON per module.

Inputs (from pyobj_dump.ps1 -Mode bindicts):
  <mod>.<attr>.bin        raw bindict blobs  -> parsed with NeoXtractor BindictParser
  <mod>.<attr>.cache.json decoded-entry cache of native bindict (partial, used when blob missing)
  <mod>.py.json           remaining plain Python attributes (dict/list/taggeddict/...)

Output: <out>/<mod>.json = {"<attr>": value, ...}  (bin_data_content -> "data")
"""
import json, os, sys, re
from collections import defaultdict
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "bindict"))
from parser import BindictParser

def conv(o):
    if isinstance(o, dict): return {str(k): conv(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set, frozenset)): return [conv(x) for x in o]
    if isinstance(o, bytes): return o.hex()
    return o

def attr_name(a):
    if a in ("bin_data_content", "bin_data"): return "data"
    m = re.fullmatch(r"bin_(.+)_content", a)
    return m.group(1) if m else a

src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)
mods = defaultdict(dict); stats = defaultdict(int)
for fn in sorted(os.listdir(src)):
    p = os.path.join(src, fn)
    if fn.endswith(".py.json"):
        mod = fn[:-8]
        try: d = json.load(open(p, encoding="utf-8"))
        except Exception: stats["py_bad"] += 1; continue
        for k, v in d.items(): mods[mod].setdefault(k, v)
        stats["py"] += 1
    elif fn.endswith(".cache.json"):
        mod, attr = fn[:-11].rsplit(".", 1)
        try: d = json.load(open(p, encoding="utf-8"))
        except Exception: stats["cache_bad"] += 1; continue
        mods[mod].setdefault("__cache__" + attr_name(attr), d); stats["cache"] += 1
    elif fn.endswith(".bin"):
        mod, attr = fn[:-4].rsplit(".", 1)
        r = BindictParser()._parse_dictionary_data(open(p, "rb").read())
        if r is None: stats["bin_fail"] += 1; continue
        mods[mod][attr_name(attr)] = conv(r); stats["bin"] += 1
# promote caches when no full table
for mod, d in mods.items():
    for k in [k for k in d if k.startswith("__cache__")]:
        name = k[len("__cache__"):]
        v = d.pop(k)
        if not d.get(name) or not isinstance(d.get(name), dict) or len(d[name]) < len(v):
            d[name] = v; d.setdefault("__partial__", []).append(name)
    for k in ("_reload_all", "fix_bindict_bug_version", "bin_data_content", "translate"):
        if d.get(k) in (None, True, False): d.pop(k, None)
    json.dump(d, open(os.path.join(dst, mod.replace("com.data.", "") + ".json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
print(dict(stats), "modules:", len(mods))
