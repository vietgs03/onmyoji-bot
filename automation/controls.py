#!/usr/bin/env python3
"""
controls.py - Nhan dien CHINH XAC cac nut DIEU KHIEN (back / close-X / cancel)
              o moi menu bang TEMPLATE MATCHING tu thu vien OAS.

Bai hoc dat gia: agent truoc day DOAN mu vi tri nut back/X -> ket o Summon Room.
OAS co san 167 template anh nut dieu khien (41 back, 33 close, ... voi toa do +
mo ta). Cac nut ICON (mui ten back, X do dong popup) GIONG nhau giua client EN/TQ
nen template-match dung duoc cho game Steam EN cua ta. (Nut co CHU TQ nhu '取消'
thi bo qua, dung OCR EN thay the.)

Cach dung:
  from controls import ControlFinder
  cf = ControlFinder()
  hit = cf.find(img, kind='back')   # tra (cx, cy, score, name) hoac None
  hit = cf.find(img, kind='close')  # nut X dong popup
  all_ = cf.find_all(img)           # moi nut dieu khien tren man

Phan loai 'kind':
  back   - mui ten quay lai (goc tren-trai, nhieu mau: yellow/blue/green)
  close  - X dong popup (do/hong, goc tren-phai cua popup)
  cancel - nut huy (thuong co chu -> dung OCR, it template icon)

Build cache template 1 lan: python controls.py build
Test:                        python controls.py test <anh.png>
"""
import os, re, glob, sys, json
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OAS = os.path.join(ROOT, "research", "OAS")
CACHE = os.path.join(ROOT, "knowledge", "control_templates.json")

# Game Steam EN 1152x679 vs OAS 1280x720. Template anh OAS cung o 1280x720
# -> scale template ve ti le game truoc khi match.
SX, SY = 1152 / 1280, 679 / 720

_RULE = re.compile(
    r"(\w+)\s*=\s*RuleImage\(\s*roi_front=\((\d+),(\d+),(\d+),(\d+)\)"
    r".*?threshold=([\d.]+).*?file=\"([^\"]*)\"", re.S)

# Phan loai nut theo ten asset. Chi lay nut ICON (khong phu thuoc ngon ngu).
# Bo cac nut co kha nang la CHU (confirm/ensure/ok thuong co text TQ).
_KINDS = {
    "back":  ["I_BACK_BLUE", "I_BACK_YELLOW", "I_BACK_YOLLOW", "I_BACK_GREEN",
              "I_BACK_Y", "I_BACK_BL", "I_BACK", "I_BACK_MALL", "I_BACK_RED",
              "I_BACK_BOTTOM", "I_BACK_ACT_LIST", "I_BACK_FRIENDS", "I_GBB_BACK",
              "I_BACK_DAILY", "I_GR_BACK_YELLOW", "I_BACK_YELLOW_SEA",
              "I_BACK_BATTLE", "I_BACK_EXIT"],
    "close": ["I_RED_CLOSE", "I_AD_CLOSE_RED", "I_RECORDS_CLOSE",
              "I_PAPER_DOLL_CLOSE", "I_HYAKKIYAKOU_CLOSE",
              "I_MAIN_SCROLL_CLOSE", "I_PLANT_TREE_CLOSE"],
}


def _collect_templates():
    """Quet OAS assets.py -> {name: {kind, roi_src, file, threshold}} cho nut dieu khien."""
    name2kind = {}
    for kind, names in _KINDS.items():
        for n in names:
            name2kind[n] = kind
    out = {}
    for f in glob.glob(os.path.join(OAS, "tasks", "**", "assets.py"), recursive=True):
        txt = open(f, encoding="utf-8", errors="ignore").read()
        for m in _RULE.finditer(txt):
            name = m.group(1)
            if name not in name2kind:
                continue
            x, y, w, h = map(int, m.groups()[1:5])
            thr = float(m.group(6))
            file = m.group(7)
            p = os.path.join(OAS, file.replace("./", ""))
            if not os.path.exists(p):
                continue
            # vung search roi_back rong hon, nhung roi_front la vi tri nut that
            out[name] = {"kind": name2kind[name], "roi_src": [x, y, w, h],
                         "threshold": thr, "path": p}
    return out


