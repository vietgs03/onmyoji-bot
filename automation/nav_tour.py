#!/usr/bin/env python3
"""
nav_tour.py - ACTION DAI do hieu qua graph navigation (giong scheduler OAS chay
nhieu task qua nhieu page). Bot tu di toi 1 LOAT node muc tieu bang goto(), moi
chang tu xac minh den dung noi khong, do thoi gian + do chinh xac, roi ve HOME.

KHAC OAS: OAS dung template anh + toa do co dinh. Day dung OCR-semantic + Dijkstra
+ re-plan khi lac. Muc tieu: do bot co dieu huong CHINH XAC qua N man that khong.

GHI SO LIEU -> logs/nav_tour.jsonl: moi chang {goal, reached, hops, dur_s, where_end}.
Cuoi in summary: ti le toi dung dich, tong thoi gian, chang nao fail.

CLI: python nav_tour.py [tour]   (tour = preset 'daily' | 'combat' | 'full')
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "logs", "nav_tour.jsonl")

# Cac tour (chuoi node muc tieu). Moi node -> goto() -> ve HOME -> node tiep.
# Chon node VERIFIED truoc (do dieu huong that), xen 1-2 node chua verified de
# kiem tra bot co tu xac minh/that bai gon gang khong.
TOURS = {
    # tour ngan: cac hub + man tien ich hay dung (deu verified)
    "daily": ["exploration", "town", "friends", "shop", "summon", "shikigami"],
    # tour combat: di sau vao cac man danh (co node cap 2/3)
    "combat": ["soul_zones", "realm_raid", "area_boss", "duel", "demon_encounter"],
    # tour full: tron verified + chua-verified de do ca 2 (do robust)
    "full": ["exploration", "soul_zones", "realm_raid", "kekkai_toppa", "town",
             "demon_encounter", "friends", "mentor", "guild", "event", "shop"],
}


def run_tour(name: str = "daily") -> None:
    from agent import Agent
    from screen_graph import ScreenGraph

    goals = TOURS.get(name)
    if not goals:
        print(f"tour khong ton tai: {name}. Co: {list(TOURS)}")
        return

    a = Agent()
    g = ScreenGraph(a)
    run_id = int(time.time())
    results = []
    try:
        # ve HOME lam moc dau
        g.escape()
        start_node = g.where()[0]
        print(f"== TOUR '{name}' ({len(goals)} chang) | bat dau o: {start_node} ==\n")

        for i, goal in enumerate(goals, 1):
            verified = ScreenGraph().nodes.get(goal, {}).get("verified", False)
            tag = "" if verified else " [chua verified]"
            print(f"--- chang {i}/{len(goals)}: -> {goal}{tag} ---")
            t0 = time.time()
            ok = g.goto(goal, verbose=False)
            dur = time.time() - t0
            where_end = g.where()[0]
            rec = {"run": run_id, "tour": name, "i": i, "goal": goal,
                   "verified": verified, "reached": bool(ok),
                   "hops_dur_s": round(dur, 1), "where_end": where_end}
            results.append(rec)
            with open(LOG, "a") as f:
                f.write(json.dumps(rec) + "\n")
            mark = "OK" if ok else "FAIL"
            print(f"    {mark} | {dur:.1f}s | ket thuc o: {where_end}\n")
            # ve HOME truoc chang sau (do tung chang doc lap tu HOME)
            g.escape()
            time.sleep(1)

    finally:
        a.c.close()

    # ===== SUMMARY =====
    n = len(results)
    won = sum(1 for r in results if r["reached"])
    tot = sum(r["hops_dur_s"] for r in results)
    print("=" * 50)
    print(f"TOUR '{name}': {won}/{n} chang TOI DUNG DICH ({100*won/n:.0f}%)")
    print(f"tong thoi gian: {tot:.1f}s | trung binh {tot/n:.1f}s/chang")
    fails = [r for r in results if not r["reached"]]
    if fails:
        print("CHANG FAIL:")
        for r in fails:
            print(f"  {r['goal']:24s} -> ket thuc nham o '{r['where_end']}'"
                  f"{' (chua verified, du kien kho)' if not r['verified'] else ''}")
    # tach hieu qua verified vs chua-verified
    vr = [r for r in results if r["verified"]]
    nvr = [r for r in results if not r["verified"]]
    if vr:
        print(f"  verified:      {sum(r['reached'] for r in vr)}/{len(vr)} toi dung")
    if nvr:
        print(f"  chua-verified: {sum(r['reached'] for r in nvr)}/{len(nvr)} toi dung")
    print(f"log: {LOG}")


if __name__ == "__main__":
    run_tour(sys.argv[1] if len(sys.argv) > 1 else "daily")
