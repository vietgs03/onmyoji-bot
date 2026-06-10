"""state_matrix.py - Bieu dien man hinh bang MA TRAN DAC TRUNG DA CHIEU (PHAN B).

Thay the bieu dien 1-chieu (bag-of-token / dhash toan man) bang ma tran
nhieu CHIEU doc lap, moi chieu bat 1 khia canh cua man hinh:

  1. SEMANTIC  : tap nhan UI on dinh (ui_tokens - loc OCR jitter/dong ho/chat).
  2. SPATIAL   : luoi GRID_COLS x GRID_ROWS cell; moi cell giu tap token OCR
                 roi vao cell do -> phan biet 2 man co CUNG token nhung BO TRI khac.
  3. STRUCTURAL: dhash TUNG CELL (8 byte/cell) -> so khop layout theo vung,
                 chong nhieu animation cuc bo (1 cell dong khong pha ca man).

So khop 2 man = trung binh co trong so cac chieu (xem similarity()).
Nguong quyet dinh cung-man: SAME_THRESH (tune bang validate tren anh that).

CLI:
  .venv/bin/python automation/state_matrix.py extract <img.png>   # in feature
  .venv/bin/python automation/state_matrix.py validate            # do confusion
                                                                  # tren logs/explore_shots
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "automation"), os.path.join(ROOT, "ml"),
          os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from state_solver import ui_tokens  # noqa: E402  loc token on dinh (da validate)

GRID_COLS = 6
GRID_ROWS = 4
SAME_THRESH = 0.72          # validate 91 anh that: AUC .9997, FP 0/4057 @0.715
CELL_HAM_MATCH = 12         # hamming <= nguong (tren 64 bit) -> cell khop layout

# Trong so cac chieu khi tron similarity (tong = 1)
W_SEMANTIC = 0.45
W_SPATIAL = 0.30
W_STRUCT = 0.25


def _cell_dhash(cell: np.ndarray) -> int:
    """dhash 64-bit cua 1 cell (gray 9x8 -> so sanh ngang)."""
    g = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY) if cell.ndim == 3 else cell
    small = cv2.resize(g, (9, 8), interpolation=cv2.INTER_AREA)
    bits = small[:, 1:] > small[:, :-1]
    return int("".join("1" if b else "0" for b in bits.flatten()), 2)


def _ham64(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


@dataclass
class FeatureMatrix:
    """Ma tran dac trung 1 man hinh. JSON-serializable (luu vao graph memory)."""
    sem: set                                   # chieu semantic: ui_tokens toan man
    grid_tokens: list = field(default_factory=list)   # [ROWS][COLS] -> list token
    grid_dhash: list = field(default_factory=list)    # [ROWS][COLS] -> int 64-bit

    def to_json(self) -> dict:
        return {
            "sem": sorted(self.sem),
            "grid_tokens": [[sorted(c) for c in row] for row in self.grid_tokens],
            "grid_dhash": [[format(h, "016x") for h in row] for row in self.grid_dhash],
        }

    @classmethod
    def from_json(cls, d: dict) -> "FeatureMatrix":
        return cls(
            sem=set(d["sem"]),
            grid_tokens=[[set(c) for c in row] for row in d["grid_tokens"]],
            grid_dhash=[[int(h, 16) for h in row] for row in d["grid_dhash"]],
        )


def extract(img: np.ndarray, words: list | None = None) -> FeatureMatrix:
    """Trich feature matrix tu anh (+ ket qua OCR neu da co, tranh OCR lai).

    words: list (text, (x,y,w,h), conf) tu ml.ocr.ocr_words. None -> tu OCR.
    """
    if words is None:
        from ocr import ocr_words
        words = ocr_words(img, min_conf=40)

    h, w = img.shape[:2]
    cw, ch = w / GRID_COLS, h / GRID_ROWS

    sem = ui_tokens(words)

    # SPATIAL: token nao roi vao cell nao (theo tam box). Chi giu token da qua
    # bo loc ui_tokens (token nhieu/dong ho khong duoc vao luoi).
    grid_tokens = [[set() for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
    for t, (x, y, bw, bh), c in words:
        s = str(t).strip().lower()
        if s not in sem:
            continue
        col = min(GRID_COLS - 1, int((x + bw / 2) / cw))
        row = min(GRID_ROWS - 1, int((y + bh / 2) / ch))
        grid_tokens[row][col].add(s)

    # STRUCTURAL: dhash tung cell
    grid_dhash = []
    for r in range(GRID_ROWS):
        row_h = []
        for cidx in range(GRID_COLS):
            y0, y1 = int(r * ch), int((r + 1) * ch)
            x0, x1 = int(cidx * cw), int((cidx + 1) * cw)
            row_h.append(_cell_dhash(img[y0:y1, x0:x1]))
        grid_dhash.append(row_h)

    return FeatureMatrix(sem=sem, grid_tokens=grid_tokens, grid_dhash=grid_dhash)


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    u = a | b
    return len(a & b) / len(u) if u else 1.0


def similarity(f1: FeatureMatrix, f2: FeatureMatrix) -> dict:
    """So khop 2 ma tran. Tra dict diem tung chieu + diem tron 'combined'.

    TRONG SO THICH NGHI (rut tu validate tren 91 anh that):
    - 2 man deu KHONG co token (loading/man toi): sem/spatial vo nghia
      (Jaccard rong-rong = 1.0 AO) -> don het trong so sang struct.
    - It token (OCR jitter de lam sem lech du man giong het): giam dan
      trong so sem/spatial theo so token thuc te, struct gánh phan con lai.
    """
    # 1. semantic
    n_tok = len(f1.sem) + len(f2.sem)
    sem = _jaccard(f1.sem, f2.sem)

    # 2. spatial: Jaccard tung cell, chi tinh cell co token o it nhat 1 ben.
    cell_scores = []
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            a, b = f1.grid_tokens[r][c], f2.grid_tokens[r][c]
            if a or b:
                cell_scores.append(_jaccard(a, b))
    spatial = float(np.mean(cell_scores)) if cell_scores else sem

    # 3. structural: ti le cell khop layout (hamming nho). Cell dong (animation)
    #    se lech vai cell nhung KHONG keo sap toan bo diem.
    match_cells = 0
    total = GRID_ROWS * GRID_COLS
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            if _ham64(f1.grid_dhash[r][c], f2.grid_dhash[r][c]) <= CELL_HAM_MATCH:
                match_cells += 1
    struct = match_cells / total

    # Do tin cay cua bang chung text: 0 token -> 0; >=8 token (2 man cong lai)
    # -> tin het muc. Tuyen tinh o giua.
    text_conf = min(1.0, n_tok / 8.0)
    w_sem = W_SEMANTIC * text_conf
    w_spa = W_SPATIAL * text_conf
    w_str = 1.0 - w_sem - w_spa          # struct nhan phan trong so con lai

    combined = w_sem * sem + w_spa * spatial + w_str * struct
    return {"sem": sem, "spatial": spatial, "struct": struct,
            "text_conf": text_conf, "combined": combined}


def same_screen(f1: FeatureMatrix, f2: FeatureMatrix,
                thresh: float = SAME_THRESH) -> bool:
    return similarity(f1, f2)["combined"] >= thresh


# ----------------------------------------------------------------------------
# VALIDATE: do confusion tren anh that (logs/explore_shots).
# Cung state-id (tu explorer cu) = positive pair; khac state-id = negative.
# ----------------------------------------------------------------------------

_FEAT_CACHE = os.path.join(ROOT, "knowledge", "_feat_cache.json")


def _load_feats(img_paths: list, verbose=True) -> dict:
    """Trich (co cache disk - OCR cham ~3s/anh) feature cho danh sach anh."""
    cache = {}
    if os.path.exists(_FEAT_CACHE):
        with open(_FEAT_CACHE) as fh:
            cache = json.load(fh)
    feats, dirty = {}, False
    for i, p in enumerate(img_paths):
        key = os.path.basename(p)
        if key in cache:
            feats[p] = FeatureMatrix.from_json(cache[key])
            continue
        img = cv2.imread(p)
        if img is None:
            continue
        if verbose:
            print(f"  OCR {i + 1}/{len(img_paths)}: {key}", file=sys.stderr)
        fm = extract(img)
        feats[p] = fm
        cache[key] = fm.to_json()
        dirty = True
    if dirty:
        with open(_FEAT_CACHE, "w") as fh:
            json.dump(cache, fh)
    return feats


def validate():
    """Do tach bach cung-man vs khac-man tren logs/explore_shots.

    GROUND TRUTH = pixel-diff (mean abs < 12 -> cung man). KHONG dung state-id
    cua explorer cu lam nhan: validate dau tien phat hien explorer cu TACH NHAM
    it nhat 5 cap (cung man pixel-diff < 7 nhung 2 state-id khac nhau do OCR
    jitter) -> nhan do ban. Pixel-diff la nhan khach quan voi anh tinh.
    """
    shot_dir = os.path.join(ROOT, "logs", "explore_shots")
    files = sorted(f for f in os.listdir(shot_dir) if f.endswith(".png"))
    paths = [os.path.join(shot_dir, f) for f in files]
    feats = _load_feats(paths)
    paths = [p for p in paths if p in feats]
    imgs = {p: cv2.imread(p) for p in paths}

    pos, neg = [], []
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            a, b = paths[i], paths[j]
            d = np.abs(imgs[a].astype(np.int16) - imgs[b].astype(np.int16)).mean()
            sim = similarity(feats[a], feats[b])["combined"]
            (pos if d < 12 else neg).append(
                (sim, d, os.path.basename(a), os.path.basename(b)))

    pv = [s for s, _, _, _ in pos]
    nv = [s for s, _, _, _ in neg]
    print("== KET QUA CONFUSION (combined similarity, GT=pixel-diff) ==")
    print(f"POS n={len(pv)} mean={np.mean(pv):.3f} min={np.min(pv):.3f}")
    print(f"NEG n={len(nv)} mean={np.mean(nv):.3f} max={np.max(nv):.3f} "
          f"p99={np.percentile(nv, 99):.3f}")
    nv_s = np.array(sorted(nv))
    auc = sum(np.searchsorted(nv_s, p) for p in pv) / (len(pv) * len(nv))
    print(f"AUC: {auc:.4f}")
    tp = sum(1 for v in pv if v >= SAME_THRESH)
    fp = sum(1 for v in nv if v >= SAME_THRESH)
    print(f"@thresh={SAME_THRESH}: TPR={tp}/{len(pv)} FPR={fp}/{len(nv)}")
    best_t, best_acc = 0.5, 0.0
    for t in np.arange(0.30, 0.98, 0.005):
        acc = (sum(1 for v in pv if v >= t)
               + sum(1 for v in nv if v < t)) / (len(pv) + len(nv))
        if acc > best_acc:
            best_acc, best_t = acc, t
    print(f"Nguong tot nhat: {best_t:.3f} (acc={best_acc:.4f})")
    print("POS kho nhat (cung man nhung sim thap):")
    for s, d, a, b in sorted(pos)[:5]:
        print(f"  sim={s:.3f} pxdiff={d:.1f} {a} ~ {b}")
    print("NEG de nham nhat (khac man nhung sim cao):")
    for s, d, a, b in sorted(neg, reverse=True)[:5]:
        print(f"  sim={s:.3f} pxdiff={d:.1f} {a} ~ {b}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "validate":
        validate()
    elif sys.argv[1] == "extract":
        img = cv2.imread(sys.argv[2])
        fm = extract(img)
        print(json.dumps(fm.to_json(), indent=1)[:2000])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
