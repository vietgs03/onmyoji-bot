"""extract_oas_pages.py - Trich xuat asset page cua OAS -> template scaled + manifest.

Doc OAS GameUi assets + page.py, scale moi template/ROI tu 1280x720 xuong
1136x640 (ti le 0.888), luu PNG scaled + manifest JSON cho eye-core nap.

Output (eye-rs/assets/pages/):
  <page>.png   = template da scale (RGB)
  manifest.json = [{page, asset, roi:[x,y,w,h], threshold, file}]

Chay: python3 eye-rs/tools/extract_oas_pages.py
"""
import os
import sys
import json
import cv2

sys.path.insert(0, "/home/viethx/onmyoji-bot/eye-rs/tools")
from oas_page_detector import OASPageDetector, SX, SY, GAME_W, GAME_H

OUT_DIR = "/home/viethx/onmyoji-bot/eye-rs/assets/pages"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    det = OASPageDetector()
    manifest = []
    for page, (rb, tmpl, thr, asset) in sorted(det.pages.items()):
        # tmpl la BGR (cv2.imread OAS asset). Muon file PNG co noi dung RGB THAT
        # = giong frame RGB ben Rust. cv2.imwrite(arr) coi arr la BGR va ghi file
        # voi RGB = arr-dao-kenh. Nen imwrite(tmpl_bgr) -> file RGB that = dung.
        # (Rust decode_png tra RGB that -> khop frame Rust RGB.)
        fn = f"{page}.png"
        cv2.imwrite(os.path.join(OUT_DIR, fn), tmpl)
        manifest.append({
            "page": page,
            "asset": asset,
            "roi": [int(v) for v in rb],   # [x,y,w,h] trong khong gian 1136x640
            "threshold": float(thr),
            "tmpl_w": int(tmpl.shape[1]),
            "tmpl_h": int(tmpl.shape[0]),
            "file": fn,
        })
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({
            "game_w": GAME_W, "game_h": GAME_H,
            "scale_x": SX, "scale_y": SY,
            "pages": manifest,
        }, f, indent=2, ensure_ascii=False)
    print(f"da trich {len(manifest)} page -> {OUT_DIR}")
    print(f"  vd: {manifest[0]['page']} roi={manifest[0]['roi']} thr={manifest[0]['threshold']}")


if __name__ == "__main__":
    main()
