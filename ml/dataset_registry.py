#!/usr/bin/env python3
"""
dataset_registry.py - Dang ky tap trung MOI nguon data + danh gia chat luong dataset.

Muc dich: 1 cho nhin thay tat ca data dung de train, chung phuc vu model nao,
chat luong ra sao (so luong, can bang lop, thieu gi) -> biet can thu them gi.

Chay:
  python ml/dataset_registry.py            # bao cao day du
  python ml/dataset_registry.py gaps       # chi in cho thieu (de thu them toi nay)
"""
import os, json, sys, glob
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _exists(p):
    return os.path.exists(os.path.join(ROOT, p))


# ===== DANG KY NGUON DATA =====
# moi entry: ten, file/thumuc, dung cho model nao, loai, cach lay
SOURCES = [
    {"name": "screenshots", "path": "exploration/screens", "for": ["affordance", "screen_clf", "screen_ocr"],
     "kind": "image", "desc": "screenshot EN that (ground truth)", "regen": "explorer.py khi game bat"},
    {"name": "observations", "path": "exploration/observations.jsonl", "for": ["affordance"],
     "kind": "jsonl", "desc": "click->transition/noop", "regen": "explorer.py"},
    {"name": "labels", "path": "exploration/world.json", "for": ["screen_clf", "screen_ocr"],
     "kind": "json", "desc": "nhan man hinh per state", "regen": "label_states.py"},
    {"name": "ui_layouts", "path": "knowledge/ui_layouts.json", "for": ["agent (button coords)"],
     "kind": "json", "desc": "1205 panel/25k button toa do", "regen": "rebuild_assets.py ui"},
    {"name": "fandom_kb", "path": "data/fandom", "for": ["KB vector search"],
     "kind": "json", "desc": "269 shiki/913 skill/69 soul/26 mode", "regen": "crawl_*.py"},
    {"name": "oas_features", "path": "knowledge/oas_features.json", "for": ["KB"],
     "kind": "json", "desc": "52 game feature", "regen": "rebuild_assets.py oas"},
    {"name": "fandom_portraits", "path": "data/fandom_images", "for": ["shikigami recog (tuong lai)"],
     "kind": "image", "desc": "265 portrait EN", "regen": "rebuild_assets.py fandom"},
    {"name": "game_loading_en", "path": "data/game_assets/en_loading", "for": ["augment / loading recog"],
     "kind": "image", "desc": "260 loading art EN", "regen": "rebuild_assets.py assets_en"},
    {"name": "ui_sprites", "path": "data/game_assets/res_npk/png", "for": ["template match (tuong lai)"],
     "kind": "image", "desc": "370 UI sprite", "regen": "rebuild_assets.py sprites"},
]

MIN_PER_CLASS = 5  # nguong toi thieu mau / lop de train tin cay


def label_dist():
    w = json.load(open(os.path.join(ROOT, "exploration/world.json"), encoding="utf-8"))
    c = Counter()
    for st in w["states"].values():
        if st.get("label"):
            c[st["label"]] += 1
    return c


def obs_dist():
    p = os.path.join(ROOT, "exploration/observations.jsonl")
    c = Counter()
    for line in open(p, encoding="utf-8"):
        try:
            c[json.loads(line).get("event")] += 1
        except Exception:
            pass
    return c


def report():
    print("=" * 64)
    print("NGUON DATA")
    print("=" * 64)
    for s in SOURCES:
        ok = "OK " if _exists(s["path"]) else "MISS"
        n = ""
        full = os.path.join(ROOT, s["path"])
        if os.path.isdir(full):
            n = f"{len(os.listdir(full))} items"
        elif s["path"].endswith(".jsonl") and _exists(s["path"]):
            n = f"{sum(1 for _ in open(full))} dong"
        print(f"  [{ok}] {s['name']:18s} {n:14s} -> {', '.join(s['for'])}")
        print(f"        {s['desc']}  (regen: {s['regen']})")

    print("\n" + "=" * 64)
    print("CHAT LUONG: phan bo nhan man hinh (screen_clf/screen_ocr)")
    print("=" * 64)
    d = label_dist()
    print(f"  tong: {sum(d.values())} mau / {len(d)} lop\n")
    for lbl, n in d.most_common():
        bar = "#" * n
        flag = "  <-- THIEU" if n < MIN_PER_CLASS else ""
        print(f"  {lbl:22s} {n:3d} {bar}{flag}")

    print("\n" + "=" * 64)
    print("CHAT LUONG: affordance (click samples)")
    print("=" * 64)
    o = obs_dist()
    pos, neg = o.get("transition", 0), o.get("noop", 0)
    print(f"  transition(+): {pos}   noop(-): {neg}   ty le +: {pos/(pos+neg+1e-6):.2f}")


def gaps():
    d = label_dist()
    weak = [(l, n) for l, n in d.items() if n < MIN_PER_CLASS]
    print(f"Lop < {MIN_PER_CLASS} mau (can thu them toi nay): {len(weak)}")
    for l, n in sorted(weak, key=lambda x: x[1]):
        print(f"  {l:22s} {n} -> can +{MIN_PER_CLASS - n}")
    print("\nGoi y: chay explorer den cac man nay, hoac chup thu cong khi game bat.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "gaps":
        gaps()
    else:
        report()
