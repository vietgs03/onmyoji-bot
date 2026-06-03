#!/usr/bin/env python3
"""
edge_stats.py - HOC ONLINE do tin cay canh dieu huong (Stochastic Shortest Path).

Bai toan (ML): do thi dieu huong KHONG tat dinh:
  - Canh co the TAC (gated content: 'mo o Lv30', nut xam, event het han).
  - Canh STOCHASTIC: OCR truot ~30%, loading lau khac nhau.
  - Hu hong thay doi theo thoi gian (event reset).

Giai phap: thay cost gan tay bang cost HOC tu thuc te. Moi canh giu (success, fail).
  P_success uoc luong theo Beta posterior (Laplace/Bayesian smoothing) -> on dinh
  ca khi it data. cost = -log(P_success) + penalty_latency. Canh hay fail -> cost
  cao -> Dijkstra TU NE (chinh la 'biet tuong chan o dau').

Phat hien TUONG (blocked edge): fail lien tuc >= BLOCK_FAILS -> danh dau blocked_until
  (loai tam khoi do thi). Sau COOLDOWN thu lai (event co the mo lai).

Du lieu ben ngoai code (knowledge/edge_stats.json) -> hoc tang dan qua cac lan chay.
"""
from __future__ import annotations

import json
import math
import os
import time
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS_JSON = os.path.join(ROOT, "knowledge", "edge_stats.json")

# Beta prior: tin canh moi ~80% thanh cong (lac quan vua phai) cho den khi co data.
PRIOR_ALPHA = 4.0     # so 'thanh cong ao' ban dau
PRIOR_BETA = 1.0      # so 'that bai ao' ban dau

# Phat hien tuong: fail lien tuc bao nhieu lan thi coi canh BI CHAN.
BLOCK_FAILS = 3
# Sau khi chan, bao lau (giay) moi thu lai (event/gated co the mo). 6 gio.
BLOCK_COOLDOWN = 6 * 3600

# Tran cost de canh fail nang van con tham duoc neu KHONG con duong khac
# (tranh cost=inf lam mat ket noi do thi).
COST_CEIL = 12.0
# Phat them moi giay latency trung binh cua canh (uu tien canh nhanh).
LATENCY_WEIGHT = 0.15


class EdgeStats:
    """Kho thong ke canh + tinh cost hoc duoc. Key canh = 'src->dst'."""

    def __init__(self, path: str = STATS_JSON):
        self.path = path
        self.data: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                self.data = json.load(open(path))
            except Exception:
                self.data = {}

    # ---------- truy cap ----------
    @staticmethod
    def _key(src: str, dst: str) -> str:
        return f"{src}->{dst}"

    def _rec(self, src: str, dst: str) -> dict:
        k = self._key(src, dst)
        if k not in self.data:
            self.data[k] = {"success": 0, "fail": 0, "fail_streak": 0,
                            "lat_sum": 0.0, "lat_n": 0, "blocked_until": 0.0}
        return self.data[k]

    # ---------- ghi nhan ket qua 1 lan di canh ----------
    def record(self, src: str, dst: str, ok: bool, latency: float = 0.0) -> None:
        r = self._rec(src, dst)
        if ok:
            r["success"] += 1
            r["fail_streak"] = 0
            r["blocked_until"] = 0.0                    # thanh cong -> bo c%% chan
        else:
            r["fail"] += 1
            r["fail_streak"] += 1
            if r["fail_streak"] >= BLOCK_FAILS:         # phat hien TUONG
                r["blocked_until"] = time.time() + BLOCK_COOLDOWN
        if latency > 0:
            r["lat_sum"] += latency
            r["lat_n"] += 1

    # ---------- truy van ----------
    def is_blocked(self, src: str, dst: str) -> bool:
        r = self.data.get(self._key(src, dst))
        return bool(r and r.get("blocked_until", 0) > time.time())

    def p_success(self, src: str, dst: str) -> float:
        """Uoc luong P(thanh cong) theo Beta posterior (smoothing)."""
        r = self.data.get(self._key(src, dst))
        s = (r["success"] if r else 0) + PRIOR_ALPHA
        f = (r["fail"] if r else 0) + PRIOR_BETA
        return s / (s + f)

    def avg_latency(self, src: str, dst: str) -> float:
        r = self.data.get(self._key(src, dst))
        if r and r.get("lat_n"):
            return r["lat_sum"] / r["lat_n"]
        return 0.0

    def learned_cost(self, src: str, dst: str, base: float) -> float:
        """Cost hoc duoc = base * (-log P_success) + phat latency.
        base = cost tinh (DEFAULT/BACK/per-edge). Canh bi chan -> COST_CEIL (khong inf
        de van con duong neu BAT BUOC). P=1 -> -log≈0 -> can base lam san."""
        if self.is_blocked(src, dst):
            return COST_CEIL
        p = self.p_success(src, dst)
        # base + thanh phan rui ro: cang it tin cay -> cang dat.
        risk = -math.log(max(p, 1e-3))                 # p=1->0, p=0.5->0.69, p=0.1->2.3
        cost = base + risk + LATENCY_WEIGHT * self.avg_latency(src, dst)
        return min(cost, COST_CEIL)

    # ---------- luu ----------
    def save(self) -> None:
        json.dump(self.data, open(self.path, "w"), indent=1, ensure_ascii=False)

    # ---------- bao cao (de debug/eval) ----------
    def report(self) -> list[tuple[str, float, int, int, bool]]:
        """Tra [(canh, p_success, success, fail, blocked)] sap theo p tang dan."""
        out = []
        for k, r in self.data.items():
            src, dst = k.split("->", 1)
            out.append((k, self.p_success(src, dst), r["success"], r["fail"],
                        self.is_blocked(src, dst)))
        out.sort(key=lambda t: t[1])
        return out


def main():
    import sys
    es = EdgeStats()
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        print(f"{'canh':30} {'P':>5} {'OK':>4} {'fail':>5} blocked")
        for k, p, s, f, b in es.report():
            print(f"{k:30} {p:5.2f} {s:4d} {f:5d} {'YES' if b else ''}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
