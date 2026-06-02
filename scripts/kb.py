#!/usr/bin/env python3
"""
Tool tra cuu knowledge base Onmyoji.
  ./kb.py shikigami <ten>     # tim shikigami theo ten EN/CN
  ./kb.py soul <ten>          # tim soul (御魂)
  ./kb.py stats               # thong ke data
  ./kb.py rarity SSR          # liet ke theo do hiem
"""
import json, os, sys

BASE = os.path.join(os.path.dirname(__file__), "..", "data", "fandom")

def load(name):
    p = os.path.join(BASE, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []

def cmd_shikigami(q):
    data = load("shikigami_parsed.json")
    ql = q.lower()
    hits = [s for s in data if ql in (s.get("name_en") or "").lower()
            or ql in (s.get("name_cn") or "").lower()
            or ql in (s.get("name_gl") or "").lower()]
    for s in hits[:15]:
        print(f"#{s['id']:>3} [{s['rarity']}] {s['name_en']:<22} CN:{s['name_cn']} JP:{s['name_jp']} GL:{s['name_gl']}")
    if not hits: print("khong tim thay")

def cmd_soul(q):
    data = load("souls_parsed.json")
    ql = q.lower()
    hits = [s for s in data if ql in (s.get("name_en") or "").lower()
            or ql in (s.get("name_cn") or "").lower()]
    for s in hits[:15]:
        print(f"#{s['no']:>3} {s['name_en']:<18} [{s['type']}]")
        print(f"      2set: {s['combo2']}")
        print(f"      4set: {s['combo4']}")
    if not hits: print("khong tim thay")

def cmd_rarity(r):
    data = load("shikigami_parsed.json")
    hits = [s for s in data if (s.get("rarity") or "").upper() == r.upper()]
    print(f"{len(hits)} shikigami rarity {r}:")
    for s in hits:
        print(f"  #{s['id']:>3} {s['name_en']:<22} {s['name_cn']}")

def cmd_stats():
    from collections import Counter
    sk = load("shikigami_parsed.json")
    so = load("souls_parsed.json")
    gm = load("game_modes.json") if os.path.exists(os.path.join(BASE,"game_modes.json")) else {}
    print(f"Shikigami: {len(sk)}  ->", dict(Counter(s['rarity'] for s in sk)))
    print(f"Souls:     {len(so)}")
    gm_data = json.load(open(os.path.join(BASE,"game_modes.json"),encoding="utf-8")) if os.path.exists(os.path.join(BASE,"game_modes.json")) else {}
    print(f"Game modes: {len(gm_data)} ->", ", ".join(list(gm_data.keys())[:10]), "...")
    gj = os.path.join(BASE, "..", "guidemyoji", "posts.json")
    if os.path.exists(gj):
        print(f"Guidemyoji posts: {len(json.load(open(gj,encoding='utf-8')))}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else ""
    {"shikigami": cmd_shikigami, "soul": cmd_soul,
     "rarity": cmd_rarity, "stats": lambda _: cmd_stats()}.get(
        cmd, lambda _: print("unknown cmd"))(arg)
