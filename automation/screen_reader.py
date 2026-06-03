#!/usr/bin/env python3
"""ScreenReader - hieu man hinh DONG (khong phu thuoc lop hoc cung).

Triet ly: game "muon van muon ve" + event doi lien tuc -> KHONG the train
classifier cho moi man. Thay vao do doc TEXT + button tren man -> dieu huong
theo NGU NGHIA. Man la -> van xu ly duoc (vi doc chu, khong can biet ten man).

3 tang:
  1. OCR text (PaddleOCR) - doc moi chu + toa do + conf
  2. UI layout tinh (ui_lookup) - button co dinh (back/close/auto) du khong co chu
  3. Button detection (perception.detect_buttons) - dom tron/nut neu can

API:
  r = ScreenReader(img)
  r.texts()                  # [(text, cx, cy, conf)]
  r.find("Town")             # exact/fuzzy -> (cx, cy, text, conf) hoac None
  r.find_all("event")        # tat ca khop
  r.has("Summon")            # bool
  r.tappables()              # text giong button (loai marquee/dong thoi gian)
  r.describe()               # tom tat man hinh de log/debug
"""
import difflib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "ml"))
sys.path.insert(0, os.path.join(ROOT, "knowledge"))

from ocr import ocr_words  # noqa: E402

# tu/cum hay xuat hien trong marquee (thong bao cuon tren cung) -> bo
_MARQUEE_HINT = re.compile(
    r"summoned|challenging|triggered|requested|shard zone|add them|friend to|"
    r"obtained|the rare|sigil|has |is |a |to |them|rare ", re.I)

# vung marquee tren cung (y < 130) - thong bao cuon, bo khi tim button
_MARQUEE_Y = 130


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


class ScreenReader:
    def __init__(self, img, min_conf=55):
        self.img = img
        self.h, self.w = (img.shape[:2] if img is not None else (0, 0))
        self.words = ocr_words(img, min_conf=min_conf) if img is not None else []

    # ---------- text ----------
    def texts(self):
        out = []
        for txt, (x, y, w, h), conf in self.words:
            out.append((txt, x + w // 2, y + h // 2, conf))
        return out

    def _candidates(self, drop_marquee=True):
        """Loc bo marquee (thong bao cuon tren cung) + text dai - khong phai button."""
        res = []
        for txt, (x, y, w, h), conf in self.words:
            cy = y + h // 2
            if drop_marquee:
                # marquee: o dai bang tren cung (y nho) HOAC text dai/co tu thong bao
                if cy < _MARQUEE_Y and (w > 120 or _MARQUEE_HINT.search(txt)):
                    continue
                if len(txt) > 24 or _MARQUEE_HINT.search(txt):
                    continue
            res.append((txt, x + w // 2, cy, conf))
        return res

    # ---------- tim element ----------
    def find(self, target, fuzzy=0.8):
        """Tim 1 element khop nhat. Exact (chuan hoa) > fuzzy ratio."""
        tn = _norm(target)
        cands = self._candidates()
        # exact / substring chuan hoa
        exact = [(c, abs(c[1] - self.w / 2)) for c in cands
                 if tn == _norm(c[0]) or (len(tn) >= 4 and tn in _norm(c[0]))]
        if exact:
            return min(exact, key=lambda e: e[1])[0]
        # fuzzy
        best, best_r = None, fuzzy
        for c in cands:
            r = difflib.SequenceMatcher(None, tn, _norm(c[0])).ratio()
            if r >= best_r:
                best, best_r = c, r
        return best

    def find_all(self, target):
        tn = _norm(target)
        return [c for c in self._candidates()
                if tn in _norm(c[0]) or
                difflib.SequenceMatcher(None, tn, _norm(c[0])).ratio() >= 0.8]

    def has(self, target, fuzzy=0.8):
        return self.find(target, fuzzy) is not None

    def tappables(self):
        """Text co the la button (ngan, khong phai marquee/timer)."""
        out = []
        for txt, cx, cy, conf in self._candidates():
            if len(_norm(txt)) < 2:
                continue
            out.append((txt, cx, cy, conf))
        return out

    # ---------- debug ----------
    def describe(self):
        taps = self.tappables()
        lines = [f"Man hinh {self.w}x{self.h}, {len(self.words)} text, "
                 f"{len(taps)} button kha nang:"]
        for txt, cx, cy, conf in sorted(taps, key=lambda t: (t[2], t[1])):
            lines.append(f"  [{conf:5.1f}] '{txt}' @ ({cx},{cy})")
        return "\n".join(lines)


def main():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from control_client import Controller
    ctl = Controller()
    img = ctl.bgshot()
    ctl.close()
    r = ScreenReader(img)
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print(f"find('{q}') ->", r.find(q))
        print(f"find_all('{q}') ->", r.find_all(q))
    else:
        print(r.describe())


if __name__ == "__main__":
    main()
