#!/usr/bin/env python3
"""
maze_sim.py - SIMULATOR me cung lon de KIEM CHUNG thuat toan dieu huong.

Muc dich: chung minh thuat toan (Dijkstra tren do thi xac suat + EdgeStats hoc online)
  (1) TIM DUNG duong tren me cung/graph-tree CO THUC su lon (toi trieu node),
  (2) NE duoc 'tuong chan' (gated) ma agent KHONG biet truoc - phai HOC,
  (3) SCALE tot.

Cach lam: thay 'game' that bang me cung sinh ngau nhien. Agent KHONG biet tuong o dau;
  no di mu, gap tuong (move fail) -> EdgeStats hoc -> Dijkstra lan sau ne. Dung CHINH
  thuat toan trong screen_graph.py (khong sua) -> simulator la "su that mat dat".

Render: me cung nho -> PNG (tuong do, duong xanh, duong hoc duoc). Lon -> in metric.

Chay:
  .venv/bin/python automation/maze_sim.py grid 40 40     # ve PNG me cung 40x40
  .venv/bin/python automation/maze_sim.py scale 1000000  # benchmark trieu node
  .venv/bin/python automation/maze_sim.py learn 30 30    # demo hoc ne tuong + PNG
"""
from __future__ import annotations

import heapq
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edge_stats import EdgeStats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "maze")
os.makedirs(OUT, exist_ok=True)


# ======================================================================
# ME CUNG: do thi grid WxH. Node = (r,c). Canh = 4 huong neu khong co tuong CUNG.
# Tuong GATED (an): canh ton tai trong do thi nhung agent di se FAIL cho den khi
# 'mo khoa' - agent khong biet truoc, phai HOC qua that bai. Day la diem mau chot.
# ======================================================================
class Maze:
    def __init__(self, w: int, h: int, gated_frac: float = 0.12, seed: int = 0):
        self.w, self.h = w, h
        rng = random.Random(seed)
        # tuong CUNG: tao bang DFS spanning tree roi them vai canh -> co nhieu duong.
        self.hard: set[tuple] = set()       # canh bi tuong cung (khong bao gio di duoc)
        self.gated: set[tuple] = set()      # canh gated (an, fail cho den khi unlock)
        # sinh me cung perfect bang DFS roi duc them -> da duong (de co duong vong).
        self.tree: set[tuple] = set()       # canh thuoc spanning tree (KHONG gate -> luon co loi giai)
        self._carve(rng)
        # gan gated ngau nhien tren cac canh DUC THEM (khong dung canh tree) ->
        # luon con it nhat 1 duong di duoc tu moi node toi moi node. Agent phai HOC ne.
        for e in list(self._all_open_edges()):
            if e not in self.tree and rng.random() < gated_frac:
                self.gated.add(e)

    @staticmethod
    def _ek(a, b):
        return (a, b) if a <= b else (b, a)

    def _carve(self, rng):
        # bat dau full tuong giua moi cap ke -> DFS pha tuong tao spanning tree.
        all_e = set()
        for r in range(self.h):
            for c in range(self.w):
                if c + 1 < self.w: all_e.add(self._ek((r, c), (r, c + 1)))
                if r + 1 < self.h: all_e.add(self._ek((r, c), (r + 1, c)))
        self.hard = set(all_e)
        stack = [(0, 0)]; seen = {(0, 0)}
        while stack:
            r, c = stack[-1]
            nb = [(r + dr, c + dc) for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0))
                  if 0 <= r + dr < self.h and 0 <= c + dc < self.w and (r + dr, c + dc) not in seen]
            if not nb:
                stack.pop(); continue
            nx = rng.choice(nb)
            self.hard.discard(self._ek((r, c), nx))    # pha tuong -> mo duong
            self.tree.add(self._ek((r, c), nx))        # canh tree: luon di duoc (loi giai)
            seen.add(nx); stack.append(nx)
        # duc them ~30% canh ngau nhien -> co nhieu duong (de tuong gated co dat dung)
        rem = list(self.hard)
        rng.shuffle(rem)
        for e in rem[: int(len(rem) * 0.30)]:
            self.hard.discard(e)

    def _all_open_edges(self):
        for r in range(self.h):
            for c in range(self.w):
                for dr, dc in ((0, 1), (1, 0)):
                    b = (r + dr, c + dc)
                    if 0 <= b[0] < self.h and 0 <= b[1] < self.w:
                        e = self._ek((r, c), b)
                        if e not in self.hard:
                            yield e

    def neighbors(self, n):
        """Canh DI DUOC TRONG DO THI (gated van la canh - agent thay, di moi fail)."""
        r, c = n
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            b = (r + dr, c + dc)
            if 0 <= b[0] < self.h and 0 <= b[1] < self.w and self._ek(n, b) not in self.hard:
                yield b

    def can_pass(self, a, b):
        """SU THAT MAT DAT: canh di duoc khong? gated -> KHONG (cho den khi unlock)."""
        e = self._ek(a, b)
        return e not in self.hard and e not in self.gated

    def unlock(self, a, b):
        self.gated.discard(self._ek(a, b))


