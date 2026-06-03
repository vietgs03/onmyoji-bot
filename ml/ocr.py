#!/usr/bin/env python3
"""
ocr.py - Doc text tu anh game bang tesseract (da co /usr/bin/tesseract).

Dung de:
  - Doc chu tren nut (Explore/Summon/Challenge...) -> label man chinh xac, khong can vision.
  - Doc so lieu (AP/vang/ve/level) o thanh tren -> bot biet tai nguyen de quyet dinh.
  - Doc ten shikigami/soul -> khop voi KB.

API:
  ocr_text(img, roi=None)         -> chuoi text
  ocr_words(img, roi=None)        -> list (text, (x,y,w,h), conf)
  read_resources(img)             -> dict {coin, ticket, sushi, ...} (best-effort)

Dung: python ocr.py <anh.png> [x0 y0 x1 y1]
"""
import os, sys, re
import numpy as np
import cv2

try:
    import pytesseract
    _HAS = True
except Exception:
    _HAS = False


def _prep(img):
    """Tien xu ly cho OCR: gray + upscale + threshold (chu game thuong sang tren nen toi)."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = cv2.resize(g, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    # thu ca thuong va dao mau, chon ban co nhieu text hon (lam o ham goi)
    return g


def ocr_text(img, roi=None, invert=False):
    if not _HAS or img is None:
        return ""
    crop = img[roi[1]:roi[3], roi[0]:roi[2]] if roi else img
    if crop.size == 0:
        return ""
    g = _prep(crop)
    if invert:
        g = 255 - g
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    txt = pytesseract.image_to_string(th, config="--psm 6")
    return txt.strip()


def ocr_words(img, roi=None, min_conf=40):
    """Tra list (text, (x,y,w,h) trong toa do GOC anh, conf)."""
    if not _HAS or img is None:
        return []
    ox, oy = (roi[0], roi[1]) if roi else (0, 0)
    crop = img[roi[1]:roi[3], roi[0]:roi[2]] if roi else img
    if crop.size == 0:
        return []
    g = _prep(crop)
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
            # toa do trong crop da x2 -> chia 2 + offset
            x = ox + data["left"][i] // 2
            y = oy + data["top"][i] // 2
            w = data["width"][i] // 2
            h = data["height"][i] // 2
            out.append((t, (x, y, w, h), conf))
    return out


def read_resources(img):
    """Best-effort doc so o thanh tai nguyen tren cung (y ~ 55..95).
    Tra dict cac so tim duoc (theo thu tu trai->phai)."""
    words = ocr_words(img, roi=(380, 50, 1130, 100), min_conf=30)
    nums = []
    for t, (x, y, w, h), conf in sorted(words, key=lambda z: z[1][0]):
        # chuan hoa: 14.77M / 393513 / 13.4K
        m = re.fullmatch(r"[\d.,]+[KMkm]?", t)
        if m:
            nums.append(t)
    return {"raw_numbers": nums}


def find_text(img, target, roi=None):
    """Tim cum tu khop 'target' (khong phan biet hoa), tra (x,y) tam neu thay."""
    for t, (x, y, w, h), conf in ocr_words(img, roi):
        if target.lower() in t.lower():
            return (x + w // 2, y + h // 2)
    return None


if __name__ == "__main__":
    if not _HAS:
        print("pytesseract chua cai"); sys.exit(1)
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path or not os.path.exists(path):
        print("usage: python ocr.py <anh.png> [x0 y0 x1 y1]"); sys.exit(1)
    img = cv2.imread(path)
    roi = tuple(map(int, sys.argv[2:6])) if len(sys.argv) >= 6 else None
    print("=== text ===")
    print(ocr_text(img, roi))
    print("=== words (conf>=40) ===")
    for t, box, c in ocr_words(img, roi)[:30]:
        print(f"  {t!r:24} @{box} conf={c:.0f}")
    print("=== resources ===")
    print(read_resources(img))