class ControlFinder:
    _templates = None   # {name: {kind, gray-template (scaled), roi, threshold}}

    def __init__(self):
        if ControlFinder._templates is None:
            ControlFinder._templates = self._load()
        self.t = ControlFinder._templates

    def _load(self):
        meta = _collect_templates()
        out = {}
        for name, d in meta.items():
            img = cv2.imread(d["path"])
            if img is None:
                continue
            # scale template ve ti le game
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            nw = max(6, int(g.shape[1] * SX))
            nh = max(6, int(g.shape[0] * SY))
            g = cv2.resize(g, (nw, nh))
            out[name] = {"kind": d["kind"], "tmpl": g,
                         "threshold": d["threshold"]}
        return out

    # game UI co gian theo man/su kien -> thu nhieu ti le template (multi-scale).
    # range rong (0.6-1.4) vi back arrow xuat hien nhieu kich co (vd Char Showcase,
    # Shop back nho hon binh thuong).
    _SCALES = (0.62, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4)

    def _match_one(self, scene_gray, tmpl, region=None):
        """Template match 1 tmpl (DA THU NHIEU SCALE) trong scene/region.
        Tra (score, cx, cy). Multi-scale vi nut co gian theo man (vd Shop back nho hon)."""
        s = scene_gray
        ox = oy = 0
        if region:
            x0, y0, x1, y1 = region
            s = scene_gray[y0:y1, x0:x1]
            ox, oy = x0, y0
        best = (-1.0, 0, 0)
        for sc in self._SCALES:
            t = tmpl if sc == 1.0 else cv2.resize(tmpl, None, fx=sc, fy=sc)
            if s.shape[0] < t.shape[0] or s.shape[1] < t.shape[1]:
                continue
            res = cv2.matchTemplate(s, t, cv2.TM_CCOEFF_NORMED)
            _, mx, _, loc = cv2.minMaxLoc(res)
            if mx > best[0]:
                cx = ox + loc[0] + t.shape[1] // 2
                cy = oy + loc[1] + t.shape[0] // 2
                best = (mx, cx, cy)
        return best

    @staticmethod
    def _is_reddish(img, cx, cy, r=16):
        """Nut close X la VONG TRON DO/HONG. Kiem tra vung quanh (cx,cy) co du do.
        Tra True neu >= 12% pixel la do/hong (loc bot FP tren nen tim/xanh)."""
        H, W = img.shape[:2]
        x0, y0 = max(0, cx - r), max(0, cy - r)
        x1, y1 = min(W, cx + r), min(H, cy + r)
        patch = img[y0:y1, x0:x1]
        if patch.size == 0:
            return False
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        # do bao gom 2 dai hue (0-12 va 168-180)
        m1 = cv2.inRange(hsv, (0, 80, 80), (12, 255, 255))
        m2 = cv2.inRange(hsv, (168, 80, 80), (180, 255, 255))
        red = (m1 | m2) > 0
        return red.mean() >= 0.12

    @staticmethod
    def _find_red_circle(img, region):
        """Tim nut X DONG popup bang HSV: dom DO/HONG tron co dau X TRANG ben trong.
        Yeu cau do tron cao + pixel sang o tam (loai notification-dot do dac).
        Luu y: X "vien rong" tren nen sang co the bi bo sot -> fallback la
        find_close_button (HSV) trong Agent.back(). Tra (cx,cy,conf,'red_circle')|None."""
        x0, y0, x1, y1 = region
        roi = img[y0:y1, x0:x1]
        if roi.size == 0:
            return None
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        m1 = cv2.inRange(hsv, (0, 90, 90), (12, 255, 255))
        m2 = cv2.inRange(hsv, (166, 90, 90), (180, 255, 255))
        mask = cv2.morphologyEx(m1 | m2, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        for c in cnts:
            a = cv2.contourArea(c)
            if a < 150 or a > 2400:
                continue
            (cx, cy), r = cv2.minEnclosingCircle(c)
            if r < 9 or r > 26 or a / (np.pi * r * r + 1e-6) < 0.62:
                continue
            # dau X trang: tam phai co pixel sang (notification-dot dac thi khong)
            ix, iy, rr = int(cx), int(cy), int(r * 0.6)
            cen = gray[max(0, iy - rr):iy + rr, max(0, ix - rr):ix + rr]
            if cen.size == 0 or (cen > 180).mean() < 0.06:
                continue
            conf = 0.85
            if best is None or conf > best[2]:
                best = (int(x0 + cx), int(y0 + cy), conf, "red_circle")
        return best

    def find(self, img, kind="back", region=None, min_score=None):
        """Tim nut dieu khien tot nhat thuoc `kind`. Tra (cx,cy,score,name) | None.
        region: gioi han vung tim (back thuong goc trai, close goc phai-tren).
        - back : template-match (mui ten, nhieu mau/scale). Vung goc-trai nho nen
                 it nhieu -> nguong thap (0.68) van P=1.0, bat duoc back muon ve.
        - close: template-match (xac nhan mau do) HOAC HSV red-circle (bat X muon ve).
                 Nguong cao hon (0.82) vi vung rong, de nham icon."""
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        H, W = g.shape
        # nguong rieng theo loai (back an toan o nguong thap nho vung hep)
        if min_score is None:
            min_score = 0.72 if kind == "back" else 0.82
        if region is None:
            if kind == "back":
                region = (0, 0, int(W * 0.18), int(H * 0.20))      # goc tren-trai
            elif kind == "close":
                # X dong popup: uu tien goc tren-phai (vung pho bien nhat)
                region = (int(W * 0.6), 0, W, int(H * 0.35))
        best = None
        for name, d in self.t.items():
            if d["kind"] != kind:
                continue
            score, cx, cy = self._match_one(g, d["tmpl"], region)
            if score < min_score:
                continue
            if kind == "close" and not self._is_reddish(img, cx, cy):
                continue
            if best is None or score > best[2]:
                best = (cx, cy, score, name)
        # close: neu template khong bat, thu HSV red-circle (vong do DAC + X trang)
        # chi goc tren-phai. Luu y: X "vien rong" thi red-circle khong bat (do tron
        # thap) -> dua vao template + fallback find_close_button trong Agent.back().
        if kind == "close" and best is None:
            rc_region = (int(W * 0.62), 0, W, int(H * 0.32))
            best = self._find_red_circle(img, rc_region)
        return best

    def find_all(self, img, min_score=0.72):
        """Tra dict {kind: (cx,cy,score,name)} cho moi loai tim duoc."""
        out = {}
        for kind in _KINDS:
            hit = self.find(img, kind=kind, min_score=min_score)
            if hit:
                out[kind] = hit
        return out

    # === Nut THOAT dang CHU (game Steam EN) - tim bang OCR, khong template ===
    # Cac nut huy/thoat trong game EN la CHU tieng Anh (template OAS la chu TQ,
    # khong match). Vd: popup "Download Illustration" co nut Cancel; xac nhan
    # roi tran co Leave/Quit/Give Up; ...
    # Phan loai theo TAC DUNG -> agent biet bam gi de THOAT/HUY an toan.
    EXIT_WORDS = {
        # tu khoa (lowercase) -> loai. 'dismiss' = bam de thoat/huy/tu choi an toan.
        "cancel": "cancel", "no": "cancel", "later": "cancel",
        "exit": "exit", "quit": "exit", "leave": "exit", "give up": "exit",
        "close": "close", "back": "back", "return": "back",
        "skip": "skip",
        # luu y: KHONG coi 'confirm/ok/yes/download' la thoat (do la dong y/tiep tuc)
    }

    # Tu khoa nut THOAT dang chu (EN). Chi nhung tu RO RANG la nut huy/thoat.
    # Bo 'no'/'return'/'back' khoi text-match (de nham 'No.5', 'Fest Return',
    # ten event) - icon back-arrow da lo viec back roi.
    EXIT_WORDS = {
        "cancel": "cancel", "exit": "exit", "quit": "exit",
        "leave": "exit", "skip": "skip", "later": "cancel",
    }
    # 'give up' xu ly rieng (cum 2 tu)
    _EXIT_PHRASES = {"give up": "exit"}

    def find_text_button(self, img, want=None, reader=None):
        """Tim nut THOAT/HUY dang CHU (EN) bang OCR. Tra list
        [{'word','kind','center':(x,y),'conf'}] sap theo do tin.
        want: loc theo loai ('cancel'/'exit'/'skip') hoac None=tat ca.
        reader: ScreenReader co san (tranh OCR lai). Neu None se tu OCR.

        CHI khop nhan NGAN dung tu khoa ('Cancel','Exit','Quit','Leave','Skip',
        'Give Up'). KHONG khop cum dai (ten/mo ta) -> tranh FP 'Skill Close-up',
        'Returner Ebisu', 'Fest Return'."""
        import re as _re
        import sys as _sys
        _sys.path.insert(0, os.path.join(ROOT, "scripts"))
        _sys.path.insert(0, os.path.join(ROOT, "ml"))
        if reader is None:
            from screen_reader import ScreenReader
            reader = ScreenReader(img)
        hits = []
        for word, x, y, *rest in reader.tappables():
            toks = _re.findall(r"[a-z]+", word.strip().lower())
            joined = " ".join(toks)
            kind = None
            if joined in self._EXIT_PHRASES:           # cum 'give up'
                kind = self._EXIT_PHRASES[joined]
            elif len(toks) == 1 and toks[0] in self.EXIT_WORDS:  # nut 1-tu
                kind = self.EXIT_WORDS[toks[0]]
            if kind is None or (want and kind != want):
                continue
            conf = rest[-1] if rest else 80
            hits.append({"word": word, "kind": kind, "center": (x, y),
                         "conf": conf})
        hits.sort(key=lambda h: -h["conf"])
        return hits

    def find_dismiss(self, img, reader=None):
        """Tim 1 nut THOAT/HUY tot nhat de bam (icon X/back HOAC chu Cancel/Exit).
        Uu tien: close-X (>=0.9) > back-arrow > chu Cancel/Exit > red-circle.
        Tra dict {'type','center':(x,y),'conf','via'} hoac None.
        Day la API chinh cho Agent: 'lam sao thoat man nay an toan'."""
        # 1. icon back/close bang template (dang tin nhat)
        close = self.find(img, kind="close")
        back = self.find(img, kind="back")
        if close and close[2] >= 0.9:
            return {"type": "close", "center": (close[0], close[1]),
                    "conf": close[2], "via": close[3]}
        if back:
            return {"type": "back", "center": (back[0], back[1]),
                    "conf": back[2], "via": back[3]}
        if close:
            return {"type": "close", "center": (close[0], close[1]),
                    "conf": close[2], "via": close[3]}
        # 2. nut chu Cancel/Exit/Skip (popup EN khong co icon)
        txt = self.find_text_button(img, reader=reader)
        # uu tien cancel > exit > skip (cancel an toan nhat de thoat popup)
        order = {"cancel": 0, "exit": 1, "skip": 2}
        txt.sort(key=lambda h: (order.get(h["kind"], 9), -h["conf"]))
        if txt:
            h = txt[0]
            return {"type": h["kind"], "center": h["center"],
                    "conf": h["conf"] / 100.0, "via": "ocr:" + h["word"]}
        return None


def build():
    cf = ControlFinder()
    by_kind = {}
    for name, d in cf.t.items():
        by_kind.setdefault(d["kind"], []).append(name)
    print(f"loaded {len(cf.t)} control templates (scaled to game):")
    for k, names in by_kind.items():
        print(f"  {k:6}: {len(names)} -> {names}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "test":
        img = cv2.imread(sys.argv[2])
        cf = ControlFinder()
        print("control buttons found:")
        for kind, hit in cf.find_all(img).items():
            cx, cy, sc, nm = hit
            print(f"  {kind:6}: ({cx},{cy}) score={sc:.2f} via {nm}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
