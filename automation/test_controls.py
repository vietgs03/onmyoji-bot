#!/usr/bin/env python3
"""
test_controls.py - EVAL THAT KY nhan dien nut DIEU KHIEN (back / close-X)
                   tren TOAN BO 105 man, dung GROUND-TRUTH gan bang VISION.

Ground-truth: captures/ground_truth_controls.json {tag:{back:bool, close:bool}}
(gan thu cong bang vision, chinh xac - khong tin nhan world.json tho).

Do cho TUNG loai (back, close):
  precision = trong cac man detector BAO co nut, bao nhieu % la dung (GT=true)
  recall    = trong cac man GT co nut, detector tim duoc bao nhieu %
  F1
Game RAT nhieu man -> can ca 2 cao. Muc tieu >=0.90.

Chay: .venv/bin/python automation/test_controls.py
"""
import os, sys, json, cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from controls import ControlFinder

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(ROOT, "exploration", "world.json")
GT = os.path.join(ROOT, "knowledge", "control_ground_truth.json")


def main(min_score=None, verbose=True):
    cf = ControlFinder()
    gt = json.load(open(GT))
    w = json.load(open(WORLD))
    tag2path = {}
    for s in w["states"].values():
        p = s.get("screenshot", "")
        if p:
            tag2path[os.path.basename(p).replace(".png", "")] = p

    stats = {k: {"tp": 0, "fp": 0, "fn": 0} for k in ("back", "close")}
    errs = []
    for tag, truth in gt.items():
        p = tag2path.get(tag)
        if not p or not os.path.exists(p):
            continue
        img = cv2.imread(p)
        for kind in ("back", "close"):
            hit = cf.find(img, kind=kind, min_score=min_score)
            pred = hit is not None
            real = bool(truth[kind])
            s = stats[kind]
            if pred and real:
                s["tp"] += 1
            elif pred and not real:
                s["fp"] += 1
                errs.append(("FP", kind, tag, hit[:3]))
            elif not pred and real:
                s["fn"] += 1
                errs.append(("FN", kind, tag, None))

    print(f"=== EVAL controls (min_score={min_score}, GT vision, 105 man) ===")
    macro = []
    for kind, s in stats.items():
        tp, fp, fn = s["tp"], s["fp"], s["fn"]
        prec = tp / (tp + fp) if tp + fp else 1.0
        rec = tp / (tp + fn) if tp + fn else 1.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        macro.append(f1)
        print(f"  {kind:6}: P={prec:.3f} R={rec:.3f} F1={f1:.3f}  "
              f"(tp={tp} fp={fp} fn={fn})")
    print(f"  MACRO-F1 = {sum(macro)/len(macro):.3f}")
    if verbose and errs:
        print("\n--- loi (FP=bao nham, FN=bo sot) ---")
        for typ, kind, tag, hit in errs:
            print(f"  [{typ}] {kind:6} {tag} {hit if hit else ''}")
    return sum(macro) / len(macro)


if __name__ == "__main__":
    ms = float(sys.argv[1]) if len(sys.argv) > 1 else None
    main(ms)
