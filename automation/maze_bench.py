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


def _far_pair(m, size, rng, min_frac=0.5, tries=40):
    """Random 1 cap (start,goal) co loi giai VA cach nhau XA (>= min_frac*duong cheo).
    Ep duong dai de test NANG, tranh start/goal sat nhau (test nhe).
    Toi uu: uoc luong Manhattan TRUOC, chi BFS khi du xa (BFS dat tren maze lon)."""
    want = int((size * 2) * min_frac)           # nguong do dai toi thieu
    best = None
    for _ in range(tries):
        s = (rng.randrange(size), rng.randrange(size))
        g = (rng.randrange(size), rng.randrange(size))
        if s == g:
            continue
        if abs(s[0]-g[0]) + abs(s[1]-g[1]) < want:
            continue                            # Manhattan < want -> chac chan khong du xa
        opt = bfs_optimal(m, s, g)              # chi BFS khi co tiem nang
        if opt is None:
            continue
        if opt >= want:
            return s, g, opt
        if best is None or opt > best[2]:
            best = (s, g, opt)
    if best:
        return best
    # fallback: lay bat ky cap co loi giai (maze gated nang co the it cap xa)
    for _ in range(tries):
        s = (rng.randrange(size), rng.randrange(size))
        g = (rng.randrange(size), rng.randrange(size))
        if s == g:
            continue
        opt = bfs_optimal(m, s, g)
        if opt:
            return s, g, opt
    return None


# ----------------------------------------------------------------------
# A. BATTERY random
# ----------------------------------------------------------------------
def battery(n_mazes=20, n_pairs=4, size=50, gated=0.22, seed0=1000):
    print(f"=== A. BATTERY RANDOM: {n_mazes} me cung x {n_pairs} cap (start,goal) XA, "
          f"{size}x{size}={size*size} node, gated~{gated:.0%} ===", flush=True)
    modes = {
        "no-learn ": dict(learn=False, astar=False),
        "learn-Dij": dict(learn=True,  astar=False),
        "learn-A* ": dict(learn=True,  astar=True),
    }
    agg = {k: {"reach": [], "bumps": [], "ratio": []} for k in modes}

    rng = random.Random(seed0)
    for i in range(n_mazes):
        if i % 5 == 0:
            print(f"  ...maze {i}/{n_mazes}", flush=True)
        m = Maze(size, size, gated_frac=gated, seed=seed0 + i)
        pairs = []
        while len(pairs) < n_pairs:
            pr = _far_pair(m, size, rng)         # cap XA nhau, co loi giai
            if pr:
                pairs.append((pr[0], pr[1]))
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
def curve(size=50, gated=0.22, episodes=8, n_mazes=15, seed0=2000):
    print(f"\n=== B. LEARNING CURVE: {n_mazes} me cung {size}x{size}, moi cung {episodes} "
          f"episode (giu stats), start/goal RANDOM moi episode - dam tuong giam ===")
    # trung binh bumps theo episode tren nhieu me cung
    per_ep = [[] for _ in range(episodes)]
    per_ep_reach = [[] for _ in range(episodes)]
    rng = random.Random(seed0)
    for i in range(n_mazes):
        m = Maze(size, size, gated_frac=gated, seed=seed0 + i)
        a = MazeAgent(m, fresh_stats())                 # GIU stats qua cac episode
        for ep in range(episodes):
            pr = _far_pair(m, size, rng)                # RANDOM cap moi episode
            if not pr:
                continue
            s, g, _ = pr
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
def version_gain(size=50, gated=0.25, versions=5, train_runs=5, n_mazes=12, seed0=3000):
    print(f"\n=== C. VERSION GAIN: {n_mazes} me cung {size}x{size}, {versions} version "
          f"(moi version = +{train_runs} vong train, cap RANDOM) ===")
    print("    Train tren cap start/goal RANDOM, EVAL tren cap RANDOM KHAC")
    print("    -> do TONG QUAT HOA (hoc ban do tuong chung), khong overfit 1 duong.\n")
    print(f"{'version':>8} {'reach% (eval)':>14} {'bumps (eval)':>14}")
    for v in range(versions):
        reach, bumps = [], []
        rng_eval = random.Random(seed0 + 777)      # cap EVAL co dinh moi version (cong bang)
        for i in range(n_mazes):
            m = Maze(size, size, gated_frac=gated, seed=seed0 + i)
            a = MazeAgent(m, fresh_stats())
            rng_train = random.Random(seed0 + 100 + i)
            for _ in range(v * train_runs):         # train tren cap RANDOM khac nhau
                pr = _far_pair(m, size, rng_train)
                if pr:
                    a.navigate(pr[0], pr[1], learn=True, astar=True)
            # EVAL tren cap random rieng (KHONG trung train) -> tong quat hoa
            pe = _far_pair(m, size, rng_eval)
            if not pe:
                continue
            r = a.navigate(pe[0], pe[1], learn=False, astar=True)
            reach.append(1.0 if r["reached"] else 0.0)
            bumps.append(r["bumps"])
        print(f"{v:8} {statistics.mean(reach)*100:13.1f}% {statistics.mean(bumps):13.2f}")
    print("  => version cao (train nhieu cap khac nhau) -> bumps eval giam = model")
    print("     hoc duoc BAN DO TUONG, tong quat sang cap moi (khong chi thuoc 1 duong).")


def correctness(n_mazes=50, n_pairs=10, size=40, gated=0.0, seed0=9000):
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
