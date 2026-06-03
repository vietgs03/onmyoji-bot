#!/usr/bin/env python3
"""
maze_bench.py - BENCHMARK RANDOM HOA + do DO HOC HOI (learning curve).

Tai sao: 1 test case co the may man (data 'da hieu biet qua'). De danh gia THAT,
  phai random hoa NHIEU test case (nhieu seed/kich thuoc/start-goal) va do thong ke
  voi khoang tin cay -> tranh overfit. Va quan trong: do DO HOC HOI = hieu qua tang
  dan qua cac lan (episode)/version. Model hoc tot -> agent tot.

3 bai do:
  A. BATTERY random: N me cung x M cap (start,goal) ngau nhien. So sanh:
       - no-learn   : khong nho gi (moi lan nhu lan dau) - BASELINE.
       - learn-Dij  : Dijkstra + EdgeStats hoc.
       - learn-A*   : A* (heuristic Manhattan) + EdgeStats hoc.
     Metric: success rate, dam tuong trung binh, do dai/optimal (do toi uu).
  B. LEARNING CURVE: cung 1 me cung, chay K episode lien tiep (giu stats) ->
     dam tuong giam dan ra sao. Day la 'duong cong hoc' cua model.
  C. VERSION GAIN: gia lap 'nhieu version' = nhieu vong huan luyen, do do nhan dien
     (reach rate) + hieu qua (bumps) cai thien qua tung version.

Chay:
  .venv/bin/python automation/maze_bench.py battery
  .venv/bin/python automation/maze_bench.py curve
  .venv/bin/python automation/maze_bench.py all
"""
from __future__ import annotations

import os, sys, math, random, statistics, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from maze_sim import Maze, MazeAgent
from edge_stats import EdgeStats


