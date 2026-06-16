#!/usr/bin/env python3
"""test_recognition_robustness.py - Kiem tra DO BEN nhan dien (tri thuc nguoc).

Y tuong (user): tu cac anh man da hoc, BIEN DOI da dang (sang/toi, mo, cat/xao,
dao, phong to/thu nho...) roi do xem he thong CON nhan dung khong. Tim diem yeu
de biet he thong tin cay toi dau = "huan luyen tri thuc nguoc".

Do 2 lop nhan dien (giong production):
  1. dhash (perception.py) - state hash, so hamming voi ban goc.
  2. page detector (manifest + template, cv2.matchTemplate TM_CCOEFF_NORMED) -
     CHINH la lop landmark robust ma production dung (eye-rs/assets/pages).

Cac phep BIEN DOI:
  - brightness: chinh sang/toi (gamma + offset).
  - blur: lam mo (gaussian) nhieu muc.
  - crop_shift: cat + dich (mo phong man xe dich/pan).
  - flip: dao ngang/doc (PHAI fail - kiem tra he thong KHONG nhan bua).
  - scale: phong to/thu nho.
  - rotate: xoay nhe.
  - noise: them nhieu.
  - occlude: che 1 phan (popup/overlay).

Output: bang ti le nhan dung theo tung phep + nguong chiu duoc. JSON + console.

Chay:
  python3 scripts/test_recognition_robustness.py [--images N] [--json out.json]
"""
import os
import sys
import json
import argparse
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
ASSETS = os.path.join(ROOT, "eye-rs", "assets", "pages")
MANIFEST = os.path.join(ASSETS, "manifest.json")

from perception import dhash, hamming  # noqa: E402

CANON_THR = 12  # nguong hamming coi la "cung man" (khop world_model)
GAME_W, GAME_H = 1136, 640
CANON_W, CANON_H = 1152, 679  # dhash chay o canon (production resize client->canon truoc)


def _dhash_canon(bgr_img):
    """dhash giong production: resize ve canon 1152x679 roi hash (BGR, vi
    perception.dhash tu cvtColor BGR2GRAY ben trong)."""
    canon = cv2.resize(bgr_img, (CANON_W, CANON_H))
    return dhash(canon)


# ---------- PAGE DETECTOR (Python, khop production Rust) ----------
class PageDetector:
    """Load manifest + template (cv2 BGR, cung he mau voi file da luu). Detect =
    matchTemplate TM_CCOEFF_NORMED trong ROI -> page co score >= threshold cao nhat."""

    def __init__(self):
        m = json.load(open(MANIFEST, encoding="utf-8"))
        self.pages = []
        for p in m["pages"]:
            tmpl = cv2.imread(os.path.join(ASSETS, p["file"]))
            if tmpl is None:
                continue
            self.pages.append((p["page"], p["roi"], float(p["threshold"]), tmpl))

    def detect(self, img):
        """img: BGR 1136x640. Tra (page, score) tot nhat vuot threshold, hoac (None, best)."""
        best_page, best_score, over = None, -2.0, None
        H, W = img.shape[:2]
        for page, (x, y, w, h), thr, tmpl in self.pages:
            # clamp ROI
            x2, y2 = min(x + w, W), min(y + h, H)
            x1, y1 = max(0, x), max(0, y)
            if x2 - x1 < tmpl.shape[1] or y2 - y1 < tmpl.shape[0]:
                continue
            roi = img[y1:y2, x1:x2]
            res = cv2.matchTemplate(roi, tmpl, cv2.TM_CCOEFF_NORMED)
            _, mx, _, _ = cv2.minMaxLoc(res)
            if mx > best_score:
                best_score = mx
            if mx >= thr and (over is None or mx > over[1]):
                over = (page, mx)
        if over:
            return over
        return (None, best_score)


# ---------- BIEN DOI ANH ----------
def t_brightness(img, factor):
    """factor <1 toi, >1 sang."""
    return np.clip(img.astype(np.float32) * factor, 0, 255).astype(np.uint8)


def t_blur(img, k):
    k = int(k) | 1  # le
    return cv2.GaussianBlur(img, (k, k), 0)


def t_crop_shift(img, dx, dy):
    """Dich anh dx,dy (mo phong pan) - vung trong fill den."""
    H, W = img.shape[:2]
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, M, (W, H))


def t_flip(img, mode):
    return cv2.flip(img, mode)  # 1 ngang, 0 doc, -1 ca hai


