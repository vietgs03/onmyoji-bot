"""So sanh OAS page detector vs RustEye dhash tren nhieu frame live.

Chup N frame, voi moi frame:
- OAS detector -> page (ground-truth, template match ROI on dinh)
- RustEye dhash -> state_id + world label (fuzzy match hamming<=12)
Danh gia: OAS nhan duoc page bao nhieu %, RustEye match world bao nhieu %.
"""
import sys, time, os, subprocess
sys.path.insert(0, '/home/viethx/onmyoji-bot')
sys.path.insert(0, '/home/viethx/onmyoji-bot/scripts')
sys.path.insert(0, '/home/viethx/onmyoji-bot/eye-rs/tools')

from control_client import Controller
from oas_page_detector import OASPageDetector
import perception as P
import cv2

# world model de match
from onmyoji.adapters.world.world_model_adapter import WorldModelAdapter

det = OASPageDetector()
wm = WorldModelAdapter()
ctl = Controller()

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
print(f"=== OAS detector vs RustEye dhash ({N} frame) ===", flush=True)
print(f"OAS loaded {len(det.pages)} page\n", flush=True)

oas_hit = 0
wm_hit = 0
rows = []
for i in range(N):
    img = ctl.bgshot_raw()
    if img is None:
        continue
    # OAS
    oas_page = det.detect(img)
    # RustEye dhash + world match
    canon = cv2.resize(img, (1152, 679))
    dh = P.dhash(canon)
    sid = P.state_id(dh)
    matched = wm.match_state(dh, sid)
    label = wm.resolve_label(matched) if matched else None
    if oas_page:
        oas_hit += 1
    if label:
        wm_hit += 1
    rows.append((oas_page, label, sid[:8]))
    time.sleep(0.3)

ctl.close()
print(f"{'OAS page':28} {'WM label':20} {'dhash'}", flush=True)
for oas, lab, sid in rows:
    print(f"{str(oas):28} {str(lab):20} {sid}", flush=True)
print(f"\n=== TONG KET ===", flush=True)
print(f"  OAS nhan duoc page : {oas_hit}/{N} = {100*oas_hit/N:.0f}%", flush=True)
print(f"  RustEye match world: {wm_hit}/{N} = {100*wm_hit/N:.0f}%", flush=True)
print(f"  -> OAS detector {'manh hon' if oas_hit > wm_hit else 'bang/yeu hon'} dhash world model", flush=True)
