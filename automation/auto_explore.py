#!/usr/bin/env python3
"""
explorer.py - VET CAN tu dong man hinh game (autonomous UI exploration).

Triet ly (theo yeu cau): KHONG doan toa do thu cong. Vao 1 man hinh -> liet ke
MOI ung vien click (text-OCR + icon-blob khong-chu nhu nut Bonus) -> dung dau
ghi do -> click -> neu man doi thi xay edge + de quy explore man moi -> backtrack.
Giong do me cung tu phat trien. Tat ca ghi ra graph realtime.

Khac biet voi screen_graph.py:
  - screen_graph = cay menu DA BIET (con nguoi/agent dat ten, navigate co dich).
  - explorer = TU DONG kham pha cai CHUA biet, sinh du lieu de bo sung cay do.

Thanh phan:
  1. fingerprint(reader,img) -> chu ky man hinh (tap-text set + dhash) de nhan
     "da tham man nay chua" (khu trung lap, tranh lap vo han).
  2. candidates(reader,img) -> [(x,y,label,source)] moi diem dang click:
       - text-OCR tappables (co nhan)
       - icon-blob: contour vung sang/nut tron khong co chu (bat nut Bonus)
  3. Explorer.run(): DFS co stack + backtrack (escape/back). Moi node nho ung
     vien nao DA thu + ket qua (no-op / dan toi man X). Ghi logs/explore_*.jsonl
     va logs/explore_graph.json.

Dung:
  python explorer.py [start_node] [--max-actions N] [--max-depth D]
  # vd dang o man Soul: python explorer.py --max-actions 60
"""
import os, sys, time, json, hashlib
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "automation"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "ml"))

from screen_reader import ScreenReader, _norm

LOGDIR = os.path.join(ROOT, "logs")
os.makedirs(LOGDIR, exist_ok=True)
SHOTDIR = os.path.join(LOGDIR, "explore_shots")
os.makedirs(SHOTDIR, exist_ok=True)


# ======================================================================
# 1) FINGERPRINT - chu ky man hinh
# ======================================================================
def dhash(img, hash_size=8):
    """Perceptual hash (difference hash). Robust voi nhieu nho, doi sang."""
    if img is None:
        return "0" * 16
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (hash_size + 1, hash_size))
    diff = g[:, 1:] > g[:, :-1]
    bits = 0
    for b in diff.flatten():
        bits = (bits << 1) | int(b)
    return f"{bits:0{hash_size*hash_size//4}x}"


