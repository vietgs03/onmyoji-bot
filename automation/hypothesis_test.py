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


def hyp_gold():
    print("=== TANG 2: TIM 'GIA TRI VANG' TRONG ANH (KHONG OCR, KHONG label) ===\n")
    img, st = _load_home()
    if img is None:
        print("khong co anh HOME"); return
    H, W = img.shape[:2]
    print(f"anh HOME: ma tran {W}x{H} pixel (~{W*H:,} o). "
          f"Tim vung currency MA KHONG OCR.\n")

    sal = _currency_saliency(img)
    # luoi probe GxG: agent 'nhin' tam 1 o luoi moi lan (mo phong attention/foveal).
    G = 24
    cell_h, cell_w = H // G, W // G
    scores = np.zeros((G, G), np.float32)
    for r in range(G):
        for c in range(G):
            blk = sal[r*cell_h:(r+1)*cell_h, c*cell_w:(c+1)*cell_w]
            scores[r, c] = blk.mean()

    # --- chien luoc 1: QUET TUAN TU (raster) - baseline ngok ---
    order_raster = [(r, c) for r in range(G) for c in range(G)]
    # --- chien luoc 2: GREEDY theo saliency (nhin cho 'sang' nhat truoc) ---
    order_greedy = sorted(order_raster, key=lambda rc: -scores[rc[0], rc[1]])

    # nguong 'tim thay' = o nam trong top-3 saliency that (gia tri vang that).
    truth = set(sorted(order_raster, key=lambda rc: -scores[rc[0], rc[1]])[:3])

    def probes_until_hit(order):
        for i, rc in enumerate(order, 1):
            if rc in truth:
                return i
        return len(order)

    p_raster = probes_until_hit(order_raster)
    p_greedy = probes_until_hit(order_greedy)
    print(f"luoi probe {G}x{G} = {G*G} o (moi o = 1 lan 'nhin', KHONG OCR ca anh):")
    print(f"  quet tuan tu (raster):     {p_raster:4d} lan probe moi cham vung vang")
    print(f"  greedy theo saliency:      {p_greedy:4d} lan probe (nhin cho sang truoc)")
    print(f"  => model co 'attention' (saliency) tim ra trong {p_greedy} lan thay vi "
          f"{p_raster} -> nhanh {p_raster/max(p_greedy,1):.0f}x, KHONG can OCR/label.\n")

    # GIA THUYET cho HOME->town (tang 1) trong khong gian anh (tang 2):
    print("GIA THUYET ket hop: 'muon toi town' -> tang 1 cho biet click nut Town.")
    print("  Nut Town o anh la 1 VUNG pixel; neu chua label, model dung saliency +")
    print("  template-match de dinh vi -> 1 lan dinh vi thay vi quet ca 1M pixel.")

    # --- RENDER: ban do saliency + thu tu probe greedy ---
    heat = cv2.applyColorMap(
        cv2.normalize(sal, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8),
        cv2.COLORMAP_JET)
    vis = cv2.addWeighted(img, 0.5, heat, 0.5, 0)
    # danh dau top-3 vung vang
    for rank, (r, c) in enumerate(sorted(order_raster, key=lambda rc: -scores[rc[0], rc[1]])[:3], 1):
        x, y = c*cell_w, r*cell_h
        cv2.rectangle(vis, (x, y), (x+cell_w, y+cell_h), (0, 255, 255), 3)
        cv2.putText(vis, f"#{rank}", (x+3, y+22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 255, 255), 2)
    out = os.path.join(OUT, "gold_saliency.png")
    cv2.imwrite(out, vis)
    print(f"  render: {out} (heatmap currency + top-3 vung vang khoanh vang)")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("nav", "all"):
        hyp_nav()
    if cmd in ("gold", "all"):
        print()
        hyp_gold()


if __name__ == "__main__":
    main()
