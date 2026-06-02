#!/usr/bin/env python3
"""Cat 1 vung tu screenshot lam template anchor.
  ./cut_asset.py <src.png> <PAGE> <asset_name> <x> <y> <w> <h>
Luu vao assets/<PAGE>/<asset_name>.png va in ra roi de dien yaml.
"""
import cv2, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src, page, name, x, y, w, h = sys.argv[1], sys.argv[2], sys.argv[3], *map(int, sys.argv[4:8])
img = cv2.imread(src)
crop = img[y:y+h, x:x+w]
out_dir = os.path.join(ROOT, "assets", page)
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, f"{name}.png")
cv2.imwrite(out, crop)
# roi_back = vung tim, lay rong hon mot chut de chiu sai lech
rx, ry = max(0, x-15), max(0, y-15)
rw, rh = w+30, h+30
print(f"saved {out} ({w}x{h})")
print(f"  anchor yaml:")
print(f"    - asset: {page}/{name}.png")
print(f"      roi: [{rx}, {ry}, {rw}, {rh}]")
print(f"      threshold: 0.85")
