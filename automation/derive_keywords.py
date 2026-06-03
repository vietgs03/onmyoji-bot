#!/usr/bin/env python3
"""
derive_keywords.py - TU SINH keyword `identify` toi uu tu data that (world.json).

Van de: identify gan tay tu 1 anh dai dien -> hep, truot cac BIEN THE cung label
  (vd Event co 16 anh: nhieu sub-tab/popup). test_world_maze lo ra 56.9% (nhieu None).

Y tuong (giong feature selection trong ML): voi moi label, OCR TAT CA anh cua no ->
  dem token xuat hien o BAO NHIEU anh (document frequency). Chon token:
    - DF cao trong label (bao phu nhieu anh cua label do),
    - DF thap o label KHAC (dac trung, it nham) -> giong TF-IDF.
  In ra goi y keyword (phu >=X% anh, khong dung chung voi label khac).

Chay: .venv/bin/python automation/derive_keywords.py [label]
Ket qua -> knowledge/_derived_keywords.json (tham khao de sua NODES/OVERLAYS).
"""
import os, sys, json, cv2, re
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from screen_reader import ScreenReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(ROOT, "exploration", "world.json")
OUT = os.path.join(ROOT, "knowledge", "_derived_keywords.json")
CACHE = os.path.join(ROOT, "knowledge", "_ocr_tokens", "world_tokens.json")

IGNORE = {"World", "Event Overview"}


def tokenize(text):
    # tach tu, bo dau, lower; giu tu >= 3 ky tu (tranh nhieu).
    return [t for t in re.findall(r"[A-Za-z]+", text.lower()) if len(t) >= 3]


def ocr_all():
    """OCR moi anh -> set token. Cache ra file (OCR cham ~1.2s/anh)."""
    if os.path.exists(CACHE):
        return json.load(open(CACHE))
    w = json.load(open(WORLD))
    out = {}                                         # sid -> {label, tokens[]}
    items = list(w["states"].items())
    for i, (sid, s) in enumerate(items):
        if s["label"] in IGNORE:
            continue
        img = cv2.imread(os.path.join(ROOT, s["screenshot"]))
        if img is None:
            continue
        r = ScreenReader(img)
        toks = set()
        for t in r.tappables():
            toks |= set(tokenize(t[0]))
        out[sid] = {"label": s["label"], "tokens": sorted(toks)}
        print(f"  OCR {i+1}/{len(items)} {s['label']:18} {len(toks)} token", flush=True)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(out, open(CACHE, "w"), ensure_ascii=False, indent=1)
    return out


def main():
    data = ocr_all()
    # gom theo label
    by_label = defaultdict(list)                     # label -> [token_set,...]
    for v in data.values():
        by_label[v["label"]].append(set(v["tokens"]))
    # DF toan cuc moi token (so anh chua no, tren tat ca label)
    global_df = Counter()
    for v in data.values():
        global_df.update(set(v["tokens"]))
    n_imgs = len(data)

    suggest = {}
    target = sys.argv[1] if len(sys.argv) > 1 else None
    for label in sorted(by_label):
        sets = by_label[label]
        n = len(sets)
        in_df = Counter()                            # so anh cua label nay chua token
        for s in sets:
            in_df.update(s)
        # diem = (phu trong label) * (dac trung: it xuat hien o label khac)
        scored = []
        for tok, df_in in in_df.items():
            cover = df_in / n                        # bao phu trong label
            df_out = global_df[tok] - df_in          # so anh label KHAC chua token
            spec = 1.0 / (1 + df_out)                # cang it nham cang cao
            scored.append((cover * spec, cover, df_in, df_out, tok))
        scored.sort(reverse=True)
        top = scored[:8]
        suggest[label] = [
            {"token": t, "cover": round(c, 2), "in": di, "out": do}
            for _, c, di, do, t in top
        ]
        if target is None or target.lower() in label.lower():
            print(f"\n=== {label} ({n} anh) ===")
            for sc, c, di, do, t in top:
                print(f"  {t:16} phu={c:.2f} ({di}/{n} anh)  nham_label_khac={do}  diem={sc:.2f}")

    json.dump(suggest, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"\n-> luu goi y: {OUT}")


if __name__ == "__main__":
    main()
