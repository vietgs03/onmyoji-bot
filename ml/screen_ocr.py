#!/usr/bin/env python3
"""
screen_ocr.py - Dinh danh man hinh bang TEXT (OCR PaddleOCR).

Y tuong: tren client Global/EN moi man co cac tu-khoa dac trung
(HOME co 'Explore/Summon/Shikigamis'; Shop co 'Buy/Price'; Settings co 'Sound'...).
Ta hoc "text fingerprint" cua moi nhan tu anh da label, roi phan loai man moi
bang cosine TF-IDF. Manh + de hieu hon CNN, khong can GPU.

CAI TIEN (senior):
  1. Cache OCR THEO PER-IMAGE HASH (knowledge/_ocr_tokens/<md5>.json) -> chi OCR
     anh moi, train nhanh, khong timeout. Cache ben qua nhieu lan build.
  2. Eval LEAVE-ONE-OUT THAT (rebuild fingerprint loai ANH dang test) -> con so
     trung thuc khi gap man moi, day la ROI metric.
  3. ANCHOR token co vi tri (title-bar y<140) duoc nhan trong so cao -> phan biet
     popup-de-HOME (vd Group Buying) voi HOME that. Tang chinh xac, giam nham.

Build:  python screen_ocr.py build   -> sinh knowledge/screen_text.json
Eval:   python screen_ocr.py eval    -> LOO accuracy (metric that)
Pred:   python screen_ocr.py pred <anh.png>
"""
import os, sys, json, glob, collections, math, re, hashlib
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ml.ocr import ocr_words  # noqa

WORLD = os.path.join(ROOT, "exploration", "world.json")
SCREENS = os.path.join(ROOT, "exploration", "screens")
OUT = os.path.join(ROOT, "knowledge", "screen_text.json")
TOKDIR = os.path.join(ROOT, "knowledge", "_ocr_tokens")  # cache per-image

_WORD_RE = re.compile(r"[a-z]{2,}")
_TITLE_Y = 140          # token co y < nguong nay = title/header (anchor manh)
_ANCHOR_W = 2.5         # trong so token title-bar (anchor dac trung man)


def _feats(img):
    """Trich token tu anh -> dict {token: weight}. Token o title-bar (y nho)
    duoc nhan trong so cao vi no la dac trung dinh danh man (vd 'Summon','Settings').
    Tra dict de giu trong so, va set de tuong thich code cu."""
    feats = collections.Counter()
    h = img.shape[0]
    for t, (x, y, w, hh), conf in ocr_words(img, min_conf=70):
        weight = _ANCHOR_W if y < _TITLE_Y else 1.0
        for word in _WORD_RE.findall(t.lower()):
            feats[word] = max(feats[word], weight)  # giu trong so cao nhat
    return dict(feats)


def tokens(img):
    """Tuong thich nguoc: tra set token (khong trong so). Dung boi screen_reader cu."""
    return set(_feats(img))


# ---------- cache per-image ----------
def _img_key(path):
    """Hash noi dung anh -> key cache on dinh."""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def _cached_feats(path):
    """Tra dict feats cho 1 anh, dung cache neu co (theo hash noi dung)."""
    os.makedirs(TOKDIR, exist_ok=True)
    key = _img_key(path)
    cp = os.path.join(TOKDIR, key + ".json")
    if os.path.exists(cp):
        return json.load(open(cp))
    img = cv2.imread(path)
    feats = _feats(img) if img is not None else {}
    json.dump(feats, open(cp, "w"))
    return feats


def _labeled():
    w = json.load(open(WORLD))
    out = {}
    for sid, st in w["states"].items():
        lbl = st.get("label")
        p = os.path.join(SCREENS, sid + ".png")
        if lbl and os.path.exists(p):
            out.setdefault(lbl, []).append((sid, p))
    return out


def _all_feats():
    """{sid: feats_dict} cho moi anh label, dung cache per-image (OCR 1 lan/anh)."""
    data = _labeled()
    feats = {}
    new = 0
    for lbl, items in data.items():
        for sid, p in items:
            key = _img_key(p)
            cp = os.path.join(TOKDIR, key + ".json")
            if not os.path.exists(cp):
                new += 1
            feats[sid] = _cached_feats(p)
    if new:
        print(f"  OCR {new} anh moi (con lai dung cache)")
    return feats