def fresh_stats():
    """EdgeStats sach (file tam moi) -> moi lan benchmark khong dinh nhau."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd); os.remove(path)
    return EdgeStats(path)


def bfs_optimal(maze, start, goal):
    """Do dai duong NGAN NHAT THAT (chi qua canh KHONG gated) - de tinh do toi uu."""
    from collections import deque
    q = deque([(start, 0)]); seen = {start}
    while q:
        n, d = q.popleft()
        if n == goal:
            return d
        for nb in maze.neighbors(n):
            if maze.can_pass(n, nb) and nb not in seen:
                seen.add(nb); q.append((nb, d + 1))
    return None


def ci95(xs):
    """Khoang tin cay 95% cua trung binh (xap xi normal)."""
    if len(xs) < 2:
        return (xs[0] if xs else 0.0, 0.0)
    m = statistics.mean(xs); sd = statistics.pstdev(xs)
    return m, 1.96 * sd / math.sqrt(len(xs))


# ----------------------------------------------------------------------
# A. BATTERY random
# ----------------------------------------------------------------------
def battery(n_mazes=40, n_pairs=5, size=25, gated=0.15, seed0=1000):
    print(f"=== A. BATTERY RANDOM: {n_mazes} me cung x {n_pairs} cap (start,goal), "
          f"{size}x{size}, gated~{gated:.0%} ===")
    modes = {
        "no-learn ": dict(learn=False, astar=False),
        "learn-Dij": dict(learn=True,  astar=False),
        "learn-A* ": dict(learn=True,  astar=True),
    }
    agg = {k: {"reach": [], "bumps": [], "ratio": []} for k in modes}

    rng = random.Random(seed0)
    for i in range(n_mazes):
        m = Maze(size, size, gated_frac=gated, seed=seed0 + i)
        pairs = []
        while len(pairs) < n_pairs:
            s = (rng.randrange(size), rng.randrange(size))
            g = (rng.randrange(size), rng.randrange(size))
            if s != g and bfs_optimal(m, s, g) is not None:   # chi cap co loi giai
                pairs.append((s, g))
        for mode, opt in modes.items():
            # MOI mode lam lai tu stats sach tren CUNG me cung+pairs (cong bang).
            for (s, g) in pairs:
                a = MazeAgent(m, fresh_stats())
                r = a.navigate(s, g, **opt)
                agg[mode]["reach"].append(1.0 if r["reached"] else 0.0)
                agg[mode]["bumps"].append(r["bumps"])
                best = bfs_optimal(m, s, g) or 1
                if r["reached"] and best > 0:
                    agg[mode]["ratio"].append(r["steps"] / best)

    print(f"\n{'mode':10} {'reach%':>8} {'bumps(tb±ci)':>16} {'do_dai/optimal':>16}")
    for mode in modes:
        rc, _ = ci95(agg[mode]["reach"])
        bm, bci = ci95(agg[mode]["bumps"])
        rt, rci = ci95(agg[mode]["ratio"]) if agg[mode]["ratio"] else (0, 0)
        print(f"{mode:10} {rc*100:7.1f}% {bm:7.2f}±{bci:.2f}     {rt:7.2f}±{rci:.2f}")
    print("  (reach%: ty le toi dich | bumps: lan dam tuong | do_dai/optimal: 1.0=toi uu)")


# ----------------------------------------------------------------------
# B. LEARNING CURVE
# ----------------------------------------------------------------------
def curve(size=30, gated=0.18, episodes=8, n_mazes=20, seed0=2000):
    print(f"\n=== B. LEARNING CURVE: {n_mazes} me cung, moi cung chay {episodes} "
          f"episode (giu stats) - do dam tuong giam dan ===")
    # trung binh bumps theo episode tren nhieu me cung
    per_ep = [[] for _ in range(episodes)]
    per_ep_reach = [[] for _ in range(episodes)]
    for i in range(n_mazes):
        m = Maze(size, size, gated_frac=gated, seed=seed0 + i)
        s, g = (0, 0), (size - 1, size - 1)
        if bfs_optimal(m, s, g) is None:
            continue
        a = MazeAgent(m, fresh_stats())                 # GIU stats qua cac episode
        for ep in range(episodes):
            r = a.navigate(s, g, learn=True, astar=True)
            per_ep[ep].append(r["bumps"])
            per_ep_reach[ep].append(1.0 if r["reached"] else 0.0)

    print(f"\n{'episode':>8} {'dam tuong (tb±ci)':>20} {'reach%':>8}  duong cong")
    base = statistics.mean(per_ep[0]) if per_ep[0] else 1
    for ep in range(episodes):
        bm, bci = ci95(per_ep[ep])
        rc, _ = ci95(per_ep_reach[ep])
        bar = "#" * int(round(bm / max(base, 1e-9) * 30))
        print(f"{ep:8} {bm:9.2f}±{bci:5.2f}      {rc*100:6.1f}%  {bar}")
    print(f"  => dam tuong ep0={statistics.mean(per_ep[0]):.2f} -> "
          f"ep{episodes-1}={statistics.mean(per_ep[-1]):.2f} "
          f"(giam {(1-statistics.mean(per_ep[-1])/max(base,1e-9))*100:.0f}%). "
          f"Day la DO HOC HOI cua model.")


# ----------------------------------------------------------------------
# C. VERSION GAIN (nhieu vong huan luyen -> do cai thien)
# ----------------------------------------------------------------------
def version_gain(size=28, gated=0.2, versions=5, train_runs=4, n_mazes=15, seed0=3000):
    print(f"\n=== C. VERSION GAIN: {n_mazes} me cung, {versions} version "
          f"(moi version = +{train_runs} vong train) - do nhan dien tang ===")
    print(f"\n{'version':>8} {'reach% (eval)':>14} {'bumps (eval)':>14}")
    for v in range(versions):
        reach, bumps = [], []
        for i in range(n_mazes):
            m = Maze(size, size, gated_frac=gated, seed=seed0 + i)
            s, g = (0, 0), (size - 1, size - 1)
            if bfs_optimal(m, s, g) is None:
                continue
            a = MazeAgent(m, fresh_stats())
            for _ in range(v * train_runs):             # train v*train_runs vong
                a.navigate(s, g, learn=True, astar=True)
            r = a.navigate(s, g, learn=False, astar=True)   # EVAL (khong hoc them)
            reach.append(1.0 if r["reached"] else 0.0)
            bumps.append(r["bumps"])
        print(f"{v:8} {statistics.mean(reach)*100:13.1f}% {statistics.mean(bumps):13.2f}")
    print("  => qua tung version (train nhieu hon), bumps giam = model nhan dien tuong tot hon.")


def correctness(n_mazes=50, n_pairs=10, size=20, gated=0.0, seed0=9000):
    """KIEM DUNG: tren me cung KHONG gated, navigate phai cho do dai = BFS optimal
    (vi cost=1 deu -> Dijkstra/A* == BFS). Random nhieu case de bat sai sot."""
    print(f"=== D. CORRECTNESS: {n_mazes}x{n_pairs} cap random (no gated) "
          f"- navigate phai = BFS optimal ===")
    rng = random.Random(seed0)
    ok = tot = 0
    worst = 0
    for i in range(n_mazes):
        m = Maze(size, size, gated_frac=gated, seed=seed0 + i)
        for _ in range(n_pairs):
            s = (rng.randrange(size), rng.randrange(size))
            g = (rng.randrange(size), rng.randrange(size))
            opt = bfs_optimal(m, s, g)
            if opt is None or s == g:
                continue
            a = MazeAgent(m, fresh_stats())
            r = a.navigate(s, g, learn=False, astar=True)
            tot += 1
            if r["reached"] and r["steps"] == opt:
                ok += 1
            else:
                worst = max(worst, abs(r["steps"] - opt))
    print(f"  navigate == BFS optimal: {ok}/{tot} = {ok/tot:.3f}  "
          f"(sai lech toi da: {worst} buoc)")
    return ok == tot


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("correct", "all"):
        correctness()
    if cmd in ("battery", "all"):
        battery()
    if cmd in ("curve", "all"):
        curve()
    if cmd in ("version", "all"):
        version_gain()


if __name__ == "__main__":
    main()
