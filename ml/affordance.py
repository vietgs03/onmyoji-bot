#!/usr/bin/env python3
"""
affordance.py - Train + eval AFFORDANCE model (click co tac dung khong?).

Model: GradientBoosting (robust voi feature it, khong can scale, xu ly phi tuyen).
Eval: 5-fold stratified CV (AUC + accuracy + precision/recall). So voi baseline.
Luu model: ml/models/affordance.pkl

Dung:
  python affordance.py train      # train + eval + save
  python affordance.py eval       # chi eval CV
  from affordance import Affordance; a=Affordance.load(); a.score(img,x,y)
"""
import os, sys, pickle
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dataset import build_dataset, featurize

MODELS = os.path.join(ROOT, "ml", "models")
os.makedirs(MODELS, exist_ok=True)
MODEL_PATH = os.path.join(MODELS, "affordance.pkl")


def _make_model():
    from sklearn.ensemble import GradientBoostingClassifier
    return GradientBoostingClassifier(n_estimators=120, max_depth=3,
                                      learning_rate=0.08, subsample=0.9,
                                      random_state=42)


def evaluate():
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.metrics import (roc_auc_score, accuracy_score,
                                 precision_score, recall_score, f1_score)
    X, y, meta = build_dataset()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    model = _make_model()
    proba = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
    pred = (proba >= 0.5).astype(int)
    # baseline: doan theo ti le da so
    base = max(y.mean(), 1 - y.mean())
    print(f"=== Affordance CV (5-fold) tren {len(y)} mau ===")
    print(f"  AUC       : {roc_auc_score(y, proba):.3f}")
    print(f"  accuracy  : {accuracy_score(y, pred):.3f}  (baseline da-so {base:.3f})")
    print(f"  precision : {precision_score(y, pred):.3f}")
    print(f"  recall    : {recall_score(y, pred):.3f}")
    print(f"  f1        : {f1_score(y, pred):.3f}")
    return roc_auc_score(y, proba)


def train():
    X, y, meta = build_dataset()
    model = _make_model()
    model.fit(X, y)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"trained tren {len(y)} mau -> luu {MODEL_PATH}")
    # feature importance top
    imp = model.feature_importances_
    top = np.argsort(imp)[::-1][:8]
    print("  top features (idx:importance):", [(int(i), round(float(imp[i]), 3)) for i in top])


class Affordance:
    def __init__(self, model):
        self.model = model

    @classmethod
    def load(cls):
        with open(MODEL_PATH, "rb") as f:
            return cls(pickle.load(f))

    def score(self, img, x, y):
        """Tra xac suat (0..1) click (x,y) co tac dung. 0.5 neu khong featurize duoc."""
        feat = featurize(img, x, y)
        if feat is None:
            return 0.5
        return float(self.model.predict_proba(feat.reshape(1, -1))[0, 1])

    def rank(self, img, points):
        """Sap xep diem theo affordance giam dan. Tra list (point, score)."""
        scored = [(p, self.score(img, p[0], p[1])) for p in points]
        return sorted(scored, key=lambda t: -t[1])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "train"
    if cmd == "eval":
        evaluate()
    else:
        evaluate()
        train()
