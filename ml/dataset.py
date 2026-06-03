#!/usr/bin/env python3
"""
dataset.py - Featurize observations.jsonl thanh (X, y) cho affordance model.

Bai toan AFFORDANCE: cho (anh man hinh, toa do click) -> du doan click do co
"tac dung" (chuyen man = transition) hay khong (noop). Giup explorer click thong minh:
uu tien diem co xac suat affordance cao, bo qua diem chac chan noop.

Feature cho moi mau (state, click):
  - patch anh 48x48 quanh diem click -> color histogram (HSV, 3x8 bins) + edge density
  - toa do chuan hoa (x/W, y/H) + khoang cach toi 4 goc/giua
  - do "noi bat" cuc bo: saturation/brightness trung binh trong patch vs toan anh

Label y: 1 = transition (co tac dung), 0 = noop.

Dung:
  from dataset import build_dataset
  X, y, meta = build_dataset()
"""
import json, os
import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "exploration")
SCREENS = os.path.join(EXP, "screens")
OBS = os.path.join(EXP, "observations.jsonl")
W, H = 1152, 679
PATCH = 48  # nua canh patch quanh diem click


def _imread(sid):
    p = os.path.join(SCREENS, f"{sid}.png")
    return cv2.imread(p) if os.path.exists(p) else None


def featurize(img, x, y):
    """Tra vector dac trung cho (anh, diem click). None neu khong lay duoc patch."""
    if img is None:
        return None
    h, w = img.shape[:2]
    if w < W or h < H:
        return None
    x0, x1 = max(0, x - PATCH), min(w, x + PATCH)
    y0, y1 = max(0, y - PATCH), min(h, y + PATCH)
    patch = img[y0:y1, x0:x1]
    if patch.size == 0:
        return None
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    # 1) histogram HSV (3 kenh x 8 bins = 24)
    hist = []
    for ch in range(3):
        hh = cv2.calcHist([hsv], [ch], None, [8], [0, 256]).flatten()
        hh = hh / (hh.sum() + 1e-6)
        hist.extend(hh)
    # 2) edge density (so canh / dien tich)
    g = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(g, 80, 160)
    edge_density = float(edges.mean()) / 255.0
    # 3) do noi bat cuc bo: sat/val patch vs toan anh
    full_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat_local = float(hsv[:, :, 1].mean())
    val_local = float(hsv[:, :, 2].mean())
    sat_global = float(full_hsv[:, :, 1].mean()) + 1e-6
    val_global = float(full_hsv[:, :, 2].mean()) + 1e-6
    salience = [sat_local / sat_global, val_local / val_global,
                sat_local / 255.0, val_local / 255.0]
    # 4) toa do chuan hoa + khoang cach hinh hoc
    nx, ny = x / W, y / H
    geom = [nx, ny,
            abs(nx - 0.5), abs(ny - 0.5),          # cach giua
            min(nx, 1 - nx), min(ny, 1 - ny),      # cach ria gan nhat
            float(ny > 0.88), float(nx > 0.85),    # vung footer / cot phai
            float(ny < 0.12)]                       # vung header
    return np.array(hist + [edge_density] + salience + geom, dtype=np.float32)


def build_dataset():
    """Doc observations -> X (N,F), y (N,), meta (list dict). Bo qua mau thieu anh."""
    rows = [json.loads(l) for l in open(OBS, encoding="utf-8")]
    X, y, meta = [], [], []
    cache = {}
    for r in rows:
        ev = r.get("event")
        if ev == "transition":
            sid, click, label = r["from"], r["click"], 1
        elif ev == "noop":
            sid, click, label = r["state"], r["click"], 0
        else:
            continue
        if sid not in cache:
            cache[sid] = _imread(sid)
        feat = featurize(cache[sid], click[0], click[1])
        if feat is None:
            continue
        X.append(feat)
        y.append(label)
        meta.append({"sid": sid, "click": click, "event": ev})
    return np.array(X), np.array(y), meta


if __name__ == "__main__":
    X, y, meta = build_dataset()
    print(f"dataset: X={X.shape} y={y.shape}")
    print(f"  positives (transition): {int(y.sum())}  negatives (noop): {int((y==0).sum())}")
    print(f"  feature dim: {X.shape[1] if len(X) else 0}")
