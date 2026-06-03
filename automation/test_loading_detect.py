#!/usr/bin/env python3
"""
test_loading_detect.py - EVAL do chinh xac phat hien LOADING (3 detector hop nhat).

Vi sao quan trong: agent phai biet 'click xong, da load xong man dich chua' truoc
khi doc/click tiep. Neu nham loading thanh ready -> doc watermark -> dieu huong sai.

3 detector (Agent.is_loading_screen + wait_stable):
  1. dark-ratio          -> boot/splash toi.
  2. pHash DB 260 artwork -> loading-tip artwork (shikigami).
  3. it button THAT       -> loading chuyen canh chung (wait_stable dem button).

Day la 2 eval:
  A) is_loading_screen (dark + DB) tren 8 loading + UI  -> bat bao nhieu loading.
  B) full (them dem button) -> ACC tong (nhu phien ban truoc, 0.952).

Chay: .venv/bin/python automation/test_loading_detect.py
Khong can game.
"""
import os, sys, json, cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent import Agent
from screen_reader import ScreenReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(ROOT, "exploration", "world.json")


def main():
    agent = Agent.__new__(Agent)   # khong can Controller
    w = json.load(open(WORLD))
    MIN = 2

    loading, ui = [], []
    for sid, s in w["states"].items():
        lbl, p = s.get("label"), s.get("screenshot")
        if not (lbl and p and os.path.exists(p)):
            continue
        img = cv2.imread(p)
        # detector 1+2 (nhanh, khong OCR)
        is_load12 = agent.is_loading_screen(img)
        # detector 3 (dem button - can OCR)
        r = ScreenReader(img)
        n_btn = sum(1 for t, _, _, c in r.tappables()
                    if c >= 80 and not agent._is_watermark(t))
        rec = (sid, lbl, is_load12, n_btn)
        (loading if lbl == "Loading" else ui).append(rec)

    # --- Eval A: detector 1+2 (dark + DB) bat loading ---
    print("=== A) dark + pHash DB (khong dem button) ===")
    a_hit = sum(1 for _, _, l12, _ in loading if l12)
    a_fp = sum(1 for _, _, l12, _ in ui if l12)
    print(f"  loading bat duoc: {a_hit}/{len(loading)} (artwork DB + dark)")
    print(f"  false-pos tren UI: {a_fp}/{len(ui)}")
    for sid, lbl, l12, _ in loading:
        if l12:
            print(f"     [DB/dark] {sid} loading")

    # --- Eval B: hop nhat (1+2 OR it-button) ---
    print("\n=== B) HOP NHAT 3 detector (final, dung trong wait_stable) ===")
    def is_load_final(l12, n):
        return l12 or n < MIN
    tp = sum(1 for _, _, l12, n in loading if is_load_final(l12, n))
    fp = sum(1 for _, _, l12, n in ui if is_load_final(l12, n))
    tn = len(ui) - fp
    acc = (tp + (len(ui) - fp)) / (len(loading) + len(ui))
    print(f"  LOADING nhan dung: {tp}/{len(loading)}  (0 false-neg = an toan)")
    print(f"  UI nhan dung (ready): {tn}/{len(ui)}")
    print(f"  ACCURACY: {acc:.3f}")
    if fp:
        print(f"  ! {fp} UI bi cho loading (doi them, vo hai neu la Animation/man mo):")
        for sid, lbl, l12, n in ui:
            if is_load_final(l12, n):
                print(f"     {sid} [{lbl}] db/dark={l12} n_btn={n}")
    return acc


if __name__ == "__main__":
    main()
