#!/usr/bin/env python3
"""
Perception layer cho Onmyoji bot.

Cung cap:
  - bgshot()      : chup man hinh game (background, khong can foreground)
  - bgclick(x,y)  : click background (PostMessage)
  - dhash(img)    : perceptual hash tren VUNG TINH -> state ID on dinh
  - hamming(a,b)
  - detect_buttons(img) : tim cac vung NHIEU KHA NANG la nut (CV, khong hardcode):
        + icon tron quanh ria (Hough circles)
        + cum text/icon o footer + cac panel (contour tren anh edge/saturation)
    Tra ve list (x, y, w, h, score) da gop trung lap (NMS).

Khong hardcode toa do nut cu the -> day la diem khac OAS (template thu cong).
"""
import subprocess, os, hashlib
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "scripts", "onmyoji.sh")

W, H = 1152, 679

# Persistent controller (PowerShell server qua pipe) - nhanh hon spawn moi lan.
# Khoi tao lazy de cac script khong dung control van import duoc.
_CTL = None
def _ctl():
    global _CTL
    if _CTL is None:
        from control_client import Controller
        _CTL = Controller()
    return _CTL

# vung dong cua HOME (san nha): chat bar + nhan vat. Dung de mask khi hash.
DYNAMIC_MASKS = [
    (350, 95, 1000, 130),   # chat bar tren
    (280, 150, 900, 480),   # nhan vat dong giua san
]


def bgshot(name="_perc_tmp"):
    return _ctl().bgshot()


def bgclick(x, y):
    _ctl().bgclick(x, y)


# Cac VUNG TINH dung de tinh state-hash. Tranh nhan vat dong + cay + chat.
# Moi vung (x0,y0,x1,y1) duoc hash rieng roi noi lai -> on dinh voi animation.
STABLE_REGIONS = [
    (0,   55, 1152, 95),    # currency bar tren (vang/ve/sushi)
    (980, 130, 1130, 560),  # cot icon modes ben phai (Event/Summon/clocks)
    (0,   600, 1152, 660),  # footer text row (Collection/Team/Guild...)
    (0,   95,  280, 600),   # ria trai (avatar, seal, ...) - it dong hon giua
]


def dhash(img, per_region=4):
    """State-hash on dinh: hash tung VUNG TINH roi noi lai.
    Bo qua hoan toan vung nhan vat dong o giua + cay sakura."""
    if img is None or img.size == 0 or img.shape[0] < H or img.shape[1] < W:
        return None
    parts = []
    for x0, y0, x1, y1 in STABLE_REGIONS:
        crop = img[y0:y1, x0:x1]
        if crop.size == 0:
            return None
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, (per_region + 1, per_region))
        diff = g[:, 1:] > g[:, :-1]
        parts.append("".join("1" if v else "0" for v in diff.flatten()))
    return "".join(parts)


