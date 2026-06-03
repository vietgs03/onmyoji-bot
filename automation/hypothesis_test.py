#!/usr/bin/env python3
"""
hypothesis_test.py - DAT GIA THUYET + render test case khi agent vao game (CHUA chay that).

Cau hoi cua user gop 2 TANG 'me cung':

  TANG 1 - ME CUNG DIEU HUONG (graph cac man): tu HOME muon toi 'town' qua bao nhieu
           buoc? Dung CHINH screen_graph (Dijkstra) tren knowledge that.

  TANG 2 - ME CUNG TRONG 1 BUC ANH (ma tran ~1000x1000 pixel): muon 'kiem tra gia tri
           vang' (so jade/coin tren HOME), agent phai TIM vung chua gia tri do trong
           ma tran pixel MA KHONG OCR / KHONG label truoc. Bao nhieu lan 'nhin' (probe)
           thi tim ra? -> day la search trong khong gian anh, danh gia model sau nay.

Muc tieu: dat GIA THUYET ve cach model xu ly + RENDER test case truc quan de kiem
  chung logic (offline, dung anh that world.json). Phuc vu danh gia model + daily.

Chay:
  .venv/bin/python automation/hypothesis_test.py nav      # tang 1: dem buoc dieu huong
  .venv/bin/python automation/hypothesis_test.py gold      # tang 2: tim gia tri vang trong anh
  .venv/bin/python automation/hypothesis_test.py all
"""
from __future__ import annotations

import os, sys, json
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from screen_graph import ScreenGraph, NODES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(ROOT, "exploration", "world.json")
OUT = os.path.join(ROOT, "research", "hypothesis")
os.makedirs(OUT, exist_ok=True)


# ======================================================================
# TANG 1: ME CUNG DIEU HUONG - tu HOME toi muc tieu qua bao nhieu buoc?
# ======================================================================
def hyp_nav():
    print("=== TANG 1: ME CUNG DIEU HUONG (graph man) - dem buoc Dijkstra ===\n")
    g = ScreenGraph()                                 # dung knowledge that (NODES)
    targets = ["town", "shop", "realm_raid", "duel", "mentor", "guild", "settings"]
    print(f"{'tu HOME toi':14} {'so buoc':>8}  duong di")
    for t in targets:
        p = g.path("HOME", t)
        n = len(p) - 1 if p else None
        print(f"{t:14} {str(n):>8}  {' -> '.join(p) if p else 'KHONG TOI DUOC'}")

    # GIA THUYET: agent o BAT KY dau (vd dang trong realm_raid) muon ve town.
    print("\nGIA THUYET: agent dang lac trong 'realm_raid', muon toi 'town':")
    p = g.path("realm_raid", "town")
    print(f"  duong: {' -> '.join(p)} ({len(p)-1} buoc, co di LUI ve exploration/HOME)")
    print("  => model: moi buoc doc man 1 lan (overlay? where? Dijkstra re-plan). "
          "Neu nut fail -> EdgeStats tang cost -> lan sau ne.")


# ======================================================================
# TANG 2: ME CUNG TRONG ANH - tim 'gia tri vang' KHONG OCR / KHONG label.
# Y tuong: coi anh 1000x1000 nhu ma tran. 'Gia tri vang' (currency) la vung co dac
# trung thi giac: chu so sang tren nen toi, gan ICON tien o thanh tren. Agent KHONG
# biet truoc o dau -> phai SEARCH. Ta mo phong 2 chien luoc va dem so lan 'probe'
# (nhin 1 o luoi) de tim ra -> chi phi nhan dien khi chua co label/OCR.
# ======================================================================
def _load_home():
    w = json.load(open(WORLD))
    for k, v in w["states"].items():
        if v["label"] == "HOME":
            return cv2.imread(os.path.join(ROOT, v["screenshot"])), v
    return None, None


