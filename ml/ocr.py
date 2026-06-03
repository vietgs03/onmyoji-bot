#!/usr/bin/env python3
"""
ocr.py - Doc text tu anh game.

Engine chinh: PaddleOCR (ppocr-onnx) - chay CPU, doc tot ca EN + so tren font game
cach dieu (da test tren client Global/EN: 'Friend','ATK','60/60','3256+3126' score>0.9).
Fallback: tesseract neu ppocr khong co.

Dung de:
  - Doc chu tren nut (Explore/Summon/Challenge...) -> label man chinh xac, khong can vision.
  - Doc so lieu (AP/vang/ve/level) o thanh tren -> bot biet tai nguyen de quyet dinh.
  - Doc ten shikigami/soul -> khop voi KB.

API (giu nguyen, tuong thich code cu):
  ocr_text(img, roi=None)         -> chuoi text (noi cac dong)
  ocr_words(img, roi=None)        -> list (text, (x,y,w,h), conf 0..100)
  read_resources(img)             -> dict {raw_numbers: [...]}
  find_text(img, target, roi)     -> (cx,cy) tam cum tu khop, hoac None

Dung: python ocr.py <anh.png> [x0 y0 x1 y1]
"""
import os, sys, re
import numpy as np
import cv2

# ---- engine PaddleOCR (uu tien) ----
_TS = None
_HAS_PP = False
try:
    from ppocronnx.predict_system import TextSystem
    _HAS_PP = True
except Exception:
    _HAS_PP = False

# ---- fallback tesseract ----
try:
    import pytesseract
    _HAS_TES = True
except Exception:
    _HAS_TES = False


def _ts():
    """Lazy-load TextSystem (load model ~0.4s, 1 lan)."""
    global _TS
    if _TS is None:
        _TS = TextSystem(box_thresh=0.5, unclip_ratio=1.6)
    return _TS


def _crop(img, roi):
    if roi is None:
        return img, 0, 0
    x0, y0, x1, y1 = roi
    return img[y0:y1, x0:x1], x0, y0


def ocr_words(img, roi=None, min_conf=40):
    """Tra list (text, (x,y,w,h) trong toa do GOC anh, conf 0..100)."""
    if img is None:
        return []
    crop, ox, oy = _crop(img, roi)
    if crop is None or crop.size == 0:
        return []
    if _HAS_PP:
        try:
            res = _ts().detect_and_ocr(crop)
        except Exception:
            res = []
        out = []
        for r in res:
            conf = float(getattr(r, "score", 0)) * 100.0
            if conf < min_conf:
                continue
            box = np.array(r.box)  # 4x2
            x = int(box[:, 0].min()) + ox
            y = int(box[:, 1].min()) + oy
            w = int(box[:, 0].max() - box[:, 0].min())
            h = int(box[:, 1].max() - box[:, 1].min())
            out.append((r.ocr_text.strip(), (x, y, w, h), conf))
        return out
    # fallback tesseract
    if _HAS_TES:
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        g = cv2.resize(g, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        data = pytesseract.image_to_data(g, config="--psm 11",
                                         output_type=pytesseract.Output.DICT)
        out = []
        for i, t in enumerate(data["text"]):
            t = t.strip()
            try:
                conf = float(data["conf"][i])
            except Exception:
                conf = -1
            if t and conf >= min_conf:
                x = ox + data["left"][i] // 2
                y = oy + data["top"][i] // 2
                w = data["width"][i] // 2
                h = data["height"][i] // 2
                out.append((t, (x, y, w, h), conf))
        return out
    return []


def ocr_text(img, roi=None, **_):
    """Noi tat ca dong text doc duoc (top->bottom, left->right)."""
    words = ocr_words(img, roi, min_conf=30)
    words.sort(key=lambda z: (z[1][1] // 12, z[1][0]))  # gom theo hang
    return " ".join(w[0] for w in words).strip()


def read_resources(img):
    """Best-effort doc so o thanh tai nguyen tren cung (y ~ 50..100).
    Tra dict cac so tim duoc (theo thu tu trai->phai)."""
    words = ocr_words(img, roi=(380, 50, 1130, 105), min_conf=30)
    nums = []
    for t, (x, y, w, h), conf in sorted(words, key=lambda z: z[1][0]):
        m = re.fullmatch(r"[\d][\d.,]*[KMkm]?", t)
        if m:
            nums.append(t)
    return {"raw_numbers": nums}


def find_text(img, target, roi=None):
    """Tim cum tu khop 'target' (khong phan biet hoa), tra (cx,cy) tam neu thay."""
    for t, (x, y, w, h), conf in ocr_words(img, roi, min_conf=40):
        if target.lower() in t.lower():
            return (x + w // 2, y + h // 2)
    return None


def engine():
    return "paddleocr" if _HAS_PP else ("tesseract" if _HAS_TES else "none")


if __name__ == "__main__":
    print(f"[engine: {engine()}]")
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path or not os.path.exists(path):
        print("usage: python ocr.py <anh.png> [x0 y0 x1 y1]"); sys.exit(1)
    img = cv2.imread(path)
    roi = tuple(map(int, sys.argv[2:6])) if len(sys.argv) >= 6 else None
    print("=== words (conf>=40) ===")
    for t, box, c in ocr_words(img, roi)[:40]:
        print(f"  {t!r:30} @{box} conf={c:.0f}")
    print("=== text ===")
    print(ocr_text(img, roi)[:300])
    print("=== resources ===")
    print(read_resources(img))
