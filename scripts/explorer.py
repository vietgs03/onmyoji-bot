#!/usr/bin/env python3
"""
Autonomous explorer v2 - dung perception (CV detect nut) + world_model (graph).

Chien luoc:
  1. observe() -> sid hien tai. Neu moi -> luu screenshot.
  2. detect_buttons() -> danh sach nut UNG VIEN (CV, khong hardcode).
     Bo sung HOTSPOTS co dinh (footer 11 nut + cac goc) cho HOME -> chac chan.
  3. Chon nut CHUA THU diem cao nhat. Click. observe() lai.
     - neu doi state -> add_edge, luu, roi BACK ve (de thu tiep nut khac state cu).
     - neu khong doi -> mark tried, thu nut khac.
  4. Neu state hien tai het nut chua thu -> tim duong BFS ve HOME (hoac back tho).
  5. Dinh ky (moi N buoc) ve HOME de tranh lac sau.

Chay: .venv/bin/python scripts/explorer.py [budget]
"""
import os, sys, time, json
import cv2
from perception import (bgshot, bgclick, dhash, hamming, detect_buttons, W, H)
from world_model import WorldModel, SCREENS, EXP

OBS = os.path.join(EXP, "observations.jsonl")

# Hotspot entry-point co dinh (footer HOME + goc). Khong phai hardcode toan bo
# graph - chi seed cac diem chac chan de explorer khong bo sot menu chinh.
HOME_FOOTER = [(125, 632), (235, 632), (335, 632), (425, 632), (523, 632),
               (623, 632), (723, 632), (822, 632), (922, 632), (1022, 632),
               (608, 192),   # Explore
               (988, 245),   # Summon
               (1075, 185),  # Event
               (1033, 72), (1092, 72),  # mail/chat goc tren phai
               (936, 91),    # settings (da biet)
               (660, 277)]   # Town

BACK_CLICKS = [(1115, 78), (28, 68), (575, 640)]  # X cua so / back goc trai / vung duoi

def log(rec):
    with open(OBS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def candidate_buttons(img, sid, is_home):
    """Gop nut CV + hotspot (neu HOME). Tra list (x,y) sap theo uu tien."""
    btns = detect_buttons(img, suppress_center=is_home)
    pts = [(cx, cy) for cx, cy, w, h, s in btns if s >= 0.5]
    if is_home:
        pts = HOME_FOOTER + pts
    # khu trung gan nhau
    uniq = []
    for p in pts:
        if all(abs(p[0]-q[0]) > 20 or abs(p[1]-q[1]) > 20 for q in uniq):
            uniq.append(p)
    return uniq

def try_back(wm):
    """Bam cac nut back pho bien, tra sid sau khi back."""
    for bx, by in BACK_CLICKS:
        bgclick(bx, by); time.sleep(0.9)
    sid, _, _ = wm.observe()
    return sid

def goto_home(wm, home_sid, max_back=4):
    """Co gang ve HOME bang BFS; neu khong co duong, bam back nhieu lan."""
    sid, _, _ = wm.observe()
    if sid == home_sid:
        return sid
    path = wm.bfs_path(sid, home_sid)
    if path:
        for (x, y) in path:
            bgclick(x, y); time.sleep(1.2)
        sid, _, _ = wm.observe()
        if sid == home_sid:
            return sid
    for _ in range(max_back):
        sid = try_back(wm)
        if sid == home_sid:
            return sid
    return sid

def explore(budget=60, home_every=12):
    wm = WorldModel().load()
    # xac dinh HOME sid: observe lan dau (gia dinh dang o HOME sau goto)
    home_sid, isnew, img = wm.observe()
    if isnew:
        log({"event": "new_state", "state": home_sid, "step": -1})
    print(f"HOME = {home_sid}")

    transitions = 0
    for step in range(budget):
        sid, isnew, img = wm.observe()
        if img is None:
            print("  ! no shot"); break
        if isnew:
            log({"event": "new_state", "state": sid, "step": step})
            print(f"[{step}] NEW STATE {sid} (total {len(wm.states)})")

        is_home = (sid == home_sid)
        cands = candidate_buttons(img, sid, is_home)
        # chon nut chua thu
        target = next((p for p in cands if not wm.is_tried(sid, p)), None)

        if target is None:
            print(f"[{step}] {sid} het nut -> ve HOME")
            home_sid_now = goto_home(wm, home_sid)
            wm.save()
            continue

        x, y = target
        wm.mark_tried(sid, (x, y))
        bgclick(x, y); time.sleep(1.1)
        sid2, isnew2, img2 = wm.observe()

        if sid2 != sid:
            wm.add_edge(sid, (x, y), sid2)
            transitions += 1
            log({"event": "transition", "from": sid, "click": [x, y],
                 "to": sid2, "to_is_new": isnew2, "step": step})
            print(f"[{step}] {sid} --({x},{y})--> {sid2} {'NEW' if isnew2 else ''}")
            # back ve state cu (sid) de tiep tuc thu nut khac cua no.
            # Uu tien BFS sid2->sid; neu khong co thi bam back tho.
            path = wm.bfs_path(sid2, sid)
            if path:
                for (bx, by) in path:
                    bgclick(bx, by); time.sleep(1.0)
            else:
                try_back(wm)
        else:
            log({"event": "noop", "state": sid, "click": [x, y], "step": step})

        if (step + 1) % home_every == 0:
            goto_home(wm, home_sid)
        if (step + 1) % 10 == 0:
            wm.save()
            print(f"  ...saved. {wm.stats()}")

    wm.save()
    print(f"\nDONE. {wm.stats()} transitions={transitions}")
    print(f"world -> {os.path.join(EXP,'world.json')}")

if __name__ == "__main__":
    budget = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    explore(budget=budget)
