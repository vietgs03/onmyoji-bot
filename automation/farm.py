#!/usr/bin/env python3
"""Farm engine: vong lap danh + nhan thuong cho cac che do Onmyoji.

TRIET LY (giong screen_graph): KHONG hardcode toa do. Moi vong:
  1) chup + OCR -> nhan dien TRANG THAI battle hien tai (qua keyword semantic).
  2) chon HANH DONG theo trang thai (bam nut tim duoc qua OCR, hoac tap giua man).
  3) lap den khi du so tran / het ve / loi.

Cac che do battle Onmyoji deu chia se 1 vong trang thai chung:
    SELECT  : man chon (co nut 'Challenge'/'Battle'/so level) -> bam vao tran
    PREPARE : man dan doi hinh (co 'Ready'/'Battle'/'Auto') -> bam Ready/Battle
    FIGHTING: dang danh (it text, co thanh HP / 'Auto'/'Speed') -> CHO
    RESULT  : ket qua (co 'Victory'/'Defeat'/'Reward'/'Tap to') -> tap de qua
    BLOCKED : het ve / het luot (co 'No more'/'Insufficient'/'Stamina') -> DUNG

Trang thai nhan qua FarmState.detect() = keyword khop nhieu nhat. Hanh dong la
data-driven (bang ACTIONS), khong if-else rai rac -> de them che do / sua doc.
"""
import os
import sys
import time
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "automation"))
from agent import Agent          # noqa: E402
from screen_graph import ScreenGraph  # noqa: E402

LOG = os.path.join(ROOT, "logs", "farm.jsonl")
WIN_W, WIN_H = 1152, 679          # cua so game; center = giua man (tap qua result)


# ---------------------------------------------------------------------------
# TRANG THAI battle: ten -> keyword OCR dac trung (khop >=1 = o trang thai do).
# Xep theo do uu tien khi nhieu trang thai cung khop (RESULT/BLOCKED truoc).
# ---------------------------------------------------------------------------
STATES = {
    # het tai nguyen -> dung han (uu tien cao nhat de khong danh vo ich)
    "BLOCKED":  ["No more", "Insufficient", "not enough", "depleted",
                 "Stamina", "tickets left", "Get more"],
    # ket qua tran -> tap qua (Victory/Defeat/reward/continue)
    "RESULT":   ["Victory", "Defeat", "Reward", "Tap to", "Continue",
                 "Obtained", "EXP", "Settlement"],
    # dan doi hinh truoc tran -> bam Ready/Battle de vao danh
    "PREPARE":  ["Ready", "Prepare", "Start Battle", "Auto Battle"],
    # dang danh -> CHO (it text dang ke; nhan qua 'Auto'/'Speed'/'Surrender')
    "FIGHTING": ["Surrender", "Speed", "Pause"],
    # man chon tran/level -> bam vao tran de bat dau
    "SELECT":   ["Challenge", "Battle", "Sweep", "Quick", "Enter"],
}

# HANH DONG cho moi trang thai. (kind, arg)
#   tap_text : bam text dau tien khop arg (OCR tim toa do that)
#   tap_center: tap giua man (qua result / fighting cho)
#   wait     : cho on dinh
#   stop     : dung vong lap
ACTIONS = {
    "BLOCKED":  ("stop", None),
    "RESULT":   ("tap_center", None),            # tap bat ky de bo qua man ket qua
    "PREPARE":  ("tap_text", ["Ready", "Battle", "Start"]),
    "FIGHTING": ("wait", 3.0),                   # cho danh xong
    "SELECT":   ("tap_text", ["Challenge", "Battle", "Enter", "Sweep"]),
    None:       ("tap_center", None),            # khong ro -> tap giua, doc lai
}


class FarmState:
    """Nhan dien trang thai battle tu 1 ScreenReader."""

    @staticmethod
    def detect(reader) -> tuple[str | None, int]:
        """Tra (ten_trang_thai, so_keyword_khop). None neu khong khop gi."""
        for name, kws in STATES.items():          # theo thu tu uu tien
            hits = sum(1 for k in kws if reader.has(k))
            if hits > 0:
                return name, hits
        return None, 0


class Farmer:
    """Chay vong farm 1 che do. `mode_node` = node screen_graph cua man che do.

    Vd: Farmer(a, 'soul_zones').run(max_battles=3). Goto vao node truoc roi lap
    detect->act. KHONG biet toa do nut - tim qua OCR moi vong."""

    def __init__(self, agent: Agent, mode_node: str):
        self.a = agent
        self.g = ScreenGraph(agent)
        self.mode = mode_node

    def _log(self, **kw):
        kw["t"] = round(time.time(), 1)
        with open(LOG, "a") as f:
            f.write(json.dumps(kw, ensure_ascii=False) + "\n")

    def run(self, max_battles: int = 3, max_loops: int = 60,
            verbose: bool = True) -> dict:
        """Vong farm. Dem so lan vao RESULT (1 tran xong) -> dung khi du max_battles
        hoac BLOCKED hoac qua max_loops (chong treo). Tra thong ke."""
        # 1) di toi man che do
        if not self.g.goto(self.mode, verbose=False):
            self._log(ev="goto_fail", mode=self.mode)
            return {"ok": False, "reason": "khong toi duoc man", "battles": 0}

        battles, loops = 0, 0
        last_state = None
        stuck = 0
        while battles < max_battles and loops < max_loops:
            loops += 1
            r = self.a.read()
            state, hits = FarmState.detect(r)
            if verbose:
                print(f"[farm] loop {loops}: state={state}({hits}) battles={battles}")
            self._log(ev="loop", i=loops, state=state, hits=hits, battles=battles)

            # dem 1 tran khi vao RESULT lan dau (khong dem lap khi van o RESULT)
            if state == "RESULT" and last_state != "RESULT":
                battles += 1

            # chong ket: cung trang thai 'SELECT/PREPARE' lien tuc ma khong tien
            if state == last_state and state in ("SELECT", "PREPARE"):
                stuck += 1
                if stuck >= 5:
                    self._log(ev="stuck", state=state)
                    if verbose:
                        print(f"[farm] KET o {state} 5 vong -> dung")
                    break
            else:
                stuck = 0
            last_state = state

            kind, arg = ACTIONS.get(state, ACTIONS[None])
            if kind == "stop":
                self._log(ev="blocked")
                if verbose:
                    print("[farm] BLOCKED (het ve/luot) -> dung")
                break
            elif kind == "wait":
                time.sleep(arg)
            elif kind == "tap_center":
                self.a.tap(WIN_W // 2, WIN_H // 2)
                time.sleep(1.5)
            elif kind == "tap_text":
                done = False
                for txt in arg:
                    res = self.a.tap_text(txt)
                    ok = res[0] if isinstance(res, tuple) else res
                    if ok:
                        done = True
                        break
                if not done:                       # khong tim thay nut -> tap giua
                    self.a.tap(WIN_W // 2, WIN_H // 2)
                time.sleep(2.0)

        result = {"ok": True, "battles": battles, "loops": loops,
                  "blocked": last_state == "BLOCKED", "mode": self.mode}
        self._log(ev="done", **result)
        if verbose:
            print(f"[farm] XONG: {battles} tran / {loops} vong | mode={self.mode}")
        return result


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "soul_zones"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    a = Agent()
    try:
        res = Farmer(a, mode).run(max_battles=n)
        print(json.dumps(res, ensure_ascii=False))
    finally:
        a.c.close()


if __name__ == "__main__":
    main()
