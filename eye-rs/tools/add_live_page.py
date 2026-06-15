#!/usr/bin/env python3
"""add_live_page.py - Them 1 page template tu frame LIVE vao manifest (eye-rs).

Vi sao: OAS template (phien ban game cu/do phan giai khac) co the KHONG fire tren
live (vd page_town -0.15). Tool nay crop landmark tu chinh frame live cua game
hien tai -> dam bao match cao. Dung cho man DONG (Town, Exploration...) de page
detector neo on dinh thay vi dhash troi.

Cach dung:
    # chup frame hien tai (dang o man can them)
    python3 add_live_page.py shoot /tmp/cur.png
    # them page: ten, roi landmark [x y w h] (vung TINH + dac trung man do)
    python3 add_live_page.py add /tmp/cur.png page_town_live "x y w h" [threshold]

Sau do chay gen_pages_embed.py + build lai.
"""
import sys, os, json
import cv2

ROOT = "/home/viethx/onmyoji-bot/eye-rs"
ASSETS = os.path.join(ROOT, "assets/pages")
MANIFEST = os.path.join(ASSETS, "manifest.json")


def shoot(out):
    sys.path.insert(0, "/home/viethx/onmyoji-bot/scripts")
    from control_client import Controller
    c = Controller()
    img = c.bgshot_raw()
    c.close()
    if img is None:
        print("grab fail"); sys.exit(1)
    cv2.imwrite(out, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    print("saved", out, img.shape)


def add(src, page, roi_str, threshold=0.8):
    x, y, w, h = (int(v) for v in roi_str.split())
    img = cv2.imread(src)  # BGR
    if img is None:
        print("khong doc duoc", src); sys.exit(1)
    H, W = img.shape[:2]
    if (W, H) != (1136, 640):
        print(f"CANH BAO: anh {W}x{H} != 1136x640 (game client). Co the lech ROI.")
    crop = img[y:y+h, x:x+w]
    # luu template TRUE-RGB (khop frame Rust RGB) -> save PNG RGB
    fn = f"{page}.png"
    cv2.imwrite(os.path.join(ASSETS, fn), crop)  # BGR file; gen doc lai
    # cap nhat manifest
    m = json.load(open(MANIFEST, encoding="utf-8"))
    # bo entry cu cung ten (idempotent)
    m["pages"] = [p for p in m["pages"] if p["page"] != page]
    m["pages"].append({
        "page": page,
        "asset": f"LIVE_{page.upper()}",
        "roi": [x, y, w, h],
        "threshold": float(threshold),
        "tmpl_w": w,
        "tmpl_h": h,
        "file": fn,
    })
    json.dump(m, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"added {page} roi=[{x},{y},{w},{h}] thr={threshold} -> {fn} ({w}x{h})")
    print(f"total pages: {len(m['pages'])}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "shoot":
        shoot(sys.argv[2])
    elif cmd == "add":
        add(sys.argv[2], sys.argv[3], sys.argv[4],
            sys.argv[5] if len(sys.argv) > 5 else 0.8)
    else:
        print(__doc__)
