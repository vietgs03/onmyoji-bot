#!/usr/bin/env python3
"""
render_daily_realm.py - ME CUNG THUC TE: daily 'farm Realm 30 lan' tu BAT KY man nao.

User: nhiem vu daily OAS (vd Realm Raid 30 lan) khong phai chi-duong, ma la:
  agent dang o BAT KY man (soul_zones, town, dang danh...) -> phai TU DINH VI -> toi
  realm_raid -> THUC HIEN action (challenge loop 30 lan) -> verify. Day moi la ma tran
  thuc te gap phai.

Mo phong (offline, chua chay game):
  1. Voi MOI man xuat phat (toan bo NODES) -> Dijkstra tu do toi 'realm_raid'.
     -> so step + tung hanh dong (click/Back). Verify = BFS optimal.
  2. ACTION LOOP: tai realm_raid, lap N lan (challenge -> battle -> reward -> back).
     Mo hinh hoa nhu state-machine nho de uoc luong tong thao tac/lan.
  3. RENDER: ban do 'tu moi man toi realm bao nhieu step' (heat) + 1 so case tieu bieu.

Chay: .venv/bin/python automation/render_daily_realm.py
Anh -> research/daily_realm/*.png
"""
from __future__ import annotations

import os, sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from screen_graph import ScreenGraph, NODES, HOME

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "daily_realm")
os.makedirs(OUT, exist_ok=True)

GOAL = "realm_raid"
N_FARM = 30                                          # so lan farm theo daily OAS


def bfs_len(g, s, t):
    if s == t:
        return 0
    q = deque([(s, 0)]); seen = {s}
    while q:
        n, d = q.popleft()
        for nb in g._neighbors(n):
            if nb not in seen:
                if nb == t:
                    return d + 1
                seen.add(nb); q.append((nb, d + 1))
    return None


def step_action(g, src, dst):
    if g._is_back_edge(src, dst):
        return "Back"
    btn = g._exits(src).get(dst, {})
    if btn.get("text"):
        return f"click '{btn['text'][0]}'"
    if btn.get("center"):
        return f"click {btn['center']}"
    return "?"


def reach_table(g):
    """Tu MOI man -> realm_raid: so step + duong + verify optimal."""
    print(f"=== DAILY 'farm Realm {N_FARM} lan': tu MOI man toi '{GOAL}' ===\n")
    print(f"{'xuat phat':16} {'step':>4} {'optimal':>7}  {'OK':>3}  duong di")
    rows = []
    for s in sorted(NODES):
        p = g.path(s, GOAL)
        opt = bfs_len(g, s, GOAL)
        steps = len(p) - 1 if p else None
        ok = (p is not None and steps == opt)
        rows.append((s, p, steps, opt, ok))
        path_str = " -> ".join(p) if p else "KHONG TOI"
        print(f"{s:16} {str(steps):>4} {str(opt):>7}  {'OK ' if ok else 'SAI'}  {path_str}")
    allok = all(r[4] for r in rows)
    worst = max((r[2] for r in rows if r[2] is not None), default=0)
    print(f"\nTAT CA toi duoc + step CHUAN: {allok} | xa nhat: {worst} step")
    return rows


def show_3_cases(g):
    """3 case user nhac: dang o soul_zones / town / dang danh (gia lap = realm con)."""
    print("\n=== 3 CASE TIEU BIEU (chi tiet tung hanh dong) ===")
    for s in ["soul_zones", "town", "duel"]:
        p = g.path(s, GOAL)
        print(f"\n  Dang o '{s}' -> can toi '{GOAL}' ({len(p)-1} step):")
        for i in range(len(p) - 1):
            print(f"    {i+1}. {p[i]:14} -> {p[i+1]:14} | {step_action(g, p[i], p[i+1])}")
        print(f"    {len(p)}. tai '{GOAL}': lap {N_FARM} lan "
              f"[click Challenge/Assault -> battle -> Reward -> Back]")


