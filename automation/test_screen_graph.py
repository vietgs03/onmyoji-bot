#!/usr/bin/env python3
"""
test_screen_graph.py - EVAL graph dieu huong (where + path/BFS).

Kiem tra:
  A. CAY hop le (moi parent/exit ton tai, khong vong) - tinh, khong can game.
  B. BFS path dung tren vai cap dien hinh - tinh.
  C. where() nhan dien dung node tren anh that (world.json) - dung OCR.

Chay: .venv/bin/python automation/test_screen_graph.py
"""
import os, sys, json, cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml"))
from screen_graph import ScreenGraph, NODES, HOME
from screen_reader import ScreenReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(ROOT, "exploration", "world.json")

# nhan world.json -> node graph (de so where())
LBL2NODE = {
    "HOME": "HOME", "Explore": "exploration", "Town": "town", "Summon": "summon",
    "Shikigami": "shikigami", "Friends": "friends", "Shop": "shop",
}

# cac cap path mong doi (BFS)
PATH_CASES = [
    ("HOME", "realm_raid", ["HOME", "exploration", "realm_raid"]),
    ("HOME", "duel", ["HOME", "town", "duel"]),
    ("realm_raid", "duel", ["realm_raid", "exploration", "HOME", "town", "duel"]),
    ("summon", "HOME", ["summon", "HOME"]),
]


def test_tree():
    errs = []
    for n, d in NODES.items():
        par = d.get("parent")
        if par and par not in NODES:
            errs.append(f"{n}: parent '{par}' khong ton tai")
        # phat hien vong cha
        seen, cur = set(), n
        while cur:
            if cur in seen:
                errs.append(f"{n}: vong parent")
                break
            seen.add(cur)
            cur = NODES.get(cur, {}).get("parent")
        for dst in d.get("exits", {}):
            if dst not in NODES:
                errs.append(f"{n}: exit '{dst}' khong ton tai")
    print(f"A. CAY: {'HOP LE' if not errs else 'LOI'} ({len(NODES)} node)")
    for e in errs:
        print("   ", e)
    return not errs


def test_paths():
    g = ScreenGraph()
    ok = 0
    for start, goal, exp in PATH_CASES:
        got = g.path(start, goal)
        good = got == exp
        ok += good
        print(f"B. path {start}->{goal}: {'OK' if good else 'SAI'}  {got}")
    return ok == len(PATH_CASES)


def test_where():
    g = ScreenGraph()
    w = json.load(open(WORLD))
    seen = {}
    for s in w["states"].values():
        lbl, p = s.get("label"), s.get("screenshot")
        if lbl in LBL2NODE and lbl not in seen and p and os.path.exists(p):
            seen[lbl] = p
    ok = tot = 0
    for lbl, p in sorted(seen.items()):
        r = ScreenReader(cv2.imread(p))
        got = g.where(reader=r)
        exp = LBL2NODE[lbl]
        good = got == exp
        ok += good
        tot += 1
        print(f"C. where {lbl:10} -> {str(got):12} mong={exp:12} {'OK' if good else 'SAI'}")
    print(f"   where accuracy: {ok}/{tot} = {ok/tot:.3f}")
    return ok / tot


def main():
    a = test_tree()
    b = test_paths()
    c = test_where()
    print(f"\nTONG: cay={'OK' if a else 'LOI'}, path={'OK' if b else 'LOI'}, "
          f"where={c:.3f}")


if __name__ == "__main__":
    main()