def _ham(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def text_signature(reader):
    """Tap text chuan hoa, on dinh -> chu ky NGHIA cua man hinh.
    Bo qua so/timer (hay thay doi: HP, dem gio) de fingerprint on dinh."""
    toks = set()
    for txt, _, _, conf in reader.tappables():
        n = _norm(txt)
        if len(n) < 2:
            continue
        # bo token toan so / co nhieu so (HP, gio, tien) - khong on dinh
        digits = sum(c.isdigit() for c in n)
        if digits and digits >= len(n) * 0.5:
            continue
        toks.add(n)
    return frozenset(toks)


def fingerprint(reader, img):
    """(text_sig, dhash). 2 man 'cung' neu text_sig giong NHIEU + dhash gan."""
    return text_signature(reader), dhash(img)


def same_screen(fp1, fp2, jacc=0.6, hd=12, abs_overlap=8):
    """2 fingerprint co phai cung mot man? Uu tien NGHIA (text overlap).
    - Jaccard >= jacc -> cung man.
    - HOAC so token chu CHUNG >= abs_overlap (man nhieu token nhu Home/Town,
      OCR nhieu nhe lam Jaccard tut nhung van chung phan lon noi dung).
    - inter/union < 0.3 -> chac chan khac man.
    Fallback hinh anh (hamming dhash) khi it/khong co text."""
    s1, h1 = fp1
    s2, h2 = fp2
    if s1 or s2:
        inter = len(s1 & s2)
        union = len(s1 | s2) or 1
        if inter / union >= jacc or inter >= abs_overlap:
            return True
        if inter / union < 0.30:
            return False
    # it text -> dua vao hinh
    return _ham(h1, h2) <= hd


def sig_key(fp):
    """Khoa on dinh cho dict node (tu text_sig; rong thi dung dhash)."""
    s, h = fp
    if s:
        return "T:" + hashlib.md5("|".join(sorted(s)).encode()).hexdigest()[:12]
    return "H:" + h


# ======================================================================
# 2) CANDIDATES - moi diem dang click (text + icon khong-chu)
# ======================================================================
def _icon_blobs(img, exclude_boxes, min_area=240, max_area=9000):
    """Tim cac NUT/ICON KHONG CHU (vd nut Bonus swirl, nut tron header/footer).
    Cach: tim vung SANG noi bat (nut thuong sang hon nen), hinh gon (compact),
    KHONG nam de len text da co. Tra [(cx,cy,w,h)].

    Ly do can: OCR bo sot nut icon khong chu -> explorer se khong bao gio thu
    nut Bonus neu chi dua vao text. Day la mau chot 'dung dau ghi do'."""
    if img is None:
        return []
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # nut UI thuong sang/tuong phan -> nguong thich nghi + Otsu ket hop
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        a = cv2.contourArea(c)
        if a < min_area or a > max_area:
            continue
        x, y, w, h = cv2.boundingRect(c)
        ar = w / (h + 1e-6)
        if ar < 0.45 or ar > 2.6:        # icon ~ vuong/tron, bo thanh dai
            continue
        fill = a / (w * h + 1e-6)
        if fill < 0.45:                  # qua rong -> ko phai nut dac
            continue
        cx, cy = x + w // 2, y + h // 2
        # bo qua neu trung tam de len text da OCR (da co ung vien text)
        skip = False
        for (ex, ey, ew, eh) in exclude_boxes:
            if ex - 6 <= cx <= ex + ew + 6 and ey - 6 <= cy <= ey + eh + 6:
                skip = True
                break
        if skip:
            continue
        out.append((cx, cy, w, h))
    # khu trung diem gan nhau (<24px)
    dedup = []
    for cx, cy, w, h in sorted(out, key=lambda b: -b[2] * b[3]):
        if all(abs(cx - dx) + abs(cy - dy) > 24 for dx, dy, _, _ in dedup):
            dedup.append((cx, cy, w, h))
    return dedup


# Vung game an toan de click. Tranh:
#  - title bar Windows (y<TOP_SAFE): text 'onmyoji' o (77,16) khong phai game UI.
#  - nut X dong CUA SO game (goc tren phai ~1115,16): bam la TAT GAME.
TOP_SAFE = 34            # y < day = title bar OS, bo qua
WIN_CLOSE = (1100, 1152, 0, 34)   # x0,x1,y0,y1 vung nut min/max/X cua so


def _in_game(cx, cy):
    if cy < TOP_SAFE:
        return False
    x0, x1, y0, y1 = WIN_CLOSE
    if x0 <= cx <= x1 and y0 <= cy <= y1:
        return False
    return True


def candidates(reader, img):
    """Tra danh sach ung vien click [(x,y,label,source)].
    source: 'text' (co nhan OCR) hoac 'icon' (blob khong chu).
    LOC vung title-bar Windows + nut dong cua so (tranh thoat game)."""
    cands = []
    text_boxes = []
    for txt, (x, y, w, h), conf in reader.words:
        text_boxes.append((x, y, w, h))
    # text tappables (da loc marquee)
    seen = set()
    for txt, cx, cy, conf in reader.tappables():
        if not _in_game(cx, cy):
            continue
        key = (round(cx / 18), round(cy / 18))
        if key in seen:
            continue
        seen.add(key)
        cands.append((cx, cy, _norm(txt) or "?", "text"))
    # icon blobs khong chu
    for cx, cy, w, h in _icon_blobs(img, text_boxes):
        if not _in_game(cx, cy):
            continue
        key = (round(cx / 18), round(cy / 18))
        if key in seen:
            continue
        seen.add(key)
        cands.append((cx, cy, f"icon@{cx},{cy}", "icon"))
    return cands


# ======================================================================
# 3) EXPLORER - DFS vet can co backtrack
# ======================================================================
class ExploreNode:
    __slots__ = ("key", "fp", "label", "cands", "tried", "edges", "shot")

    def __init__(self, key, fp, label, cands, shot):
        self.key = key
        self.fp = fp
        self.label = label
        self.cands = cands            # [(x,y,label,source)]
        self.tried = {}               # idx -> result ('noop'|dest_key|'lost')
        self.edges = {}               # dest_key -> (cand_label, x, y)
        self.shot = shot


class Explorer:
    def __init__(self, agent, verbose=True):
        self.a = agent
        self.nodes = {}               # key -> ExploreNode
        self.verbose = verbose
        self.t0 = time.time()
        self.run_id = time.strftime("%H%M%S")
        self.jl = open(os.path.join(LOGDIR, f"explore_{self.run_id}.jsonl"), "w")
        self.n_actions = 0
        self.cur_key = None        # node man hinh dang dung (cap nhat moi observe)
        self.deadline = None       # wall-clock budget (set trong run)

    def _budget_done(self, max_actions):
        """True khi het ngan sach: so action HOAC qua thoi gian (watchdog).
        Tranh treo vo han khi backtrack lac (vd ket trong popup Summon)."""
        if self.n_actions >= max_actions:
            return True
        if self.deadline is not None and time.time() > self.deadline:
            return True
        return False

    def log(self, **kw):
        kw["t"] = round(time.time() - self.t0, 1)
        self.jl.write(json.dumps(kw, ensure_ascii=False) + "\n")
        self.jl.flush()
        if self.verbose:
            print(json.dumps(kw, ensure_ascii=False), flush=True)

    # ---- doc man hinh hien tai -> ExploreNode (tao moi neu chua thay) ----
    def observe(self, hint_label=None):
        img = self.a.shot()
        if img is None:
            time.sleep(0.6)
            img = self.a.shot()
        r = ScreenReader(img)
        fp = fingerprint(r, img)
        # tim node trung trong memory (theo same_screen, ko chi sig_key)
        for k, nd in self.nodes.items():
            if same_screen(fp, nd.fp):
                self.cur_key = nd.key
                return nd, r, img, False
        key = sig_key(fp)
        # tranh dung key (hiem) -> them hau to
        if key in self.nodes:
            key += f".{len(self.nodes)}"
        cands = candidates(r, img)
        label = hint_label or self._auto_label(r)
        shot_path = os.path.join(SHOTDIR, f"{self.run_id}_{key}.png")
        if not os.path.exists(shot_path) and img is not None:
            cv2.imwrite(shot_path, img)
        nd = ExploreNode(key, fp, label, cands, shot_path)
        self.nodes[key] = nd
        self.cur_key = key
        self.log(ev="new_screen", key=key, label=label,
                 n_cands=len(cands),
                 sample=[c[2] for c in cands[:8]])
        return nd, r, img, True

    def _auto_label(self, reader):
        """Dat ten tam cho man tu vai text CHU noi bat (bo token so/tien/level).
        Vd Home -> 'explore/event/shikigami' chu khong phai '287/1432m/120k'."""
        def is_word(t):
            n = _norm(t)
            if len(n) < 3:
                return False
            digits = sum(c.isdigit() for c in n)
            return digits < len(n) * 0.5
        toks = [t for t in reader.tappables() if is_word(t[0])]
        # uu tien token to (button) + tren cao
        toks.sort(key=lambda t: (-t[3], t[2]))
        seen, picked = set(), []
        for t in toks:
            n = _norm(t[0])
            if n in seen:
                continue
            seen.add(n)
            picked.append(n)
            if len(picked) >= 3:
                break
        return "/".join(picked) or "?"

    # ---- backtrack ve node muc tieu bang back/escape ----
    def _back_to(self, target_key, max_steps=4):
        """Quay ve target NHANH (ton trong deadline toan cuc). Xu ly:
          1. Dialog xac nhan thoat (Confirm/Cancel) - vd Summon hoi 'Confirm to
             quit?'. Phai bam Confirm de back THUC SU (chi back-arrow se ket vong).
          2. Nut dismiss (back-arrow/X) qua controls.find_dismiss neu co, fallback
             back-arrow trai (45,68).
        Tranh Agent.back() day du (cham 10-20s/lan vi wait_stable+fallback loop).
        Verify bang same_screen voi fp cua target."""
        target_fp = self.nodes[target_key].fp if target_key in self.nodes else None
        cf = self.a.controls()
        nd = None
        for step in range(max_steps):
            # ton trong watchdog: het gio thi thoi backtrack (de run() ket thuc)
            if self.deadline is not None and time.time() > self.deadline:
                return False
            img = self.a.shot()
            r = ScreenReader(img)
            # 1) dialog confirm-quit -> bam Confirm
            if r.has("Confirm") and (r.has("Cancel") or r.has("quit")):
                hit = r.find("Confirm")
                if hit:
                    self.a.c.bgclick(hit[1], hit[2])
                    time.sleep(1.4)
                    nd, _r, _i, _n = self.observe()
                    if self._reached(target_key, target_fp, nd):
                        return True
                    continue
            # 2) nut dismiss chinh xac (template/OCR) -> fallback back-arrow trai
            clicked = None
            if cf:
                try:
                    d = cf.find_dismiss(img, reader=r)
                    if d:
                        clicked = d["center"]
                except Exception:
                    pass
            if clicked is None:
                clicked = (45, 68)
            self.a.c.bgclick(clicked[0], clicked[1])
            time.sleep(1.3)
            nd, r, img, _new = self.observe()
            if self._reached(target_key, target_fp, nd):
                return True
        return False

    @staticmethod
    def _reached(target_key, target_fp, nd):
        if nd.key == target_key:
            return True
        return target_fp is not None and same_screen(target_fp, nd.fp)

    # ---- DFS de quy ----
    @staticmethod
    def _worthy(clabel, src):
        """Bo ung vien 'rac': token toan so (HP/gio/tien), 1 ky tu."""
        if src == "icon":
            return True
        n = _norm(clabel)
        if len(n) < 2:
            return False
        digits = sum(c.isdigit() for c in n)
        if digits >= len(n) * 0.6:        # 3777, 80008000, 1950...
            return False
        return True

    def _order(self, cands):
        """Thu tu thu: icon truoc (hay bi bo sot) roi text co nghia.
        Tra list (idx, x, y, label, src) da loc rac."""
        scored = []
        for idx, (x, y, clabel, src) in enumerate(cands):
            if not self._worthy(clabel, src):
                continue
            pri = 0 if src == "icon" else 1
            scored.append((pri, idx, x, y, clabel, src))
        scored.sort(key=lambda s: (s[0], s[1]))
        return [(idx, x, y, l, s) for _p, idx, x, y, l, s in scored]

    def explore(self, node, depth, max_depth, max_actions):
        if self._budget_done(max_actions) or depth > max_depth:
            return
        # thu tung ung vien CHUA thu (da loc rac + sap uu tien)
        for idx, x, y, clabel, src in self._order(node.cands):
            if self._budget_done(max_actions):
                return
            if idx in node.tried:
                continue
            node.tried[idx] = "pending"
            self.n_actions += 1
            # ICON header/footer hay can politeclick; text dung sendclick truoc
            before = node.fp
            self._click(x, y, src)
            time.sleep(1.6)
            after_nd, r2, img2, is_new = self.observe()
            if same_screen(before, after_nd.fp):
                node.tried[idx] = "noop"
                self.log(ev="try", frm=node.key, idx=idx, label=clabel,
                         src=src, xy=[x, y], result="noop")
                continue
            # man da doi -> ghi edge
            node.tried[idx] = after_nd.key
            node.edges[after_nd.key] = (clabel, x, y)
            self.log(ev="edge", frm=node.key, to=after_nd.key,
                     via=clabel, src=src, xy=[x, y], to_label=after_nd.label,
                     new=is_new)
            self.save_graph()                       # luu NGAY (khong mat khi ket/kill)
            # de quy vao man moi (neu moi & con ngan sach)
            if is_new and depth + 1 <= max_depth:
                self.explore(after_nd, depth + 1, max_depth, max_actions)
            # backtrack ve node hien tai
            ok = self._back_to(node.key)
            if not ok:
                self.log(ev="lost", want=node.key, now=self.cur_key)
                # khong treo: chap nhan man hien tai lam goc moi de explore tiep,
                # KHONG return (de van vet can tu cho dang dung). Neu man hien tai
                # la node da biet -> tiep tuc tu do.
                if self.cur_key in self.nodes:
                    new_root = self.nodes[self.cur_key]
                    if new_root.key != node.key:
                        self.explore(new_root, depth, max_depth, max_actions)
                return

    def _click(self, x, y, src):
        # icon (header/footer) -> politeclick tin cay hon; text -> sendclick
        if src == "icon":
            try:
                self.a.c.politeclick(x, y)
                return
            except Exception:
                pass
        try:
            self.a.c.bgclick(x, y)
        except Exception:
            pass

    def run(self, max_actions=50, max_depth=3, start_label=None, budget_sec=300):
        self.deadline = time.time() + budget_sec
        nd, r, img, _ = self.observe(hint_label=start_label)
        self.log(ev="start", root=nd.key, label=nd.label, budget_sec=budget_sec)
        self.explore(nd, 0, max_depth, max_actions)
        self.save_graph()
        self.log(ev="done", n_nodes=len(self.nodes), n_actions=self.n_actions,
                 timed_out=time.time() > self.deadline)

    def save_graph(self):
        g = {"nodes": {}, "run": self.run_id}
        for k, nd in self.nodes.items():
            g["nodes"][k] = {
                "label": nd.label,
                "shot": os.path.basename(nd.shot),
                "n_cands": len(nd.cands),
                "edges": {dst: {"via": v[0], "x": v[1], "y": v[2]}
                          for dst, v in nd.edges.items()},
                "noop": [nd.cands[i][2] for i, res in nd.tried.items()
                         if res == "noop" and i < len(nd.cands)],
            }
        path = os.path.join(LOGDIR, f"explore_graph_{self.run_id}.json")
        json.dump(g, open(path, "w"), indent=1, ensure_ascii=False)
        if self.verbose:
            print(f"luu graph {path}: {len(self.nodes)} node", flush=True)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("start_label", nargs="?", default=None)
    ap.add_argument("--max-actions", type=int, default=50)
    ap.add_argument("--max-depth", type=int, default=3)
    ap.add_argument("--budget-sec", type=int, default=300)
    args = ap.parse_args()
    from agent import Agent
    a = Agent()
    try:
        Explorer(a).run(max_actions=args.max_actions,
                        max_depth=args.max_depth,
                        start_label=args.start_label,
                        budget_sec=args.budget_sec)
    finally:
        os._exit(0)


if __name__ == "__main__":
    main()
