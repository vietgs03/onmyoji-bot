#!/usr/bin/env python3
"""soul_lines.py - Doc DONG PHU (substats) cua Ngu Hon (soul) tu anh man chi tiet.

Muc dich: task cuong hoa soul can biet lan roll vua roi vao dong nao de quyet dinh
di tiep hay dung (chien thuat loc som). File nay tach phan "doc" ra khoi task de
test OFFLINE duoc (khong can game): chi can dua vao list (text, bbox, conf) cua OCR.

Cach doc: OCR full anh man chi tiet soul -> moi dong phu la 1 cap
  <ten thuoc tinh>  <gia tri>
nam gan nhau theo truc Y (cung 1 hang). Cac ten thuoc tinh la tap dong (closed set),
nen ta nhan dien theo ten thay vi vi tri -> ben voi layout/do phan giai.

API:
  lines_from_ocr(words)                 -> [SoulLine(name, value, y, raw_name)]
  stat_of(line)                         -> key chuan hoa ('spd','atk_pct',...) hoac None
  parse_lines(words, stats=None) -> SoulState(stats={key: value}, lines=[...])

CLI (test offline bang OCR 1 anh):
  python ml/soul_lines.py <anh.png>
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- Alias ten thuoc tinh (EN cua client Global + vai bien the OCR) -> key chuan ---
# Man soul trong client EN hien ten nhu: Attack, Attack Bonus, HP, HP Bonus,
# Defense, Defense Bonus, Speed, Crit Rate, Crit DMG, Effect Hit, Effect RES.
ALIASES = {
    "atk": "atk", "attack": "atk",
    "atk_pct": "atk_pct", "attackbonus": "atk_pct", "attack%": "atk_pct",
    "hp": "hp",
    "hp_pct": "hp_pct", "hpbonus": "hp_pct", "hp%": "hp_pct",
    "def": "def", "defense": "def", "defence": "def",
    "def_pct": "def_pct", "defensebonus": "def_pct", "defencebonus": "def_pct",
    "defense%": "def_pct",
    "spd": "spd", "speed": "spd",
    "crit": "crit", "critrate": "crit", "criticalrate": "crit",
    "critdmg": "crit_dmg", "critdamage": "crit_dmg", "critdmg%": "crit_dmg",
    "efhit": "eff_hit", "effecthit": "eff_hit", "effecthitrate": "eff_hit",
    "effhit": "eff_hit", "hit": "eff_hit",
    "efres": "eff_res", "effectres": "eff_res", "effectresist": "eff_res",
    "effectresistance": "eff_res", "res": "eff_res",
}

_PCT = re.compile(r"%\s*$")
_NUM = re.compile(r"^\+?\s*(\d+(?:[.,]\d+)?)\s*(%?)\s*$")
_ROW_TOL = 20.0     # sai lech Y toi da de coi la "cung hang" voi ten dong


class SoulLine:
    __slots__ = ("name", "value", "pct", "y", "x")

    def __init__(self, name, value=None, pct=False, y=0.0, x=0.0):
        self.name = name      # ten goc tren man hinh
        self.value = value    # so (float) hoac None neu OCR khong ra so
        self.pct = pct        # True neu co '%'
        self.y = y
        self.x = x

    @property
    def key(self):
        return stat_of(self)

    def __repr__(self):
        v = "" if self.value is None else (f"{self.value:g}{'%' if self.pct else ''}")
        return f"SoulLine({self.name!r}, {v}, y={self.y:.0f})"


class SoulState:
    """Trang thai dong phu cua 1 soul: stats map key->gia tri."""

    def __init__(self, stats=None, lines=None, level=None):
        self.stats = stats or {}          # {'spd': 2.8, 'atk_pct': 4.0, ...}
        self.lines = lines or []
        self.level = level

    def __repr__(self):
        return f"SoulState(lv={self.level}, {self.stats})"

    def get(self, key, default=None):
        return self.stats.get(key, default)


def _norm_name(s):
    s = re.sub(r"[\s_\-\.]+", "", str(s)).lower()
    return s


def stat_of(line):
    """Chuan hoa ten dong phu -> key ('spd','crit','atk_pct',...). None neu khong ro."""
    n = _norm_name(line.name)
    if n in ALIASES:
        return ALIASES[n]
    # 'Attack Bonus' -> 'attackbonus' da co trong bang; thu them dang co '%' o ten
    n2 = n.replace("%", "")
    if n2 + "%" in ALIASES:
        return ALIASES[n2 + "%"]
    return None


def parse_value(txt):
    """'12%' -> (12.0, True); '+3' -> (3.0, False); 'abc' -> (None, False)."""
    m = _NUM.match(str(txt).strip())
    if not m:
        return None, False
    v = float(m.group(1).replace(",", "."))
    return v, (m.group(2) == "%")


def lines_from_ocr(words):
    """words = [(text, (x,y,w,h), conf)] -> [SoulLine] da ghep ten + gia tri.

    Ghep theo truc Y: ten dong va so cua no nam cung 1 hang (|dy| <= nua chieu cao).
    """
    names, nums = [], []
    for w in words:
        txt, box = str(w[0]), w[1]
        x, y, bw, bh = box[0], box[1], box[2], box[3]
        cx, cy = x + bw / 2.0, y + bh / 2.0
        if stat_of(SoulLine(txt)) is not None:
            names.append((txt, cx, cy, bh))
            continue
        v, pct = parse_value(txt)
        if v is not None:
            nums.append((v, pct, cx, cy))
    out = []
    for txt, cx, cy, bh in names:
        # Buoc 1: LOC theo hang - chi giu so CUNG HANG voi ten dong (dy <= _ROW_TOL).
        # Buoc 2: trong cac so cung hang, chon so gan nhat theo truc X va uu tien '%'.
        # (Khong tron dy vao diem ngang: khung ten-value cach nhau ~400px nen dy
        #  nho khong du y de tach, phai LOC truoc roi moi xet.)
        row = []
        for v, pct, nx, ny in nums:
            dy = abs(ny - cy)
            dx = nx - cx
            if dx < -8 or dy > max(_ROW_TOL, bh * 0.9):
                continue                                   # khac hang / nam ben trai ten
            row.append((dx, v, pct))
        best = None
        if row:
            row.sort(key=lambda r: (0 if r[2] else 1, r[0]))   # uu tien %, roi gan nhat
            dx, v, pct = row[0]
            best = (v, pct)
        out.append(SoulLine(txt, best[0] if best else None,
                            best[1] if best else False, cy, cx))
    out.sort(key=lambda l: l.y)
    return out


def parse_lines(words, level=None):
    """Tien ich: OCR words -> SoulState (bo dong khong nhan dien duoc ten)."""
    stats = {}
    lines = lines_from_ocr(words)
    for l in lines:
        k = l.key
        if k and l.value is not None:
            stats[k] = l.value
    return SoulState(stats, lines, level=level)


def read_soul(img, roi=None, min_conf=40, level=None):
    """Doc truc tiep tu anh (can ppocr). Day la lop mong, test offline dung parse_lines."""
    from ocr import ocr_words
    return parse_lines(ocr_words(img, roi=roi, min_conf=min_conf), level=level)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    import cv2
    from ocr import ocr_words
    img = cv2.imread(sys.argv[1])
    st = read_soul(img, min_conf=30)
    print("stats:", st.stats)
    for l in st.lines:
        print("  ", l)


if __name__ == "__main__":
    main()
