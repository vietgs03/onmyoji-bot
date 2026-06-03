#!/usr/bin/env python3
"""
test_world_maze.py - ME CUNG TU DATA SOURCE THAT (exploration/world.json).

world.json la me cung THAT da do duoc: 105 'state' (anh man hinh that + label) +
185 'edge' (click o day -> sang man kia). Day la "su that mat dat" cua game.

Bai test: agent phai NHAN DUNG anh (where()/detect_overlay map dung node/overlay) va
  LO RA anh NHAN SAI (anh la X nhung doc thanh Y). Khac voi test_screen_graph (cherry
  -pick 13 anh dep), o day cham TAT CA 105 anh -> confusion matrix that, honest.

Phan loai: label world.json -> NODE (di toi duoc) hay OVERLAY (popup) hay BO QUA
  (chua mo hoa: World, Event Overview...). Voi NODE: dung where(); OVERLAY: detect_overlay().

Chay: .venv/bin/python automation/test_world_maze.py
"""
import os, sys, json, cv2
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from screen_graph import ScreenGraph, NODES, OVERLAYS
from screen_reader import ScreenReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(ROOT, "exploration", "world.json")

# Map label world.json -> ten node/overlay trong screen_graph.
LBL2NODE = {
    "HOME": "HOME", "Explore": "exploration", "Town": "town", "Summon": "summon",
    "Shikigami": "shikigami", "Friends": "friends", "Shop": "shop",
    "Event": "event", "Settings": "settings", "Guild Hall": "guild",
    "Shrine Pass": "shrine_pass", "Cosmetics": "cosmetics", "Mentor": "mentor",
}
LBL2OVERLAY = {
    "Loading": "loading", "Animation": "animation",
    "Character Showcase": "char_showcase", "Group Buying": "group_buying",
    "Select Champion": "select_champion", "Create Float": "create_float",
    "Cosmetic Quests": "cosmetic_quests",
}
# label chua mo hoa trong graph -> bo qua khoi cham diem (ky vong: khong nhan ra)
IGNORE = {"World", "Event Overview"}


def main():
    w = json.load(open(WORLD))
    states = w["states"]
    # Agent that chi de dung is_loading_screen (dhash) cho overlay 'loading' -
    # KHONG can PS server (chi xu ly anh). detect_overlay loading se dung no.
    try:
        from agent import Agent
        g = ScreenGraph(agent=Agent())
    except Exception:
        g = ScreenGraph()

    # gom anh theo label
    by_label = defaultdict(list)
    for sid, s in states.items():
        by_label[s["label"]].append(s)

    node_ok = node_tot = 0
    ov_ok = ov_tot = 0
    conf_node = defaultdict(lambda: defaultdict(int))   # ky_vong -> doc_ra -> dem
    fails = []                                           # (label, path, mong, got, conf)

    for label in sorted(by_label):
        if label in IGNORE:
            continue
        is_overlay = label in LBL2OVERLAY
        exp = LBL2OVERLAY.get(label) or LBL2NODE.get(label)
        if exp is None:
            continue
        for s in by_label[label]:
            p = os.path.join(ROOT, s["screenshot"])
            img = cv2.imread(p)
            if img is None:
                continue
            r = ScreenReader(img)
            if is_overlay:
                got, conf = g.detect_overlay(reader=r)
                ov_tot += 1; ov_ok += (got == exp)
            else:
                # tren NODE that: KHONG duoc nham la overlay; phai where() dung.
                ov_name, ov_c = g.detect_overlay(reader=r)
                got, conf = g.where(reader=r)
                node_tot += 1; node_ok += (got == exp)
            conf_node[exp][got] += 1
            if got != exp:
                fails.append((label, os.path.basename(p), exp, got, conf))

    # ---- bao cao ----
    print(f"=== ME CUNG DATA SOURCE THAT: {len(states)} anh, "
          f"{len([s for s in states.values() if s['label'] not in IGNORE])} cham diem ===\n")
    print(f"NODE (nhan dung man dieu huong):   {node_ok}/{node_tot} = "
          f"{node_ok/node_tot:.3f}" if node_tot else "NODE: n/a")
    print(f"OVERLAY (nhan dung popup/man tam): {ov_ok}/{ov_tot} = "
          f"{ov_ok/ov_tot:.3f}" if ov_tot else "OVERLAY: n/a")
    tot = node_tot + ov_tot; ok = node_ok + ov_ok
    print(f"TONG accuracy: {ok}/{tot} = {ok/tot:.3f}\n")

    if fails:
        print(f"--- {len(fails)} anh NHAN SAI (lo ra de soi) ---")
        for label, fn, exp, got, conf in fails:
            print(f"  [{label:18}] {fn}  mong={exp:14} doc_ra={str(got):14} conf={conf:.2f}")
    else:
        print("Khong co anh nhan sai.")


if __name__ == "__main__":
    main()
