#!/usr/bin/env python3
"""
render_nav_cases.py - KIEM CHUNG dieu huong bang TEST CASE THAT + render PNG.

User: render cac test case (HOME->collection, HOME->explore->realm, HOME->soul...)
  xem agent tim duong NHU NAO + step co CHUAN khong. Kiem chung thuc te, khong ly thuyet.

Lam:
  1. Voi moi (start, goal): chay Dijkstra (screen_graph that) -> duong di + tung step.
  2. VERIFY step chuan: tung canh phai TON TAI (forward exit hoac back-to-parent),
     va do dai phai = duong ngan nhat (BFS) -> khong di vong vo ly.
  3. RENDER: ve cay graph (cac node + canh), TO DAM duong di cua case do -> 1 PNG/case,
     + 1 PNG tong cay. Moi step ghi 'click gi' (OCR text / toa do / Back).

Chay: .venv/bin/python automation/render_nav_cases.py
Anh -> research/nav_cases/*.png
"""
from __future__ import annotations

import os, sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from screen_graph import ScreenGraph, NODES, HOME

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "nav_cases")
os.makedirs(OUT, exist_ok=True)

# Cac test case user yeu cau (+ vai case lac duong/di lui de kiem chung).
CASES = [
    ("HOME", "shikigami"),       # 'collection' shikigami (bo suu tap thuc than)
    ("HOME", "cosmetics"),       # 'collection' skin/frame
    ("HOME", "exploration"),     # vao Explore
    ("HOME", "realm_raid"),      # HOME -> Explore -> Realm Raid
    ("HOME", "soul_zones"),      # HOME -> Explore -> Soul Zones
    ("HOME", "duel"),            # HOME -> Town -> Duel
    ("HOME", "shrine_pass"),     # HOME -> Event -> Shrine Pass (sub sau)
    ("HOME", "mentor"),          # HOME -> Friends -> Mentor
    ("realm_raid", "soul_zones"),# anh em: phai di LUI ve exploration roi sang
    ("realm_raid", "town"),      # lac sau: lui ve HOME roi sang town
    ("duel", "HOME"),            # thoat ve nha (toan canh lui)
]


def bfs_len(g, s, t):
    """Do dai duong ngan nhat (so canh) bang BFS - chuan de doi chieu Dijkstra."""
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


def describe_step(g, src, dst):
    """Mo ta agent LAM GI o step src->dst (giong _go_edge that)."""
    if g._is_back_edge(src, dst):
        return "Back/dismiss (lui ve parent)"
    btn = g._exits(src).get(dst, {})
    txt = btn.get("text") or []
    if txt:
        return f"click OCR text {txt}" + (f" / fallback {btn.get('center')}" if btn.get("center") else "")
    if btn.get("center"):
        return f"click toa do {btn['center']} (nut khong text)"
    return "?"


def verify_and_print():
    g = ScreenGraph()
    print("=== KIEM CHUNG DIEU HUONG: tung test case + step ===\n")
    all_ok = True
    results = []
    for s, t in CASES:
        p = g.path(s, t)
        opt = bfs_len(g, s, t)
        steps = len(p) - 1 if p else None
        chuan = (p is not None and steps == opt)
        all_ok &= chuan
        results.append((s, t, p, steps, opt, chuan))
        print(f"[{ 'OK ' if chuan else 'SAI'}] {s} -> {t}: "
              f"{steps} step (toi uu {opt})")
        if p:
            for i in range(len(p) - 1):
                print(f"      step {i+1}: {p[i]:14} -> {p[i+1]:14}  | {describe_step(g, p[i], p[i+1])}")
        else:
            print("      KHONG TIM DUOC DUONG")
        print()
    print(f"TONG: {sum(r[5] for r in results)}/{len(results)} case step CHUAN "
          f"(= duong ngan nhat).")
    return g, results


def render(g, results):
    """Ve cay graph + to dam duong di moi case. Layout cay theo depth (BFS tu HOME)."""
    import numpy as np, cv2
    # --- layout: gan (x,y) cho moi node theo tang (depth) ---
    depth = {HOME: 0}
    order = [HOME]; q = deque([HOME])
    while q:
        n = q.popleft()
        for nb in g._exits(n):                       # chi canh tien -> cay
            if nb not in depth:
                depth[nb] = depth[n] + 1
                order.append(nb); q.append(nb)
    levels = {}
    for n, d in depth.items():
        levels.setdefault(d, []).append(n)
    pos = {}
    W, Hh = 1700, 980
    maxd = max(levels)
    for d, nodes in levels.items():
        for i, n in enumerate(sorted(nodes)):
            x = 90 + (W - 180) * (i + 1) / (len(nodes) + 1)
            y = 70 + (Hh - 140) * d / max(maxd, 1)
            pos[n] = (int(x), int(y))

    def base_canvas():
        img = np.full((Hh, W, 3), 255, np.uint8)
        for n in pos:                                # canh tien (xam)
            for nb in g._exits(n):
                if nb in pos:
                    cv2.line(img, pos[n], pos[nb], (210, 210, 210), 1)
        return img

    def draw_nodes(img, path=None):
        path = path or []
        pset = set(path)
        for n, (x, y) in pos.items():
            on = n in pset
            col = (0, 150, 0) if on else (90, 90, 90)
            cv2.circle(img, (x, y), 20 if on else 13, col, -1)
            cv2.putText(img, n, (x - 40, y - 24), cv2.FONT_HERSHEY_SIMPLEX,
                        0.42, (0, 0, 0), 1)

    # PNG tong cay
    img = base_canvas(); draw_nodes(img)
    cv2.imwrite(os.path.join(OUT, "00_tree.png"), img)

    # 1 PNG / case (to dam duong di + mui ten + so thu tu step)
    for idx, (s, t, p, steps, opt, chuan) in enumerate(results, 1):
        img = base_canvas()
        if p:
            for i in range(len(p) - 1):
                a, b = pos[p[i]], pos[p[i + 1]]
                back = g._is_back_edge(p[i], p[i + 1])
                col = (0, 120, 255) if back else (0, 150, 0)   # lui=cam, tien=xanh
                cv2.arrowedLine(img, a, b, col, 4, tipLength=0.04)
                mid = ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2)
                cv2.putText(img, str(i + 1), mid, cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 0, 200), 2)
            draw_nodes(img, p)
        title = f"{s} -> {t}  ({steps} step, optimal {opt}, {'CHUAN' if chuan else 'SAI'})"
        cv2.putText(img, title, (30, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (0, 100, 0) if chuan else (0, 0, 200), 2)
        cv2.imwrite(os.path.join(OUT, f"{idx:02d}_{s}_to_{t}.png"), img)

    print(f"\nrender {len(results)+1} PNG -> {OUT}")


def main():
    g, results = verify_and_print()
    render(g, results)


if __name__ == "__main__":
    main()
