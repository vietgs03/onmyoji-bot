#!/usr/bin/env python3
"""Phan tich logs/farm_soul_stats.jsonl: thong ke per-run + phan bo dur_s.

Dung:  .venv/bin/python tasks/analyze_soul.py [run_id]
Khong tham so -> phan tich TAT CA run (moi run 1 block) + tong hop.
"""
import json
import os
import sys
import statistics as st

LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "logs", "farm_soul_stats.jsonl")


def load():
    rows = []
    with open(LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def hist(durs, bins=(0, 40, 45, 50, 60, 75, 90, 120, 999)):
    """ASCII histogram theo cac moc thoi gian (giay)."""
    counts = [0] * (len(bins) - 1)
    for d in durs:
        for i in range(len(bins) - 1):
            if bins[i] <= d < bins[i + 1]:
                counts[i] += 1
                break
    out = []
    mx = max(counts) or 1
    for i, c in enumerate(counts):
        bar = "#" * int(40 * c / mx)
        out.append(f"  [{bins[i]:>3}-{bins[i+1]:>3}s) {c:>3} {bar}")
    return "\n".join(out)


def analyze_run(rows, run_id):
    rounds = [r for r in rows if r.get("run") == run_id and "round" in r]
    summ = next((r for r in rows if r.get("run") == run_id and r.get("summary")), None)
    if not rounds:
        return
    durs = [r["dur_s"] for r in rounds]
    wins = sum(1 for r in rounds if r.get("won"))
    print(f"\n=== RUN {run_id} ===")
    print(f"  vong:      {len(rounds)}   wins: {wins}  ({wins/len(rounds)*100:.1f}%)")
    print(f"  dur_s:     min={min(durs):.1f} max={max(durs):.1f} "
          f"mean={st.mean(durs):.1f} median={st.median(durs):.1f} "
          f"stdev={st.pstdev(durs):.1f}")
    print(f"  tong:      {sum(durs):.0f}s = {sum(durs)/60:.1f} phut")
    # vong cham bat thuong (>90s = co retry/battle kho)
    slow = [(r["round"], r["dur_s"]) for r in rounds if r["dur_s"] > 90]
    if slow:
        print(f"  cham >90s: {slow}")
    print("  phan bo dur_s:")
    print(hist(durs))
    if summ:
        print(f"  stamina:   {summ.get('stamina_start')} -> {summ.get('stamina_end')} "
              f"(dung {summ.get('stamina_used')}, "
              f"{(summ.get('stamina_used') or 0)/max(len(rounds),1):.1f}/vong)")
        print(f"  counter:   {summ.get('counter_start')} -> {summ.get('counter_end')}")


def main():
    rows = load()
    runs = []
    for r in rows:
        if "round" in r and r["run"] not in runs:
            runs.append(r["run"])
    if len(sys.argv) > 1:
        runs = [sys.argv[1]]
    for rid in runs:
        analyze_run(rows, rid)
    # tong hop tat ca vong
    all_durs = [r["dur_s"] for r in rows if "round" in r]
    all_wins = sum(1 for r in rows if "round" in r and r.get("won"))
    if all_durs:
        print(f"\n=== TONG HOP ({len(all_durs)} vong, {len(runs)} run) ===")
        print(f"  win_rate:  {all_wins/len(all_durs)*100:.1f}%")
        print(f"  dur_s:     mean={st.mean(all_durs):.1f} median={st.median(all_durs):.1f} "
              f"stdev={st.pstdev(all_durs):.1f}")
        print("  phan bo:")
        print(hist(all_durs))


if __name__ == "__main__":
    main()
