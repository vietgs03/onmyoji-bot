#!/usr/bin/env python3
"""
test_loading_detect.py - EVAL do chinh xac phan biet LOADING vs UI-ready.

Vi sao quan trong: agent phai biet 'click xong, da load xong man dich chua' truoc
khi doc/click tiep. Neu nham loading thanh ready -> doc watermark -> dieu huong sai.

Phuong phap: dem button THAT (sau khi loai watermark/tip loading). Loading screen
co ~0 button, man UI co >=10. Nguong wait_stable min_buttons=2 phan tach 2 nhom.

Chay: .venv/bin/python automation/test_loading_detect.py
Khong can game (dung anh da chup trong exploration/screens).
"""
import os, sys, json, cv2, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent import Agent
from screen_reader import ScreenReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(ROOT, "exploration", "world.json")


def n_real_buttons(img, agent):
    """So button THAT = conf>=80, khong phai watermark/tip loading."""
    r = ScreenReader(img)
    return sum(1 for t, _, _, c in r.tappables()
               if c >= 80 and not agent._is_watermark(t))


def main():
    # khong khoi tao Controller (khong can game), chi muon method _is_watermark
    agent = Agent.__new__(Agent)
    w = json.load(open(WORLD))
    MIN = 2  # nguong wait_stable

    loading, ui = [], []
    for sid, s in w["states"].items():
        lbl = s.get("label")
        p = s.get("screenshot")
        if not (lbl and p and os.path.exists(p)):
            continue
        img = cv2.imread(p)
        n = n_real_buttons(img, agent)
        (loading if lbl == "Loading" else ui).append((sid, lbl, n))

    # loading nen < MIN (du dieu kien 'van dang loading'), ui nen >= MIN ('ready')
    tp = sum(1 for _, _, n in loading if n < MIN)      # loading -> doan loading
    tn = sum(1 for _, _, n in ui if n >= MIN)          # ui      -> doan ready
    fn = len(loading) - tp                              # loading bi doan ready (NGUY HIEM)
    fp = len(ui) - tn                                   # ui bi doan loading (treo)

    print(f"LOADING screens: {len(loading)} | UI screens: {len(ui)}")
    print(f"  loading nhan dung (n<{MIN}):  {tp}/{len(loading)}")
    print(f"  ui nhan dung (n>={MIN}):       {tn}/{len(ui)}")
    acc = (tp + tn) / (len(loading) + len(ui))
    print(f"  ACCURACY: {acc:.3f}")
    if fn:
        print(f"  !! {fn} LOADING bi nham ready (se doc nham watermark):")
        for sid, lbl, n in loading:
            if n >= MIN:
                print(f"     {sid} n={n}")
    if fp:
        print(f"  ! {fp} UI bi nham loading (se cho lau):")
        for sid, lbl, n in ui:
            if n < MIN:
                print(f"     {sid} [{lbl}] n={n}")
    return acc


if __name__ == "__main__":
    main()