# ======================================================================
# AGENT: dung CHINH thuat toan production (Dijkstra trong so + EdgeStats hoc online).
# Khac voi screen_graph chi o cho 'di canh' la sim (can_pass) thay vi click that.
# ======================================================================
class MazeAgent:
    def __init__(self, maze: Maze, stats: EdgeStats):
        self.m = maze
        self.s = stats

    def _edge_cost(self, a, b):
        return self.s.learned_cost(str(a), str(b), 1.0)     # base=1 deu (grid)

    def path(self, start, goal, avoid=None, astar=True):
        """Tim duong + cost hoc duoc. astar=True dung A* (heuristic Manhattan) -
        nhanh hon Dijkstra thuan tren grid lon (it node duyet). astar=False -> Dijkstra.
        `avoid` = tap canh (frozenset {a,b}) cam di trong lan tim nay (tuong da dam)."""
        if start == goal:
            return [start]
        avoid = avoid or set()

        def h(n):                                    # heuristic: khoang cach Manhattan
            return abs(n[0] - goal[0]) + abs(n[1] - goal[1]) if astar else 0.0

        # dung came_from (parent pointer) thay vi luu ca path moi node ->
        # O(V) bo nho thay vi O(V*L) (quan trong o trieu node, tranh OOM).
        pq = [(h(start), 0.0, start)]                # (f=g+h, g, node)
        best = {start: 0.0}
        came = {start: None}
        while pq:
            _, g, cur = heapq.heappop(pq)
            if cur == goal:
                out = []                             # dung lai duong tu parent pointer
                while cur is not None:
                    out.append(cur); cur = came[cur]
                return out[::-1]
            if g > best.get(cur, math.inf):
                continue
            for nxt in self.m.neighbors(cur):
                if frozenset((cur, nxt)) in avoid:
                    continue                         # canh da dam tuong lan nay -> bo
                ng = g + self._edge_cost(cur, nxt)
                if ng < best.get(nxt, math.inf):
                    best[nxt] = ng
                    came[nxt] = cur
                    heapq.heappush(pq, (ng + h(nxt), ng, nxt))
        return None

    def navigate(self, start, goal, max_steps=100000):
        """Di tu start->goal, HOC online khi gap tuong (gated). Tra (toi_dich, lich_su).
        Tuong dam trong lan nay -> cam di lai (avoid) de khoi lap; van GHI vao stats
        de lan SAU (navigate khac) da biet ne tu dau."""
        cur = start
        trail = [cur]
        bumped = set()                               # canh da dam tuong trong lan nay
        for _ in range(max_steps):
            if cur == goal:
                return True, trail
            p = self.path(cur, goal, avoid=bumped)
            if not p or len(p) < 2:
                return False, trail                  # bi cô lap boi tuong da hoc
            nxt = p[1]
            if self.m.can_pass(cur, nxt):            # di duoc that
                self.s.record(str(cur), str(nxt), True)
                cur = nxt; trail.append(cur)
            else:                                    # GAP TUONG -> hoc + cam di lai
                self.s.record(str(cur), str(nxt), False)
                bumped.add(frozenset((cur, nxt)))
        return False, trail


