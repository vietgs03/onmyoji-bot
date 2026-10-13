#!/usr/bin/env python3
"""ui_home.py - Nap toa do man HOME + menu ngang tu data/ui_home.json.

Du lieu lay bang OCR man THAT (2026-10-13), da verify. Man HOME KHONG nam trong
res.npk nen khong the lay tu layout - phai dung OCR nhu file nay.

API:
  HOME, BOTTOM = load()            # dict ten -> (x,y)
  xy('home','explore')             # (495,191)
  is_danger('home','summon')       # True -> KHONG duoc bam
  safe_targets()                   # cac nut KHONG nguy hiem

Dung cho bot + ML: moi nut co toa do + nhan chuc nang + co danger hay khong.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "ui_home.json")

_CACHE = None


def load(path=None):
    """Nap du lieu UI HOME. Tra (home, bottom_bar) - moi cai la dict ten -> (x,y)."""
    global _CACHE
    if _CACHE is None or path:
        with open(path or PATH, encoding="utf-8") as f:
            raw = json.load(f)
        home = {k: tuple(v["screen"]) for k, v in raw.get("home", {}).items()}
        bottom = {k: tuple(v["screen"]) for k, v in raw.get("bottom_bar", {}).items()
                  if not k.startswith("_")}
        danger = set(raw.get("rules", {}).get("never_click", []))
        labels = {k: v.get("action") or v.get("label") or ""
                  for k, v in {**raw.get("home", {}), **raw.get("bottom_bar", {})}.items()
                  if isinstance(v, dict)}
        _CACHE = (home, bottom, danger, labels)
    return _CACHE[0], _CACHE[1]


def _D():
    if _CACHE is None:
        load()
    return _CACHE[2], _CACHE[3]


def xy(area, name):
    """Toa do (x,y) cua nut. area='home' hoac 'bottom'."""
    home, bottom = (load() if _CACHE is None else (_CACHE[0], _CACHE[1]))
    d = home if area == "home" else bottom
    return d.get(name)


def is_danger(area, name):
    """True neu nut nay KHONG duoc bam (vd Summon - ton tai nguyen)."""
    danger, _ = _D()
    return name in danger


def label(area, name):
    """Nhan chuc nang cua nut (tieng Anh/ghi chu)."""
    _, labels = _D()
    return labels.get(name, "")


def safe_targets(area="home"):
    """Danh sach nut AN TOAN (bo cac nut nguy hiem) - de bot tu chon."""
    danger, _ = _D()
    home, bottom = (_CACHE[0], _CACHE[1]) if _CACHE else load()
    d = home if area == "home" else bottom
    return {k: v for k, v in d.items() if k not in danger}


def main():
    home, bottom = load()
    print("=== HOME (bo qua nut nguy hiem) ===")
    for k, v in home.items():
        tag = "  [KHONG BAM]" if is_danger("home", k) else ""
        print(f"  {k:14s} {v}{tag}  {label('home', k)[:50]}")
    print("\n=== MENU NGANG DAY MAN ===")
    for k, v in bottom.items():
        if k.startswith("_"):
            continue
        print(f"  {k:12s} {v}  {label('bottom', k)}")
    print(f"\nNut an toan tren HOME: {sorted(safe_targets('home'))}")


if __name__ == "__main__":
    main()
