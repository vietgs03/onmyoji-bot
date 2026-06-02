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
from perception import (bgshot, bgclick, dhash, hamming, detect_buttons,
                        is_loading, find_close_button, W, H)
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

BACK_CLICKS = [(1015, 95), (990, 118), (45, 62), (28, 68)]
# X popup giua-tren / back goc tren trai. KHONG bam (1115,78)=X cua so game (tat game!)

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
    """Dong popup/back ve. Uu tien tim nut X (CV) -> roi BACK_CLICKS co dinh."""
    img = bgshot()
    if img is not None:
        xb = find_close_button(img)
        if xb:
            bgclick(xb[0], xb[1]); time.sleep(1.0)
    for bx, by in BACK_CLICKS:
        bgclick(bx, by); time.sleep(0.8)
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
    # van lac -> escape manh: dung graph.py (anchor HOME) de ve
    import subprocess
    gp = os.path.join(os.path.dirname(__file__), "graph.py")
    py = sys.executable
    subprocess.run([py, gp, "goto", "HOME"], capture_output=True, text=True)
    time.sleep(1.5)
    sid, _, _ = wm.observe()
    return sid

def explore(budget=60, home_every=20, max_depth=4):
    """DFS sau: vao state moi -> kham pha het no truoc khi back.
    - Khong back ngay sau transition (de di SAU vao menu con).
    - Chi back khi state hien tai het nut chua thu.
    - Bo qua khong khai thac state 'Loading' (transient)."""
    wm = WorldModel().load()
    # DAM BAO o HOME truoc khi bat dau: dong popup + goto HOME (anchor).
    import subprocess
    for _ in range(3):
        im = bgshot()
        if im is not None:
            xb = find_close_button(im)
            if xb:
                bgclick(*xb); time.sleep(1.0)
        bgclick(45, 55); time.sleep(0.8); bgclick(28, 68); time.sleep(0.8)
    gp = os.path.join(os.path.dirname(__file__), "graph.py")
    subprocess.run([sys.executable, gp, "goto", "HOME"], capture_output=True, text=True)
    time.sleep(1.5)
    home_sid, isnew, img = wm.observe()
    if isnew:
        log({"event": "new_state", "state": home_sid, "step": -1})
    print(f"HOME = {home_sid}")

    transitions = 0
    stuck = 0  # dem so buoc lien tiep khong sinh transition moi -> chong ket

    for step in range(budget):
        sid, isnew, img = wm.observe()
        if img is None:
            print("  ! no shot"); break
        # neu dang loading -> doi cho qua, observe lai (toi da 3 lan)
        waits = 0
        while is_loading(img) and waits < 3:
            time.sleep(1.5); img = bgshot(); waits += 1
        if img is not None and is_loading(img):
            print(f"[{step}] van loading -> back")
            try_back(wm); continue
        sid, isnew, img = wm.observe()  # re-observe sau khi loading xong
        if isnew:
            log({"event": "new_state", "state": sid, "step": step})
            print(f"[{step}] NEW STATE {sid} (total {len(wm.states)})")

        # do sau = khoang cach BFS tu HOME toi state nay (theo graph da hoc)
        path_from_home = wm.bfs_path(home_sid, sid)
        cur_depth = len(path_from_home) if path_from_home is not None else 99

        lbl = wm.states[sid].get("label")
        if lbl == "Loading":
            try_back(wm); continue
        if cur_depth >= max_depth:
            print(f"[{step}] {sid} depth={cur_depth} >= {max_depth} -> ve HOME")
            goto_home(wm, home_sid); stuck = 0
            continue

        is_home = (sid == home_sid)
        cands = candidate_buttons(img, sid, is_home)
        target = next((p for p in cands if not wm.is_tried(sid, p)), None)

        if target is None:
            if is_home:
                print(f"[{step}] HOME het nut -> xong"); break
            print(f"[{step}] {sid} het nut -> ve HOME tim cho khac")
            goto_home(wm, home_sid); stuck = 0
            continue

        x, y = target
        wm.mark_tried(sid, (x, y))
        bgclick(x, y); time.sleep(1.1)
        sid2, isnew2, img2 = wm.observe()

        if sid2 != sid:
            wm.add_edge(sid, (x, y), sid2)
            transitions += 1
            stuck = 0
            log({"event": "transition", "from": sid, "click": [x, y],
                 "to": sid2, "to_is_new": isnew2, "step": step})
            print(f"[{step}] {sid} --({x},{y})--> {sid2} {'NEW' if isnew2 else ''}")
        else:
            stuck += 1
            log({"event": "noop", "state": sid, "click": [x, y], "step": step})

        # chong ket: neu nhieu buoc khong co transition -> ve HOME
        if stuck >= 8:
            print(f"[{step}] stuck={stuck} -> ve HOME")
            goto_home(wm, home_sid); stuck = 0
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