def is_loading(img, dark_thr=45, dark_ratio=0.7):
    """Heuristic: man hinh loading/chuyen canh thuong RAT TOI (phan lon pixel toi).
    Tra True neu >dark_ratio pixel co do sang < dark_thr."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dark = (g < dark_thr).mean()
    return dark > dark_ratio


def find_close_button(img):
    """Tim nut X (dong popup) - dac trung Onmyoji: vong tron MAU DO/HONG hoac X TRANG.
    Tra (cx, cy) hoac None. Uu tien o nua tren man hinh (popup thuong co X tren-phai)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # mau do/hong: H quanh 0 va 170-180, S cao, V kha cao
    m1 = cv2.inRange(hsv, (0, 90, 90), (12, 255, 255))
    m2 = cv2.inRange(hsv, (160, 90, 90), (180, 255, 255))
    mask = cv2.morphologyEx(m1 | m2, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        # nut X: gan vuong, kich thuoc vua, KHONG o ria ngoai cung (do la X cua so game)
        if not (500 < area < 9000):
            continue
        if not (0.6 < w / max(h, 1) < 1.7):
            continue
        cx, cy = x + w // 2, y + h // 2
        # X popup thuong o GOC TREN-PHAI panel: cx 800..1110, cy 50..180
        if not (800 <= cx <= 1110 and 50 <= cy <= 180):
            continue
        # uu tien gan (1000,110)
        score = -((cx - 1000) ** 2 + (cy - 110) ** 2)
        if best is None or score > best[0]:
            best = (score, cx, cy)
    if best:
        return (best[1], best[2])
    # fallback: X TRANG/SANG nho o goc tren-phai (vd man character showcase)
    # chi nhan vung rat hep gan goc (y 50..80) de tranh nham icon thu/chat tren HOME
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    roi = gray[48:82, 1078:1122]
    _, bw = cv2.threshold(roi, 195, 255, cv2.THRESH_BINARY)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts2, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts2:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if 80 < area < 1200 and 0.5 < w / max(h, 1) < 2.0:
            return (1078 + x + w // 2, 48 + y + h // 2)
    return None


def hamming(a, b):
    return sum(c1 != c2 for c1, c2 in zip(a, b))


def state_id(dh):
    return hashlib.md5(dh.encode()).hexdigest()[:10]


def _nms(boxes, iou_thr=0.3):
    """Non-max suppression don gian theo score."""
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: -b[4])
    keep = []
    def iou(a, b):
        ax, ay, aw, ah = a[:4]; bx, by, bw, bh = b[:4]
        x1, y1 = max(ax, bx), max(ay, by)
        x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        if inter == 0:
            return 0.0
        return inter / (aw * ah + bw * bh - inter)
    for b in boxes:
        if all(iou(b, k) < iou_thr for k in keep):
            keep.append(b)
    return keep


# Vung KHO co nut tren HOME (nhan vat dong giua + cay sakura ben trai-tren).
# Box CV roi vao day thuong la false-positive -> ha diem nhung khong loai han
# (vi mot so UI con co nut o giua). Chi ap dung heuristic khi o HOME-like.
NOISE_REGION = (250, 130, 880, 540)  # x0,y0,x1,y1 vung nhan vat san nha


def detect_buttons(img, suppress_center=False):
    """Tim cac ung vien NUT. Tra list (cx, cy, w, h, score).
    suppress_center=True: ha diem cac box roi vao vung nhan vat (dung cho HOME)."""
    cands = []

    # 1) icon tron (cac nut ria man hinh: chat, mail, settings, modes...)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.medianBlur(gray, 5)
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=30,
                               param1=120, param2=40, minRadius=14, maxRadius=55)
    if circles is not None:
        for cx, cy, r in np.around(circles)[0].astype(int):
            cands.append((int(cx - r), int(cy - r), int(2 * r), int(2 * r), 1.0))

    # 2) vung co man do bao hoa cao (nut mau cam/do dac trung Onmyoji)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    _, th = cv2.threshold(sat, 120, 255, cv2.THRESH_BINARY)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if 900 < area < 60000 and 0.25 < w / max(h, 1) < 6:
            cands.append((x, y, w, h, 0.7))

    boxes = _nms(cands, iou_thr=0.35)
    out = []
    for x, y, w, h, s in boxes:
        cx, cy = x + w // 2, y + h // 2
        if not (0 <= cx < W and 0 <= cy < H):
            continue
        if suppress_center:
            nx0, ny0, nx1, ny1 = NOISE_REGION
            if nx0 <= cx <= nx1 and ny0 <= cy <= ny1:
                s *= 0.3
        out.append((cx, cy, w, h, round(s, 2)))
    # sap xep theo score giam dan
    out.sort(key=lambda b: -b[4])
    return out


