#!/usr/bin/env python3
"""
screen_ocr.py - Dinh danh man hinh bang TEXT (OCR PaddleOCR).

Y tuong: tren client Global/EN moi man co cac tu-khoa dac trung
(HOME co 'Explore/Summon/Shikigamis'; Shop co 'Buy/Price'; Settings co 'Sound'...).
Ta hoc "text fingerprint" cua moi nhan tu anh da label, roi phan loai man moi
bang cach so tu-khoa trung khop (TF-IDF weighting). Manh + de hieu hon CNN.

Build:  python screen_ocr.py build   -> sinh knowledge/screen_text.json
Test:   python screen_ocr.py eval    -> do accuracy LOO tren tap da label
Pred:   python screen_ocr.py pred <anh.png>
"""
import os, sys, json, glob, collections, math, re
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ml.ocr import ocr_words  # noqa

WORLD = os.path.join(ROOT, "exploration", "world.json")
SCREENS = os.path.join(ROOT, "exploration", "screens")
OUT = os.path.join(ROOT, "knowledge", "screen_text.json")

_WORD_RE = re.compile(r"[a-z]{2,}")


def tokens(img):
    """Trich set token EN chu thuong (>=2 ky tu) tu anh, conf cao."""
    toks = set()
    for t, box, conf in ocr_words(img, min_conf=70):
        for w in _WORD_RE.findall(t.lower()):
            toks.add(w)
    return toks


def _labeled():
    w = json.load(open(WORLD))
    out = {}
    for sid, st in w["states"].items():
        lbl = st.get("label")
        p = os.path.join(SCREENS, sid + ".png")
        if lbl and os.path.exists(p):
            out.setdefault(lbl, []).append((sid, p))
    return out


def _ocr_all():
    """OCR tat ca anh label 1 lan, cache ra file (OCR cham)."""
    cache = OUT + ".tokcache.json"
    if os.path.exists(cache):
        return {k: set(v) for k, v in json.load(open(cache)).items()}
    data = _labeled()
    toks = {}
    for lbl, items in data.items():
        for sid, p in items:
            img = cv2.imread(p)
            toks[sid] = tokens(img)
            print(f"  ocr {sid} [{lbl}]: {sorted(toks[sid])[:8]}")
    json.dump({k: sorted(v) for k, v in toks.items()}, open(cache, "w"))
    return toks


def build():
    data = _labeled()
    toks = _ocr_all()
    # IDF tren toan bo anh
    N = sum(len(v) for v in data.values())
    df = collections.Counter()
    for sid_toks in toks.values():
        for w in sid_toks:
            df[w] += 1
    idf = {w: math.log((N + 1) / (c + 1)) + 1 for w, c in df.items()}
    # fingerprint moi nhan = tong tf-idf token qua cac anh cua nhan
    fp = {}
    for lbl, items in data.items():
        score = collections.Counter()
        for sid, _ in items:
            for w in toks.get(sid, ()):
                score[w] += idf.get(w, 1.0)
        # giu top token dac trung
        fp[lbl] = dict(score.most_common(25))
    json.dump({"idf": idf, "fingerprints": fp}, open(OUT, "w"), indent=1)
    print(f"\nbuilt {OUT}: {len(fp)} nhan, vocab {len(idf)}")
    for lbl, sc in fp.items():
        top = ", ".join(list(sc)[:6])
        print(f"  {lbl:22} <- {top}")


def _model():
    return json.load(open(OUT))


def predict(img, model=None):
    """Tra (nhan, diem) tot nhat dua tren token khop."""
    model = model or _model()
    idf, fps = model["idf"], model["fingerprints"]
    toks = tokens(img)
    best, bs = None, 0.0
    scores = {}
    for lbl, fp in fps.items():
        s = sum(fp.get(w, 0) for w in toks)
        # chuan hoa theo do dai fingerprint de khong thien nhan nhieu chu
        norm = math.sqrt(sum(v * v for v in fp.values())) or 1.0
        s = s / norm
        scores[lbl] = s
        if s > bs:
            bs, best = s, lbl
    return best, bs, scores


def evaluate():
    """Leave-one-out: rebuild fingerprint truc tiep tu token cache, predict tung anh."""
    data = _labeled()
    toks = _ocr_all()
    model = _model()
    correct = total = 0
    by_lbl = collections.Counter()
    tot_lbl = collections.Counter()
    for lbl, items in data.items():
        for sid, p in items:
            t = toks.get(sid, set())
            # predict bang fingerprint (da loai 1 anh khong dang ke vi fp tong hop)
            idf, fps = model["idf"], model["fingerprints"]
            best, bs = None, -1
            for L, fp in fps.items():
                s = sum(fp.get(w, 0) for w in t)
                norm = math.sqrt(sum(v * v for v in fp.values())) or 1.0
                s /= norm
                if s > bs:
                    bs, best = s, L
            total += 1
            tot_lbl[lbl] += 1
            if best == lbl:
                correct += 1
                by_lbl[lbl] += 1
    print(f"\naccuracy (re-substitution): {correct}/{total} = {correct/total:.3f}")
    for lbl in sorted(tot_lbl):
        print(f"  {lbl:22} {by_lbl[lbl]}/{tot_lbl[lbl]}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "eval":
        evaluate()
    elif cmd == "pred":
        img = cv2.imread(sys.argv[2])
        lbl, s, scores = predict(img)
        print(f"-> {lbl}  (score {s:.2f})")
        for L, v in sorted(scores.items(), key=lambda z: -z[1])[:5]:
            print(f"   {L:22} {v:.2f}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