def t_scale(img, s):
    """Phong to/thu nho roi dua ve kich thuoc goc (mo phong zoom)."""
    H, W = img.shape[:2]
    rs = cv2.resize(img, (max(1, int(W * s)), max(1, int(H * s))))
    if s >= 1:  # phong to -> crop giua
        rh, rw = rs.shape[:2]
        y0, x0 = (rh - H) // 2, (rw - W) // 2
        return rs[y0:y0 + H, x0:x0 + W]
    # thu nho -> pad den giua
    out = np.zeros_like(img)
    rh, rw = rs.shape[:2]
    y0, x0 = (H - rh) // 2, (W - rw) // 2
    out[y0:y0 + rh, x0:x0 + rw] = rs
    return out


def t_rotate(img, deg):
    H, W = img.shape[:2]
    M = cv2.getRotationMatrix2D((W / 2, H / 2), deg, 1.0)
    return cv2.warpAffine(img, M, (W, H))


def t_noise(img, sigma):
    n = np.random.normal(0, sigma, img.shape).astype(np.float32)
    return np.clip(img.astype(np.float32) + n, 0, 255).astype(np.uint8)


def t_occlude(img, frac):
    """Che 1 hinh chu nhat ngau nhien (mo phong popup) phu frac dien tich."""
    out = img.copy()
    H, W = img.shape[:2]
    bw, bh = int(W * frac ** 0.5), int(H * frac ** 0.5)
    x0 = np.random.randint(0, max(1, W - bw))
    y0 = np.random.randint(0, max(1, H - bh))
    out[y0:y0 + bh, x0:x0 + bw] = 0
    return out


def t_shuffle(img, grid):
    """CAT anh thanh luoi grid x grid roi XAO TRON vi tri cac o (sap xep lung tung).
    Kiem tra MINH BACH: noi dung giu nguyen nhung BO CUC pha vo -> he thong KHONG
    duoc nhan dung (neu nhan = chi nhin mau tong the, khong hieu bo cuc)."""
    H, W = img.shape[:2]
    gh, gw = H // grid, W // grid
    cells = []
    for r in range(grid):
        for c in range(grid):
            cells.append(img[r * gh:(r + 1) * gh, c * gw:(c + 1) * gw].copy())
    idx = list(range(len(cells)))
    rng = np.random.default_rng(42)
    rng.shuffle(idx)
    out = img.copy()
    for i, r in enumerate(range(grid)):
        for c in range(grid):
            k = idx[r * grid + c]
            cell = cells[k]
            out[r * gh:r * gh + cell.shape[0], c * gw:c * gw + cell.shape[1]] = cell
    return out


# Danh sach phep bien doi: (ten, ham, list tham so, "EXPECT" co nen nhan dung khong)
# EXPECT=True: bien doi nhe, NEN van nhan dung. EXPECT=False: bien doi pha huy
# (flip/scale lon) -> NEN fail (kiem tra he thong khong nhan bua = minh bach).
TRANSFORMS = [
    ("brightness_dim", t_brightness, [0.5, 0.7, 0.85], True),
    ("brightness_bright", t_brightness, [1.2, 1.5, 1.8], True),
    ("blur", t_blur, [3, 7, 15], True),
    ("shift", t_crop_shift, [(10, 0), (30, 20), (60, 40)], True),
    ("noise", t_noise, [10, 25, 45], True),
    ("scale_up", t_scale, [1.05, 1.15, 1.3], True),
    ("scale_down", t_scale, [0.9, 0.75, 0.6], True),
    ("rotate", t_rotate, [2, 5, 10], True),
    ("occlude", t_occlude, [0.1, 0.25, 0.4], None),  # None = tuy muc
    ("shuffle", t_shuffle, [2, 4, 8], False),  # xao o -> PHAI fail (bo cuc vo)
    ("flip_h", t_flip, [1], False),   # dao ngang -> PHAI fail
    ("flip_v", t_flip, [0], False),   # dao doc -> PHAI fail
]


