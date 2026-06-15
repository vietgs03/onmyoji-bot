"""oas_page_detector.py - Detector man hinh game dua tren asset OAS (ground-truth).

Port co chon loc OAS RuleImage.match: crop anh ve roi_back -> cv2.matchTemplate
template (TM_CCOEFF_NORMED) -> max_val > threshold. OAS chay 1280x720; game ta
1136x640 (ti le ~0.888, cung 16:9) nen ta SCALE ca ROI lan template xuong.

Dung de:
- Biet chinh xac dang o page nao (theo OAS, da kiem chung tren game that).
- Lam ground-truth danh gia RustEye dhash/state_id.

Cach dung:
    det = OASPageDetector()
    page = det.detect(img_bgr_1136x640)   # vd 'page_main' hoac None
    pages = det.detect_all(img)           # tat ca page khop (co the >1)
"""
import os
import re
import cv2
import numpy as np

OAS_ROOT = "/home/viethx/onmyoji-bot/research/OAS"
GAMEUI_ASSETS = os.path.join(OAS_ROOT, "tasks/GameUi/assets.py")
PAGE_PY = os.path.join(OAS_ROOT, "tasks/GameUi/page.py")

# OAS resolution -> game resolution
OAS_W, OAS_H = 1280, 720
GAME_W, GAME_H = 1136, 640
SX, SY = GAME_W / OAS_W, GAME_H / OAS_H  # ~0.8875, 0.8889

# regex doc RuleImage: ten = RuleImage(roi_front=(...), roi_back=(...),
#                       threshold=..., method="...", file="...")
_RULE_RE = re.compile(
    r'(\w+)\s*=\s*RuleImage\('
    r'roi_front=\(([^)]*)\)\s*,\s*'
    r'roi_back=\(([^)]*)\)\s*,\s*'
    r'threshold=([\d.]+)\s*,\s*'
    r'method="([^"]*)"\s*,\s*'
    r'file="([^"]*)"'
)


def _parse_assets(path):
    """Doc file assets.py -> dict {ten: {roi_back, threshold, method, file}}."""
    out = {}
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    for m in _RULE_RE.finditer(txt):
        name, rf, rb, thr, method, fname = m.groups()
        rb = [int(x) for x in rb.split(",")]
        out[name] = {
            "roi_back": rb,
            "threshold": float(thr),
            "method": method,
            "file": fname.replace("./", OAS_ROOT + "/"),
        }
    return out


def _parse_page_checks(path):
    """Doc page.py -> dict {page_name: asset_name} qua Page(G.I_CHECK_xxx)."""
    out = {}
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    # page_main = Page(G.I_CHECK_MAIN)  hoac  Page(GGA.I_CHECK_xxx, ...)
    for m in re.finditer(r'(page_\w+)\s*=\s*Page\(\s*\w+\.(I_\w+)', txt):
        out[m.group(1)] = m.group(2)
    return out


class OASPageDetector:
    def __init__(self):
        self.assets = _parse_assets(GAMEUI_ASSETS)
        self.page_checks = _parse_page_checks(PAGE_PY)
        # load + scale template cho moi page co asset hop le
        self.pages = {}  # page_name -> (roi_back_scaled, template_scaled, threshold)
        for page, asset_name in self.page_checks.items():
            a = self.assets.get(asset_name)
            if not a or a["method"] != "Template matching":
                continue
            tmpl = cv2.imread(a["file"])
            if tmpl is None:
                continue
            # scale template xuong do phan giai game
            th, tw = tmpl.shape[:2]
            ntw, nth = max(1, round(tw * SX)), max(1, round(th * SY))
            tmpl_s = cv2.resize(tmpl, (ntw, nth), interpolation=cv2.INTER_AREA)
            # scale roi_back
            x, y, w, h = a["roi_back"]
            rb = [round(x * SX), round(y * SY), round(w * SX), round(h * SY)]
            self.pages[page] = (rb, tmpl_s, a["threshold"], asset_name)

    def _score(self, img, rb, tmpl):
        """Tra max TM_CCOEFF_NORMED cua tmpl trong vung rb cua img."""
        x, y, w, h = rb
        H, W = img.shape[:2]
        x = max(0, min(x, W - 1)); y = max(0, min(y, H - 1))
        w = max(1, min(w, W - x)); h = max(1, min(h, H - y))
        src = img[y:y + h, x:x + w]
        th, tw = tmpl.shape[:2]
        if src.shape[0] < th or src.shape[1] < tw:
            return -1.0
        res = cv2.matchTemplate(src, tmpl, cv2.TM_CCOEFF_NORMED)
        return float(cv2.minMaxLoc(res)[1])

    def detect_all(self, img):
        """Tra list (page_name, score) cho moi page vuot threshold, sap giam dan."""
        hits = []
        for page, (rb, tmpl, thr, _) in self.pages.items():
            s = self._score(img, rb, tmpl)
            if s >= thr:
                hits.append((page, s))
        hits.sort(key=lambda x: -x[1])
        return hits

    def detect(self, img):
        """Tra page khop manh nhat (hoac None)."""
        hits = self.detect_all(img)
        return hits[0][0] if hits else None

    def scores(self, img):
        """Tra dict {page: score} TAT CA page (de debug nguong)."""
        return {p: self._score(img, rb, t) for p, (rb, t, _, _) in self.pages.items()}


if __name__ == "__main__":
    import sys
    det = OASPageDetector()
    print(f"loaded {len(det.pages)}/{len(det.page_checks)} page co template hop le")
    print(f"scale OAS->game: SX={SX:.4f} SY={SY:.4f}")
    if len(sys.argv) > 1:
        img = cv2.imread(sys.argv[1])
        print(f"\nanh {sys.argv[1]} ({img.shape[1]}x{img.shape[0]}):")
        hits = det.detect_all(img)
        if hits:
            for p, s in hits:
                print(f"  {p:30} score={s:.3f}")
        else:
            print("  khong khop page nao. Top 5 score:")
            sc = sorted(det.scores(img).items(), key=lambda x: -x[1])[:5]
            for p, s in sc:
                print(f"  {p:30} score={s:.3f}")
