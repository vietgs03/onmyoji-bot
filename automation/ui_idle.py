#!/usr/bin/env python3
"""ui_idle.py - Nap toa do MAN NGHI (idle) tu data/ui_idle.json.

Nguon: LAYOUT res.npk 46693.json (ban sao 2043.json) - DU LIEU GOC tu game,
KHONG phai doan bang OCR (man nghi OCR tra ve 0 text nen khong the doc bang OCR).

Man nghi = giao dien bi an, chi con:
  - 3 icon goc TRAI TREN: thoat / setting / chat
  - nut nhac + tips goc PHAI DUOI
  - nut auto + tang toc neu dang trong tran

Cong thuc: screen_x = canvas_x ; screen_y = 640 - canvas_y

API:
  IDLE = buttons()          # {ten: (x,y)}
  xy('buttonExit')          # (33,30)
  size('button_auto')       # (100,100)
  labels()                  # {node: {'text':..,'screen':..}}
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "ui_idle.json")
_C = None


def _load():
    global _C
    if _C is None:
        with open(PATH, encoding="utf-8") as f:
            raw = json.load(f)
        _C = raw
    return _C


def buttons():
    """{ten nut: (x,y)} cua man nghi."""
    return {k: tuple(v["screen"]) for k, v in _load().get("buttons", {}).items()}


def xy(name):
    """Toa do (x,y) 1 nut. vd xy('buttonExit') -> (33,30)."""
    b = _load().get("buttons", {}).get(name)
    return tuple(b["screen"]) if b else None


def size(name):
    """Kich thuoc (w,h) 1 nut."""
    b = _load().get("buttons", {}).get(name)
    return tuple(b["size"]) if b else None


def labels():
    """Cac label tren man nghi (text + toa do)."""
    return {k: (v.get("text"), tuple(v["screen"]))
            for k, v in _load().get("labels", {}).items()}


def main():
    d = _load()
    print("=== MAN NGHI - nut (nguon: res.npk layout 46693) ===")
    for k, v in d.get("buttons", {}).items():
        print(f"  {k:20s} screen={tuple(v['screen'])}  {tuple(v['size'])}")
    print("\n=== label ===")
    for k, v in d.get("labels", {}).items():
        print(f"  {k:14s} {v['text']!r:28s} @{tuple(v['screen'])}")


if __name__ == "__main__":
    main()
