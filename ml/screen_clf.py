#!/usr/bin/env python3
"""
screen_clf.py - Phan loai MAN HINH game tu anh (bo tro dhash).

dhash chi khop man da thay (exact-ish). Classifier nay hoc DAC TRUNG TRUC QUAN cua
moi loai man (HOME/Event/Explore/...) -> doan duoc ca bien the/man gan giong chua luu.

Feature toan anh:
  - color histogram HSV theo luoi 3x3 (9 o x 3 kenh x 4 bins = 108)
  - brightness theo luoi 4x4 (16)
  - edge density theo luoi 3x3 (9)
Model: LogisticRegression (nhanh, it overfit voi mau it). Eval: leave-one-out / CV.
Luu: ml/models/screen_clf.pkl (+ label encoder).

Dung:
  python screen_clf.py train
  from screen_clf import ScreenClf; c=ScreenClf.load(); c.predict(img) -> (label, prob)
"""
import os, sys, json, pickle
import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "exploration")
SCREENS = os.path.join(EXP, "screens")
MODELS = os.path.join(ROOT, "ml", "models")
os.makedirs(MODELS, exist_ok=True)
MODEL_PATH = os.path.join(MODELS, "screen_clf.pkl")
W, H = 1152, 679


def feat_image(img):
    """Vector dac trung toan anh (133-dim). None neu anh sai kich thuoc."""
    if img is None or img.shape[0] < H or img.shape[1] < W:
        return None
    img = cv2.resize(img, (W, H))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    feats = []
    # 1) HSV hist luoi 3x3
    gh, gw = H // 3, W // 3
    for r in range(3):
        for c in range(3):
            cell = hsv[r*gh:(r+1)*gh, c*gw:(c+1)*gw]
            for ch in range(3):
                hh = cv2.calcHist([cell], [ch], None, [4], [0, 256]).flatten()
                feats.extend(hh / (hh.sum() + 1e-6))
    # 2) brightness luoi 4x4
    bh, bw = H // 4, W // 4
    for r in range(4):
        for c in range(4):
            feats.append(float(gray[r*bh:(r+1)*bh, c*bw:(c+1)*bw].mean()) / 255.0)
    # 3) edge density luoi 3x3
    for r in range(3):
        for c in range(3):
            feats.append(float(edges[r*gh:(r+1)*gh, c*gw:(c+1)*gw].mean()) / 255.0)
    return np.array(feats, dtype=np.float32)


def _load_labeled():
    world = json.load(open(os.path.join(EXP, "world.json"), encoding="utf-8"))
    X, y = [], []
    for sid, st in world["states"].items():
        lbl = st.get("label")
        if not lbl:
            continue
        img = cv2.imread(os.path.join(SCREENS, f"{sid}.png"))
        f = feat_image(img)
        if f is None:
            continue
        X.append(f)
        y.append(lbl)
    return np.array(X), np.array(y)


def evaluate():
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from collections import Counter
    X, y = _load_labeled()
    cnt = Counter(y)
    # chi giu lop co >=3 mau de CV co nghia
    keep = {k for k, v in cnt.items() if v >= 3}
    mask = np.array([lbl in keep for lbl in y])
    Xk, yk = X[mask], y[mask]
    print(f"=== Screen classifier ===")
    print(f"  tong mau co nhan: {len(y)}, lop: {len(cnt)}")
    print(f"  lop >=3 mau (dung CV): {len(keep)} -> {len(yk)} mau")
    if len(keep) < 2:
        print("  khong du lop de CV")
        return
    n_splits = min(3, min(Counter(yk).values()))
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    clf = LogisticRegression(max_iter=1000, C=1.0)
    scores = cross_val_score(clf, Xk, yk, cv=cv)
    base = max(Counter(yk).values()) / len(yk)
    print(f"  CV accuracy ({n_splits}-fold): {scores.mean():.3f} +- {scores.std():.3f}  (baseline {base:.3f})")


def train():
    from sklearn.linear_model import LogisticRegression
    X, y = _load_labeled()
    clf = LogisticRegression(max_iter=1000, C=1.0)
    clf.fit(X, y)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(clf, f)
    print(f"trained tren {len(y)} mau, {len(set(y))} lop -> {MODEL_PATH}")


class ScreenClf:
    def __init__(self, clf):
        self.clf = clf

    @classmethod
    def load(cls):
        with open(MODEL_PATH, "rb") as f:
            return cls(pickle.load(f))

    def predict(self, img):
        """Tra (label, prob). None neu anh xau."""
        f = feat_image(img)
        if f is None:
            return None, 0.0
        proba = self.clf.predict_proba(f.reshape(1, -1))[0]
        i = int(np.argmax(proba))
        return self.clf.classes_[i], float(proba[i])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "train"
    if cmd == "eval":
        evaluate()
    else:
        evaluate()
        train()