# ---------- model ----------
def _build_idf(feats):
    """IDF tren toan bo anh (df = so anh chua token)."""
    N = len(feats)
    df = collections.Counter()
    for f in feats.values():
        for w in f:
            df[w] += 1
    return {w: math.log((N + 1) / (c + 1)) + 1 for w, c in df.items()}


def _build_fp(data, feats, idf, exclude=None):
    """Fingerprint moi nhan = tong (weight*idf) token qua cac anh cua nhan.
    exclude: sid bo qua (cho leave-one-out)."""
    fp = {}
    for lbl, items in data.items():
        score = collections.Counter()
        n = 0
        for sid, _ in items:
            if sid == exclude:
                continue
            n += 1
            for w, wt in feats.get(sid, {}).items():
                score[w] += wt * idf.get(w, 1.0)
        if n == 0:
            continue
        fp[lbl] = dict(score.most_common(30))
    return fp


def _classify(qfeats, idf, fps):
    """Cosine giua query (weight*idf) va moi fingerprint. Tra (best, score, all)."""
    qvec = {w: wt * idf.get(w, 1.0) for w, wt in qfeats.items()}
    qnorm = math.sqrt(sum(v * v for v in qvec.values())) or 1.0
    best, bs, scores = None, -1.0, {}
    for lbl, fp in fps.items():
        dot = sum(qvec.get(w, 0) * v for w, v in fp.items())
        fnorm = math.sqrt(sum(v * v for v in fp.values())) or 1.0
        s = dot / (qnorm * fnorm)
        scores[lbl] = s
        if s > bs:
            bs, best = s, lbl
    return best, bs, scores


def build():
    data = _labeled()
    feats = _all_feats()
    idf = _build_idf(feats)
    fps = _build_fp(data, feats, idf)
    json.dump({"idf": idf, "fingerprints": fps}, open(OUT, "w"), indent=1)
    print(f"\nbuilt {OUT}: {len(fps)} nhan, vocab {len(idf)}")
    for lbl, sc in fps.items():
        top = ", ".join(list(sc)[:6])
        print(f"  {lbl:22} <- {top}")


def _model():
    return json.load(open(OUT))


def predict(img, model=None):
    """Tra (nhan, score cosine 0..1, scores dict) cho anh moi."""
    model = model or _model()
    return _classify(_feats(img), model["idf"], model["fingerprints"])


def evaluate():
    """LEAVE-ONE-OUT THAT: voi moi anh, rebuild fingerprint LOAI anh do roi predict.
    Day la accuracy trung thuc khi gap man moi (khong phai re-substitution)."""
    data = _labeled()
    feats = _all_feats()
    idf = _build_idf(feats)
    correct = total = 0
    by_lbl = collections.Counter()
    tot_lbl = collections.Counter()
    confusion = collections.Counter()
    for lbl, items in data.items():
        for sid, p in items:
            fps = _build_fp(data, feats, idf, exclude=sid)
            best, bs, _ = _classify(feats.get(sid, {}), idf, fps)
            total += 1
            tot_lbl[lbl] += 1
            if best == lbl:
                correct += 1
                by_lbl[lbl] += 1
            else:
                confusion[(lbl, best)] += 1
    print(f"\nLOO accuracy (THAT): {correct}/{total} = {correct/total:.3f}")
    for lbl in sorted(tot_lbl):
        mark = "" if by_lbl[lbl] == tot_lbl[lbl] else "  <-- can them mau"
        print(f"  {lbl:22} {by_lbl[lbl]}/{tot_lbl[lbl]}{mark}")
    if confusion:
        print("\nnham lan (that -> doan, so lan):")
        for (a, b), n in confusion.most_common(10):
            print(f"  {a:20} -> {b:20} x{n}")
    return correct / total


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "eval":
        evaluate()
    elif cmd == "pred":
        img = cv2.imread(sys.argv[2])
        lbl, s, scores = predict(img)
        print(f"-> {lbl}  (cosine {s:.3f})")
        for L, v in sorted(scores.items(), key=lambda z: -z[1])[:5]:
            print(f"   {L:22} {v:.3f}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
