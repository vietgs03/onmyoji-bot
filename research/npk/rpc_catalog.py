#!/usr/bin/env python3
"""rpc_catalog.py - Trich toan bo RPC client->server tu source da decompile.

Source decompile la Python 2 nen khong parse bang ast Python 3 duoc;
dung regex can bang ngoac tren tung lenh goi.
Output: data/rpc_catalog.json
  {method: {"count", "sites": [[file, func]], "param_keys": [...], "param_src": [...], "no_params": bool,
            "has_cb": bool, "class": "read"|"write"|"unknown"}}
"""
import collections, json, os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "research/npk/src_decompiled"
OUT = sys.argv[2] if len(sys.argv) > 2 else "research/npk/data/rpc_catalog.json"

CALL_RE = re.compile(r"\b(callServerMethod|callServerMethodDeprecated|call_server_method_before_login|callServer)\(\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\2")
DEF_RE = re.compile(r"^def ([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\)", re.M)

def balanced_args(s, i):
    """s[i] la ky tu ngay sau '(' ; tra ve chuoi doi so den ')' can bang."""
    depth = 1; j = i; q = None
    while j < len(s) and depth:
        c = s[j]
        if q:
            if c == "\\": j += 1
            elif c == q: q = None
        elif c in "'\"": q = c
        elif c in "([{": depth += 1
        elif c in ")]}": depth -= 1
        j += 1
    return s[i:j - 1]

calls = collections.defaultdict(lambda: {"count": 0, "sites": set(), "param_keys": set(), "param_src": [], "no_params": False})
handlers = collections.defaultdict(set)

for root, _, files in os.walk(ROOT):
    for fn in files:
        if not fn.endswith(".py"): continue
        p = os.path.join(root, fn); rel = os.path.relpath(p, ROOT)
        s = open(p, encoding="utf-8", errors="replace").read()
        defs = [(m.start(), m.group(1)) for m in DEF_RE.finditer(s)]
        for m in DEF_RE.finditer(s):
            handlers[m.group(1)].add(rel)
        for m in CALL_RE.finditer(s):
            name = m.group(3)
            open_idx = s.index("(", m.start()) + 1
            args = balanced_args(s, open_idx)
            rest = args.split(",", 1)[1].strip() if "," in args else ""
            func = None
            for pos, dn in defs:
                if pos <= m.start(): func = dn
                else: break
            e = calls[name]
            e["count"] += 1
            e["sites"].add((rel, func))
            if not rest or rest.startswith("{}") or rest in ("None",):
                e["no_params"] = True
            keys = re.findall(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*:", rest.split("}", 1)[0]) if rest.startswith("{") else []
            e["param_keys"].update(keys)
            if len(e["param_src"]) < 3 and rest:
                e["param_src"].append(rest[:200])

READ_PREFIX = ("get_", "req_", "query_", "request_", "fetch_", "check_", "ask_", "search_", "load_", "list_", "view_", "look_")
READ_WORDS = ("_info", "_list", "_rank", "_data", "_status", "_detail", "_record", "_records", "_state", "_query", "_show", "_preview")
WRITE_WORDS = ("buy", "sell", "use", "set_", "_set", "add", "del", "remove", "upgrade", "strengthen", "compose", "exchange",
               "reward", "receive", "claim", "send", "donate", "pay", "order", "create", "join", "quit", "leave", "kick",
               "invite", "accept", "refuse", "start", "finish", "submit", "change", "rename", "lock", "unlock", "discard",
               "draw", "summon", "battle", "fight", "attack", "challenge", "enter", "open", "unbind", "bind", "reset",
               "save", "update", "modify", "apply", "cancel", "transfer", "feed", "upgrade", "awake", "evolve", "gift",
               "like", "zan", "vote", "bet", "gamble", "lottery", "roll", "refresh", "recharge", "consume", "spend", "trade")

def classify(name):
    n = name.lower()
    if n.startswith(READ_PREFIX) or any(n.endswith(w) for w in READ_WORDS):
        # get_xxx_reward thuong la NHAN thuong -> write
        if any(w in n for w in ("reward", "award", "prize", "gift", "_buy", "receive", "claim")):
            return "write"
        return "read"
    if any(w in n for w in WRITE_WORDS):
        return "write"
    return "unknown"

out = {}
for name, e in calls.items():
    out[name] = {
        "count": e["count"],
        "sites": sorted([list(x) for x in e["sites"]])[:8],
        "param_keys": sorted(e["param_keys"]),
        "param_src": e["param_src"],
        "no_params": e["no_params"],
        "has_cb": (name + "_cb") in handlers,
        "cb_files": sorted(handlers.get(name + "_cb", []))[:3],
        "class": classify(name),
    }
json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
c = collections.Counter(v["class"] for v in out.values())
print("rpc methods:", len(out), dict(c))
print("read & no params:", sum(1 for v in out.values() if v["class"] == "read" and v["no_params"]))
print("with _cb handler:", sum(1 for v in out.values() if v["has_cb"]))