def action_loop_model():
    """Uoc luong thao tac cho ACTION LOOP (lap N_FARM lan farm tai realm)."""
    print(f"\n=== ACTION LOOP tai realm_raid ({N_FARM} lan) - state-machine ===")
    # 1 lan farm ~ chuoi state. (uoc luong, chua chay that)
    per_run = [
        ("chon team / Challenge", "click Challenge"),
        ("battle (auto)",         "doi ket thuc / Skip"),
        ("man Reward",            "click Reward/tap"),
        ("ve danh sach",          "tu dong / Back"),
    ]
    for st, act in per_run:
        print(f"    - {st:24} : {act}")
    print(f"  => 1 lan ~ {len(per_run)} thao tac. {N_FARM} lan ~ {len(per_run)*N_FARM} thao tac.")
    print("  Moi lan VERIFY (con luot? het ticket?) -> dung neu het, khong farm mu.")


def render(g, rows):
    import numpy as np, cv2
    # layout cay theo depth (giong render_nav_cases) + to mau theo so step toi realm
    depth = {HOME: 0}; q = deque([HOME])
    while q:
        n = q.popleft()
        for nb in g._exits(n):
            if nb not in depth:
                depth[nb] = depth[n] + 1; q.append(nb)
    levels = {}
    for n, d in depth.items():
        levels.setdefault(d, []).append(n)
    pos = {}; W, Hh = 1700, 980; maxd = max(levels)
    for d, nodes in levels.items():
        for i, n in enumerate(sorted(nodes)):
            x = 90 + (W - 180) * (i + 1) / (len(nodes) + 1)
            y = 70 + (Hh - 140) * d / max(maxd, 1)
            pos[n] = (int(x), int(y))
    steps_of = {r[0]: r[2] for r in rows}
    maxs = max((v for v in steps_of.values() if v is not None), default=1)

    img = np.full((Hh, W, 3), 255, np.uint8)
    for n in pos:                                    # canh tien (xam)
        for nb in g._exits(n):
            if nb in pos:
                cv2.line(img, pos[n], pos[nb], (215, 215, 215), 1)
    for n, (x, y) in pos.items():
        s = steps_of.get(n)
        if n == GOAL:
            col = (0, 0, 255)                        # dich = do
        elif s is None:
            col = (160, 160, 160)
        else:                                        # cang gan realm cang XANH, xa cang DO
            t = s / max(maxs, 1)
            col = (int(60 + 180*(1-t)), int(180*(1-t)), int(60 + 195*t))
        cv2.circle(img, (x, y), 16, col, -1)
        cv2.putText(img, n, (x - 42, y - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1)
        if s is not None:
            cv2.putText(img, str(s), (x - 6, y + 5), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255, 255, 255), 2)
    cv2.putText(img, f"Daily 'farm Realm {N_FARM}x': so step tu MOI man toi realm_raid "
                f"(do=dich, xanh=gan, so=step)", (30, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 150), 2)
    out = os.path.join(OUT, "reach_realm_heat.png")
    cv2.imwrite(out, img)

    # 3 case tieu bieu (duong di to dam)
    for s in ["soul_zones", "town", "duel"]:
        p = g.path(s, GOAL)
        c = img.copy()
        for i in range(len(p) - 1):
            a, b = pos[p[i]], pos[p[i+1]]
            back = g._is_back_edge(p[i], p[i+1])
            cv2.arrowedLine(c, a, b, (0, 120, 255) if back else (0, 150, 0), 5, tipLength=0.04)
            mid = ((a[0]+b[0])//2, (a[1]+b[1])//2)
            cv2.putText(c, str(i+1), mid, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 200), 2)
        cv2.imwrite(os.path.join(OUT, f"case_{s}_to_realm.png"), c)
    print(f"\nrender 4 PNG -> {OUT}")


def main():
    g = ScreenGraph()
    rows = reach_table(g)
    show_3_cases(g)
    action_loop_model()
    render(g, rows)


if __name__ == "__main__":
    main()