if __name__ == "__main__":
    img = bgshot()
    if img is None:
        print("no shot"); raise SystemExit(1)
    btns = detect_buttons(img)
    print(f"state_id={state_id(dhash(img))}  buttons={len(btns)}")
    vis = img.copy()
    for cx, cy, w, h, s in btns:
        cv2.rectangle(vis, (cx - w // 2, cy - h // 2), (cx + w // 2, cy + h // 2),
                      (0, 255, 0), 2)
        cv2.circle(vis, (cx, cy), 3, (0, 0, 255), -1)
    out = os.path.join(ROOT, "exploration", "_buttons_vis.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cv2.imwrite(out, vis)
    print(f"vis -> {out}")


def detect_red_badges(img, min_area=25, max_area=900, max_wh=40, ui_only=True):
    """Tim cac BADGE DO (chấm đỏ thông báo) tren man - dau hieu "co the claim/nhan".
    Tra list (cx, cy, area) sap xep area giam. Dung HSV 2 dai hue do, S/V cao.

    Badge do la dau hieu PHO QUAT trong game: mail moi, nhiem vu xong, qua chua nhan...
    -> task claim chi viec tap vao gan badge va xu ly popup hien ra.

    ui_only=True: BO vung trung tam (nhan vat dong + cay sakura + ribbon do) de tranh
    false-positive. Badge that nam tren ICON ria man (mail goc phai, cot mode phai,
    avatar/seal goc trai, footer). Vung loai = giua-duoi noi nhan vat dung."""
    if img is None or img.size == 0:
        return []
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m1 = cv2.inRange(hsv, (0, 120, 120), (10, 255, 255))
    m2 = cv2.inRange(hsv, (170, 120, 120), (180, 255, 255))
    mask = m1 | m2
    if ui_only:
        # zero-hoa vung TRUNG TAM dong (nhan vat/cay/ribbon) - khong phai badge UI.
        # giu: top bar (y<55 mail/currency), cot phai (x>970), ria trai hep (x<70),
        #      footer (y>600). Bo phan con lai o giua.
        h, w = mask.shape
        keep = np.zeros_like(mask)
        keep[0:55, :] = 1                  # top bar (mail, currency badge)
        keep[:, 970:] = 1                  # cot mode ben phai
        keep[:, :70] = 1                   # ria trai (avatar/seal it dong)
        keep[600:, :] = 1                  # footer
        mask = mask * keep
    n, _, stats, cent = cv2.connectedComponentsWithStats(mask, 8)
    spots = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if (min_area <= area <= max_area and w <= max_wh and h <= max_wh
                and 0.4 <= w / max(h, 1) <= 2.5):
            spots.append((int(cent[i][0]), int(cent[i][1]), int(area)))
    spots.sort(key=lambda s: -s[2])
    return spots


def detect_courtyard_dolls(img, min_item_px=60, merge_r=58):
    """Tim cac DOLL DANG CAM QUA trong san HOME (courtyard) - khong hardcode toa do.

    Theo de bai cua user: tren HOME co cac con doll than TRANG nho dung trong san,
    moi con CAM 1 vat pham mau (hop go nau 'Lot' = diem danh, the do = task/clear
    daily). Click vao doll -> mo man nhan qua tuong ung. Cac doll DOI CHO moi ngay
    nen KHONG the hardcode -> phai NHAN DIEN bang dac trung hinh anh.

    Dac trung: blob TRANG (S thap, V cao) o vung san (y 380-585, x 150-1000), kich
    thuoc nho, GAN do co dom mau (nau go / do) = vat pham doll dang cam.

    Tra list (cx, cy, area, item_px) sap theo item_px giam (nhieu mau = qua ro hon).
    Co the co false-positive (nhan vat nguoi choi) nhung luong explore se click thu
    va ghi 'no-change' -> tu loc."""
    if img is None or img.size == 0:
        return []
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    wood = cv2.inRange(hsv, (8, 80, 80), (28, 255, 230))         # hop go/cam
    red1 = cv2.inRange(hsv, (0, 110, 90), (10, 255, 255))
    red2 = cv2.inRange(hsv, (168, 110, 90), (180, 255, 255))
    item = wood | red1 | red2
    white = cv2.inRange(hsv, (0, 0, 165), (180, 60, 255))        # than doll trang
    H, W = white.shape
    zone = np.zeros_like(white)
    zone[380:585, 150:1000] = 1                                  # vung san, bo footer
    white = white * zone
    n, _, stats, cent = cv2.connectedComponentsWithStats(white, 8)
    raw = []
    for i in range(1, n):
        x, y, w, h, ar = stats[i]
        if (200 <= ar <= 2500 and 14 <= w <= 70 and 16 <= h <= 80
                and 0.4 <= w / max(h, 1) <= 1.4):
            cx, cy = int(cent[i][0]), int(cent[i][1])
            x0, x1 = max(0, x - 10), min(W, x + w + 12)
            y0, y1 = max(0, y - 5), min(H, y + h + 18)
            ic = int(item[y0:y1, x0:x1].sum() / 255)
            if ic >= min_item_px:
                raw.append((cx, cy, int(ar), ic))
    raw.sort(key=lambda r: -r[2])                                # blob lon truoc
    dolls = []
    for cx, cy, ar, ic in raw:                                   # gop cum gan nhau
        if all(abs(cx - dx) > merge_r or abs(cy - dy) > merge_r
               for dx, dy, _, _ in dolls):
            dolls.append((cx, cy, ar, ic))
    dolls.sort(key=lambda d: -d[3])
    return dolls