def run(images, out_json):
    det = PageDetector()
    # chon anh: cac frame live da chup trong session (man THAT, co page anchor)
    candidates = []
    for name in ["town_live", "town_test2", "tt1", "tt2", "exp_now", "town_raw"]:
        p = f"/tmp/{name}.png"
        if os.path.exists(p):
            candidates.append(p)
    # bo sung tu screenshots da luu (canon 1152x679 -> resize ve game)
    if len(candidates) < images:
        sc = sorted(__import__("glob").glob(os.path.join(ROOT, "exploration/screens/*.png")))
        candidates += sc[: images - len(candidates)]
    candidates = candidates[:images]

    print(f"=== TEST DO BEN NHAN DIEN tren {len(candidates)} anh ===\n")
    # baseline: page goc cua moi anh
    base = {}
    for p in candidates:
        img = cv2.imread(p)
        if img is None:
            continue
        if img.shape[:2] != (GAME_H, GAME_W):
            img = cv2.resize(img, (GAME_W, GAME_H))
        page, score = det.detect(img)
        base[p] = {"img": img, "page": page, "dhash": _dhash_canon(img)}
    usable = [p for p in base if base[p]["page"]]
    print(f"Anh co page goc (de test): {len(usable)}/{len(base)}")
    for p in usable:
        print(f"  {os.path.basename(p):20} -> {base[p]['page']}")
    print()

    results = {}
    for tname, fn, params, expect in TRANSFORMS:
        page_ok = 0
        page_tot = 0
        dhash_ok = 0
        dhash_tot = 0
        detail = []
        for p in usable:
            b = base[p]
            for prm in params:
                arg = prm if isinstance(prm, tuple) else (prm,)
                tr = fn(b["img"], *arg)
                # page detector
                pg, sc = det.detect(tr)
                same_page = (pg == b["page"])
                page_tot += 1
                page_ok += int(same_page)
                # dhash
                dh = _dhash_canon(tr)
                ham = hamming(dh, b["dhash"]) if dh and b["dhash"] else 999
                same_dh = ham <= CANON_THR
                dhash_tot += 1
                dhash_ok += int(same_dh)
                detail.append({"img": os.path.basename(p), "param": str(prm),
                               "page": pg, "page_ok": same_page,
                               "dhash_ham": ham, "dhash_ok": same_dh})
        pr_page = page_ok / page_tot if page_tot else 0
        pr_dh = dhash_ok / dhash_tot if dhash_tot else 0
        results[tname] = {"expect": expect, "page_rate": pr_page, "dhash_rate": pr_dh,
                          "page_ok": page_ok, "page_tot": page_tot, "detail": detail}
        # danh gia
        if expect is True:
            verdict = "OK" if pr_page >= 0.7 else ("YEU" if pr_page >= 0.4 else "KEM")
        elif expect is False:
            verdict = "OK(reject)" if pr_page <= 0.1 else "LO (nhan bua!)"
        else:
            verdict = "-"
        print(f"{tname:18} | page nhan dung: {pr_page*100:5.1f}% | dhash giu: {pr_dh*100:5.1f}% "
              f"| expect={expect} -> {verdict}")

    if out_json:
        json.dump({k: {kk: vv for kk, vv in v.items() if kk != "detail"}
                   for k, v in results.items()},
                  open(out_json, "w"), indent=2)
        print(f"\nda ghi summary -> {out_json}")
    # ket luan minh bach
    print("\n=== KET LUAN (tri thuc nguoc) ===")
    weak = [t for t, r in results.items() if r["expect"] is True and r["page_rate"] < 0.7]
    leak = [t for t, r in results.items() if r["expect"] is False and r["page_rate"] > 0.1]
    print("Phep lam YEU nhan dien (geometric - can canh giac):", weak or "khong")
    print("Phep le ra fail nhung NHAN BUA (lo minh bach):", leak or "khong")

    # PASS/FAIL theo tieu chi: photometric BEN (>=0.7) + minh bach (flip/shuffle reject)
    must_robust = {"brightness_dim", "brightness_bright", "blur", "noise"}
    must_reject = {"flip_h", "flip_v", "shuffle"}
    fails = []
    for t in must_robust:
        if t in results and results[t]["page_rate"] < 0.7:
            fails.append(f"{t} yeu ({results[t]['page_rate']:.2f}<0.7)")
    for t in must_reject:
        if t in results and results[t]["page_rate"] > 0.1:
            fails.append(f"{t} NHAN BUA ({results[t]['page_rate']:.2f}>0.1)")
    if fails:
        print("\n[FAIL]", "; ".join(fails))
    else:
        print("\n[PASS] he thong BEN voi photometric + MINH BACH (tu choi flip/shuffle).")
    return results, (len(fails) == 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", type=int, default=6)
    ap.add_argument("--json", default="/tmp/robustness_report.json")
    a = ap.parse_args()
    _results, ok = run(a.images, a.json)
    sys.exit(0 if ok else 1)
