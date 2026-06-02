#!/usr/bin/env python3
"""
Autonomous UI explorer cho Onmyoji.

Y tuong: bot tu "mo" game - tai moi page, no thu click vao cac diem CHUA THU
(grid hoac cac vung interactive), so sanh man hinh truoc/sau de biet:
  - click do co lam DOI MAN HINH khong (transition) hay khong (no-op).
  - neu doi -> luu screenshot moi + ghi lai "tu <page> click (x,y) -> man hinh moi".
  - tu dong tim duong VE node goc (HOME) de tiep tuc kham pha cho khac.

Output:
  exploration/observations.jsonl   # moi dong 1 quan sat (state-hash, click, ket qua)
  exploration/screens/<hash>.png   # anh moi man hinh la
  exploration/frontier.json        # cac (page_hash, click) chua thu / da thu

Man hinh "moi" duoc dinh danh bang perceptual-ish hash (dHash) cua anh.
Con NGUOI/AI (toi) doc observations + screens de DAT TEN va MO TA chuc nang.
"""
import json, os, subprocess, sys, time, hashlib
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "scripts", "onmyoji.sh")
EXP = os.path.join(ROOT, "exploration")
SCREENS = os.path.join(EXP, "screens")
OBS = os.path.join(EXP, "observations.jsonl")
os.makedirs(SCREENS, exist_ok=True)

W, H = 1152, 679

def bgshot():
    out = subprocess.run([CLI, "bgshot", "_explore_tmp"], capture_output=True, text=True)
    p = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else None
    return cv2.imread(p) if p else None

def bgclick(x, y):
    subprocess.run([CLI, "bgclick", str(int(x)), str(int(y))], capture_output=True, text=True)

def dhash(img, hash_size=16):
    """Perceptual hash tren VUNG TINH (bo chat bar tren + animation giua + nhan vat).
    Onmyoji co chat bar (~y 100-125) va nhan vat dong o giua -> gay nhieu.
    Ta hash phan KHUNG/UI (vien trai, phai, footer text) bang cach mask vung dong."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # mask: zero hoa vung chat bar va vung giua-tren (nhieu dong nhat)
    g = g.copy()
    g[95:130, 350:1000] = 0     # chat bar
    g[150:480, 280:900] = 0     # vung nhan vat dong o san nha
    g = cv2.resize(g, (hash_size + 1, hash_size))
    diff = g[:, 1:] > g[:, :-1]
    return "".join("1" if v else "0" for v in diff.flatten())

def hamming(a, b):
    return sum(c1 != c2 for c1, c2 in zip(a, b))

def state_id(img):
    """Tra ve hash ngan lam ID man hinh."""
    return hashlib.md5(dhash(img).encode()).hexdigest()[:12]

def is_new_state(h, known, threshold=18):
    """So voi cac dhash da biet; neu khac biet du lon -> man hinh moi."""
    for kh in known:
        if hamming(h, kh) <= threshold:
            return False, kh
    return True, None

def log_obs(rec):
    with open(OBS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def grid_points(cols=8, rows=6, margin_top=40, margin_bot=20):
    """Sinh luoi diem click phu man hinh (tranh vien title bar)."""
    pts = []
    usable_h = H - margin_top - margin_bot
    for r in range(rows):
        for c in range(cols):
            x = int((c + 0.5) * W / cols)
            y = int(margin_top + (r + 0.5) * usable_h / rows)
            pts.append((x, y))
    return pts

def explore(budget=40, back_clicks=((1115, 78), (28, 68))):
    """Vong lap kham pha co he thong.
    - Moi 'state' duoc dinh danh on dinh bang canonical hash (gom man hinh gan giong).
    - Tai state hien tai, thu diem grid CHUA THU; sau moi click ghi nhan transition;
      roi BACK ve de tiep tuc thu diem khac cua CUNG state (khong bi lac sang nhanh sau).
    """
    # canonical states: list (hash, id) - dai dien on dinh
    canon = []  # [(dhash, sid)]
    def canonicalize(dh, img):
        for kh, sid in canon:
            if hamming(dh, kh) <= 14:
                return sid, False
        sid = hashlib.md5(dh.encode()).hexdigest()[:10]
        canon.append((dh, sid))
        cv2.imwrite(os.path.join(SCREENS, f"{sid}.png"), img)
        return sid, True

    # nap canon tu screens da co (de chay tiep, khong lam lai)
    for fn in sorted(os.listdir(SCREENS)):
        if fn.endswith(".png"):
            im = cv2.imread(os.path.join(SCREENS, fn))
            if im is not None:
                canon.append((dhash(im), fn[:-4]))

    visited_clicks = set()
    transitions = 0

    for step in range(budget):
        before = bgshot()
        if before is None:
            print("  ! no screenshot"); break
        dh = dhash(before)
        sid, isnew = canonicalize(dh, before)
        if isnew:
            print(f"[{step}] NEW STATE {sid} (total {len(canon)})")
            log_obs({"event": "new_state", "state": sid, "step": step})

        # chon diem grid chua thu o state nay
        target = None
        for (x, y) in grid_points():
            if (sid, x, y) not in visited_clicks:
                target = (x, y); break
        if target is None:
            print(f"[{step}] state {sid} het diem -> back")
            for bx, by in back_clicks:
                bgclick(bx, by); time.sleep(1.0)
            continue

        x, y = target
        visited_clicks.add((sid, x, y))
        bgclick(x, y)
        time.sleep(1.3)
        after = bgshot()
        if after is None:
            continue
        dh2 = dhash(after)
        if hamming(dh, dh2) > 14:
            sid2, isnew2 = canonicalize(dh2, after)
            transitions += 1
            log_obs({"event": "transition", "from": sid, "click": [x, y],
                     "to": sid2, "to_is_new": isnew2, "step": step})
            print(f"[{step}] {sid} --click({x},{y})--> {sid2} {'(NEW)' if isnew2 else ''}")
            # back ve state cu de tiep tuc thu diem khac cua no
            for bx, by in back_clicks:
                bgclick(bx, by); time.sleep(1.0)
        else:
            log_obs({"event": "noop", "state": sid, "click": [x, y], "step": step})

    print(f"\nDone. canonical_states={len(canon)} transitions={transitions}")
    print(f"Observations: {OBS}")
    print(f"Screens: {SCREENS}/")

if __name__ == "__main__":
    budget = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    explore(budget=budget)