# ======================================================================
# RENDER (me cung nho)
# ======================================================================
def render(maze: Maze, trail, start, goal, fname):
    import numpy as np
    import cv2
    cell = 16
    H, W = maze.h * cell, maze.w * cell
    img = np.full((H + 1, W + 1, 3), 255, np.uint8)

    def px(rc):
        return rc[1] * cell + cell // 2, rc[0] * cell + cell // 2

    # ve tuong (canh bi chan): hard=den, gated=do
    for r in range(maze.h):
        for c in range(maze.w):
            for dr, dc in ((0, 1), (1, 0)):
                b = (r + dr, c + dc)
                if not (0 <= b[0] < maze.h and 0 <= b[1] < maze.w):
                    continue
                e = maze._ek((r, c), b)
                a1, a2 = px((r, c)), px(b)
                mid = ((a1[0] + a2[0]) // 2, (a1[1] + a2[1]) // 2)
                if e in maze.hard:
                    cv2.line(img, a1, a2, (200, 200, 200), 1)        # tuong cung mo
                elif e in maze.gated:
                    cv2.circle(img, mid, 3, (0, 0, 255), -1)         # tuong gated = do
    # ve duong di thuc te (trail) xanh la
    for i in range(len(trail) - 1):
        cv2.line(img, px(trail[i]), px(trail[i + 1]), (0, 180, 0), 2)
    cv2.circle(img, px(start), 5, (255, 0, 0), -1)                   # start xanh duong
    cv2.circle(img, px(goal), 5, (0, 0, 0), -1)                      # goal den
    path = os.path.join(OUT, fname)
    cv2.imwrite(path, img)
    return path


# ======================================================================
# LENH
# ======================================================================
def cmd_grid(w, h):
    """Ve me cung + duong tim duoc (chua hoc, lan dau gap tuong nao re tuong do)."""
    m = Maze(w, h, seed=1)
    a = MazeAgent(m, EdgeStats("/tmp/maze_grid.json"))
    if os.path.exists("/tmp/maze_grid.json"): os.remove("/tmp/maze_grid.json")
    a.s = EdgeStats("/tmp/maze_grid.json")
    start, goal = (0, 0), (h - 1, w - 1)
    ok, trail = a.navigate(start, goal)
    p = render(m, trail, start, goal, f"grid_{w}x{h}.png")
    print(f"grid {w}x{h}: toi dich={ok}, so buoc={len(trail)}, "
          f"tuong gated={len(m.gated)}, anh={p}")


def cmd_learn(w, h):
    """Demo HOC: chay 1 (gap nhieu tuong) vs chay 2 (da hoc -> it dam tuong)."""
    m = Maze(w, h, seed=3)
    es = EdgeStats("/tmp/maze_learn.json")
    if os.path.exists("/tmp/maze_learn.json"): os.remove("/tmp/maze_learn.json")
    es = EdgeStats("/tmp/maze_learn.json")
    a = MazeAgent(m, es)
    start, goal = (0, 0), (h - 1, w - 1)

    # lan 1: di mu
    bumps1 = sum(v["fail"] for v in es.data.values())
    ok1, trail1 = a.navigate(start, goal)
    bumps1 = sum(v["fail"] for v in es.data.values())
    render(m, trail1, start, goal, f"learn_{w}x{h}_run1.png")

    # lan 2: cung dich, da co kinh nghiem -> it dam tuong hon
    ok2, trail2 = a.navigate(start, goal)
    bumps2 = sum(v["fail"] for v in es.data.values()) - bumps1
    p2 = render(m, trail2, start, goal, f"learn_{w}x{h}_run2.png")
    print(f"learn {w}x{h}: tuong gated={len(m.gated)}")
    print(f"  lan 1 (di mu):     toi dich={ok1}, dam tuong={bumps1}, buoc={len(trail1)}")
    print(f"  lan 2 (da hoc):    toi dich={ok2}, dam tuong THEM={bumps2}, buoc={len(trail2)}")
    print(f"  => giam dam tuong: {bumps1} -> {bumps2} (hoc duoc tuong o dau). anh: {p2}")


def cmd_scale(n):
    """Benchmark: do thi ~n node (grid sqrt) -> do thoi gian Dijkstra 1 truy van."""
    side = int(math.sqrt(n))
    nodes = side * side
    print(f"scale: tao grid {side}x{side} = {nodes:,} node ...")
    t0 = time.time()
    m = Maze(side, side, gated_frac=0.05, seed=7)
    t_build = time.time() - t0
    a = MazeAgent(m, EdgeStats("/tmp/maze_scale.json"))
    if os.path.exists("/tmp/maze_scale.json"): os.remove("/tmp/maze_scale.json")
    a.s = EdgeStats("/tmp/maze_scale.json")
    start, goal = (0, 0), (side - 1, side - 1)
    t0 = time.time()
    pd = a.path(start, goal, astar=False)            # Dijkstra thuan
    t_dij = time.time() - t0
    t0 = time.time()
    pa = a.path(start, goal, astar=True)             # A* (heuristic Manhattan)
    t_ast = time.time() - t0
    print(f"  build {t_build:.2f}s | {nodes:,} node")
    print(f"  Dijkstra: {t_dij:.3f}s, do dai={len(pd) if pd else 'X'}")
    print(f"  A*      : {t_ast:.3f}s, do dai={len(pa) if pa else 'X'}  "
          f"(nhanh {t_dij/max(t_ast,1e-9):.1f}x)")


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == "grid":
        cmd_grid(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "learn":
        cmd_learn(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "scale":
        cmd_scale(int(sys.argv[2]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