def _currency_saliency(img):
    """Ban do 'kha nang la gia tri vang' tren tung pixel - KHONG OCR.
    Dac trung: chu so currency = text SANG (do tuong phan cao cuc bo) o NUA TREN man
    (thanh tien te). Tinh bang gradient (edge density) + uu tien vung tren."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.magnitude(gx, gy)
    edge = cv2.boxFilter(edge, -1, (25, 9))           # gom theo cum chu (ngang)
    H = img.shape[0]
    ramp = np.linspace(1.0, 0.15, H)[:, None]         # uu tien NUA TREN (thanh tien)
    return edge * ramp


# 3 loai currency tren top-bar HOME (xac nhan boi user, KHONG doan):
#   gold(vang)=14.62M | jade(hong ngoc)=32 | shushi=13.4K   (Sjade/ngoc tim o SHOP, khong o HOME)
# Moi currency = mot CON SO o thanh tren (y<70). Ta dinh vi bang OCR THAT (vi tri so)
# roi lay ICON ngay ben trai so -> doc MAU de phan biet -> mark dung tung loai.
CUR_ORDER = ["gold", "jade", "shushi"]   # trai -> phai tren top-bar
CUR_VI = {"gold": "VANG (gold)", "jade": "HONG NGOC (jade)", "shushi": "SHUSHI"}
CUR_BGR = {"gold": (0, 215, 255), "jade": (180, 105, 255), "shushi": (60, 180, 75)}


def _find_currencies(img):
    """Dinh vi 3 currency tren top-bar HOME bang OCR THAT (khong doan toa do).
    Tra list dict {name, num_box, value, icon_center, hue}. Sap trai->phai."""
    sys.path.insert(0, os.path.join(ROOT, "ml"))
    from ocr import ocr_words
    words = ocr_words(img, min_conf=40)
    # con so currency: nam o thanh tren (y<70), la chuoi co chu so (vd 14.62M / 32 / 13.4K)
    nums = []
    for t, (x, y, w, h), cf in words:
        if y >= 70:
            continue
        s = t.replace(",", "").replace(".", "")
        if any(ch.isdigit() for ch in t) and not s.isalpha() and len(t) <= 8:
            # bo gio/ngay (vd 'Tue.13:09') va toa do nhieu dau ':'
            if ":" in t or t.count("d") and t[:-1].isdigit():
                continue
            nums.append((x, y, w, h, t))
    nums.sort(key=lambda z: z[0])           # trai -> phai
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    out = []
    for (x, y, w, h, t) in nums[:3]:         # 3 currency dau tien
        # icon nam NGAY BEN TRAI con so; n4 so ngan (vd '32') thi icon van ~24px cao.
        iw = max(26, h)
        ix1 = x - 3
        ix0 = max(0, ix1 - iw)
        sub = hsv[max(0, y-6):y+h+6, ix0:ix1]
        m = (sub[:, :, 1] > 50) & (sub[:, :, 2] > 60)
        hmode = -1
        if m.sum() >= 3:
            hu = sub[:, :, 0][m].astype(int)
            hmode = int(np.bincount(hu, minlength=180).argmax())
        out.append({"value": t, "num_box": (x, y, w, h),
                    "icon_center": ((ix0+ix1)//2, y+h//2), "hue": hmode})
    return out


def hyp_gold():
    print("=== TANG 2: DINH VI 3 CURRENCY tren HOME (gold/jade/shushi) ===\n")
    img, st = _load_home()
    if img is None:
        print("khong co anh HOME"); return
    H, W = img.shape[:2]
    print(f"anh HOME: ma tran {W}x{H} pixel. Top-bar co 3 currency (trai->phai):")
    print("  gold(vang)=14.62M | jade(hong ngoc)=32 | shushi=13.4K  "
          "[Sjade/ngoc tim o SHOP, KHONG o HOME]\n")

    cur = _find_currencies(img)
    if len(cur) < 3:
        print(f"  ! chi dinh vi duoc {len(cur)}/3 con so o top-bar"); 
    # gan ten theo THU TU trai->phai (da xac nhan boi user)
    for i, c in enumerate(cur[:3]):
        c["name"] = CUR_ORDER[i]

    print("ket qua dinh vi (OCR that, KHONG doan toa do):")
    for c in cur[:3]:
        nm = c["name"]; bx = c["num_box"]; ic = c["icon_center"]
        print(f"  {CUR_VI[nm]:20} value={c['value']:>8}  so@({bx[0]},{bx[1]})  "
              f"icon@{ic} hue={c['hue']}")
    print()

    # --- phan biet bang MAU icon (hue) - de verify 3 currency KHAC nhau ---
    print("phan biet bang MAU icon (hue 0-180, -1=khong ro):")
    for c in cur[:3]:
        h = c["hue"]
        col = ("?" if h < 0 else "DO/HONG" if (h < 13 or h > 165) else "CAM/VANG"
               if h < 40 else "XANH-LA" if h < 85 else "XANH-DUONG" if h < 125
               else "TIM")
        print(f"  {c['name']:7} hue={h:3d} -> {col}")
    print()

    # --- RENDER: mark DUNG tung currency rieng ---
    vis = img.copy()
    for c in cur[:3]:
        nm = c["name"]; col = CUR_BGR[nm]
        x, y, w, h = c["num_box"]; ic = c["icon_center"]
        # khoanh con so
        cv2.rectangle(vis, (x-2, y-2), (x+w+2, y+h+2), col, 2)
        # khoanh icon
        cv2.circle(vis, ic, max(14, h//2+2), col, 2)
        # nhan ten currency (phia duoi)
        cv2.putText(vis, f"{nm}={c['value']}", (min(ic[0]-30, x-30), y+h+22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2, cv2.LINE_AA)
    out = os.path.join(OUT, "currencies_home.png")
    cv2.imwrite(out, vis)
    # ban crop top-bar phong to de doi chieu
    bar = img[34:80, 430:940]
    cv2.imwrite(os.path.join(OUT, "currencies_topbar_zoom.png"),
                cv2.resize(bar, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
    print(f"  render: {out} (mark RIENG tung currency: "
          f"gold=vang, jade=tim-hong, shushi=xanh)")
    print(f"  render: {os.path.join(OUT,'currencies_topbar_zoom.png')} (top-bar phong to)")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("nav", "all"):
        hyp_nav()
    if cmd in ("gold", "all"):
        print()
        hyp_gold()


if __name__ == "__main__":
    main()
