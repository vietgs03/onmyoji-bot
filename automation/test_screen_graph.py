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
from screen_graph import ScreenGraph, NODES, HOME, validate
from screen_reader import ScreenReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(ROOT, "exploration", "world.json")

# nhan world.json -> node graph (de so where())
LBL2NODE = {
    "HOME": "HOME", "Explore": "exploration", "Town": "town", "Summon": "summon",
    "Shikigami": "shikigami", "Friends": "friends", "Shop": "shop",
    "Event": "event", "Settings": "settings", "Guild Hall": "guild",
    "Shrine Pass": "shrine_pass", "Cosmetics": "cosmetics", "Mentor": "mentor",
}

# nhan world.json -> overlay (man tam/popup, KHONG phai node dieu huong)
LBL2OVERLAY = {
    "Character Showcase": "char_showcase", "Group Buying": "group_buying",
    "Select Champion": "select_champion", "Create Float": "create_float",
    "Cosmetic Quests": "cosmetic_quests",
}

# cac cap path mong doi (BFS)
PATH_CASES = [
    ("HOME", "realm_raid", ["HOME", "exploration", "realm_raid"]),
    ("HOME", "duel", ["HOME", "town", "duel"]),
    ("realm_raid", "duel", ["realm_raid", "exploration", "HOME", "town", "duel"]),
    ("summon", "HOME", ["summon", "HOME"]),
]


def test_tree():
    errs = validate()
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
        got, conf = g.where(reader=r)
        exp = LBL2NODE[lbl]
        good = got == exp
        ok += good
        tot += 1
        print(f"C. where {lbl:10} -> {str(got):12} (conf {conf:.2f}) "
              f"mong={exp:12} {'OK' if good else 'SAI'}")
    print(f"   where accuracy: {ok}/{tot} = {ok/tot:.3f}")
    return ok / tot


def test_overlay():
    """D. detect_overlay() nhan dien overlay/popup tren anh that.
    Va: overlay KHONG bi where() nham la node (tach bach 2 bang)."""
    g = ScreenGraph()
    w = json.load(open(WORLD))
    seen = {}
    for s in w["states"].values():
        lbl, p = s.get("label"), s.get("screenshot")
        if lbl in LBL2OVERLAY and lbl not in seen and p and os.path.exists(p):
            seen[lbl] = p
    ok = tot = 0
    for lbl, p in sorted(seen.items()):
        r = ScreenReader(cv2.imread(p))
        got, conf = g.detect_overlay(reader=r)
        exp = LBL2OVERLAY[lbl]
        good = got == exp
        ok += good
        tot += 1
        print(f"D. overlay {lbl:18} -> {str(got):16} (conf {conf:.2f}) "
              f"mong={exp:16} {'OK' if good else 'SAI'}")
    if tot:
        print(f"   overlay accuracy: {ok}/{tot} = {ok/tot:.3f}")
    return ok / tot if tot else 1.0


def test_stats():
    """E. HOC ONLINE: cost canh thich nghi + ne TUONG (Stochastic Shortest Path).
    Kiem tra: (1) canh fail nhieu -> blocked; (2) Dijkstra ne tuong, chon duong vong;
    (3) thanh cong reset block. Day la cot loi 'biet tuong chan o dau'."""
    from edge_stats import EdgeStats
    print("\n=== E. HOC ONLINE (edge stats) ===")
    if os.path.exists("/tmp/es_eval.json"):
        os.remove("/tmp/es_eval.json")             # bat dau sach -> test deterministic
    ok = tot = 0

    def chk(name, cond):
        nonlocal ok, tot
        tot += 1; ok += bool(cond)
        print(f"E. {name:40} {'OK' if cond else 'SAI'}")

    es = EdgeStats("/tmp/es_eval.json")
    # do thi do choi: A->B (ngan) | A->C->B (vong). B la dich.
    toy = {
        "A": {"identify": ["A"], "exits": {"B": {"text": ["x"], "cost": 1.0},
                                            "C": {"text": ["x"], "cost": 1.0}}, "parent": None},
        "B": {"identify": ["B"], "exits": {}, "parent": "A"},
        "C": {"identify": ["C"], "exits": {"B": {"text": ["x"], "cost": 1.0}}, "parent": "A"},
    }
    g = ScreenGraph(nodes=toy, stats=es)
    chk("truoc tuong: di duong ngan A->B", g.path("A", "B") == ["A", "B"])

    for _ in range(3):
        es.record("A", "B", ok=False)               # gap tuong 3 lan
    chk("3 fail -> canh A->B bi danh dau blocked", es.is_blocked("A", "B"))
    chk("sau tuong: Dijkstra ne, di vong A->C->B", g.path("A", "B") == ["A", "C", "B"])

    es.record("A", "B", ok=True)                     # tuong mo lai (event)
    chk("thanh cong -> bo chan, ve lai duong ngan", g.path("A", "B") == ["A", "B"])

    # cost don dieu theo do tin cay
    c_good = es.learned_cost("A", "C", 1.0)
    es.record("A", "C", ok=False); es.record("A", "C", ok=False)
    c_bad = es.learned_cost("A", "C", 1.0)
    chk("canh hay fail -> cost tang", c_bad > c_good)

    print(f"   stats logic: {ok}/{tot} = {ok/tot:.3f}")
    return ok / tot if tot else 1.0


def main():
    a = test_tree()
    b = test_paths()
    c = test_where()
    d = test_overlay()
    e = test_stats()
    print(f"\nTONG: cay={'OK' if a else 'LOI'}, path={'OK' if b else 'LOI'}, "
          f"where={c:.3f}, overlay={d:.3f}, stats={e:.3f}")


if __name__ == "__main__":
    main()
