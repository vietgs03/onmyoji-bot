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
# CANDIDATE SIGNATURE - khoa ben vung qua nhieu run (label + vung toa do).
# idx doi giua cac run (OCR khac thu tu) nen KHONG dung idx lam khoa 'da thu'.
# ======================================================================
def cand_sig(clabel, x, y):
    """Chu ky 1 ung vien: nhan + o luoi 40px. Ben vung qua run/OCR nhieu nhe."""
    return f"{clabel}@{round(x/40)},{round(y/40)}"


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
        self.tried = {}               # cand_sig -> result ('noop'|dest_key)
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
        self.global_path = os.path.join(LOGDIR, "explore_graph_global.json")
        self._load_global()        # nap ky uc tich luy cac run truoc

    def _load_global(self):
        """Nap graph tich luy (explore_graph_global.json) vao self.nodes.
        Moi node co fp khoi phuc tu 'sig'/'dhash' -> observe() match duoc man
        da biet & tried duoc tai dung (KHONG thu lai cand da thu run truoc).
        Node nap ve khong co cands thuc (se duoc bo sung khi observe lai man do)."""
        if not os.path.exists(self.global_path):
            self.glob_loaded = 0
            return
        try:
            g = json.load(open(self.global_path))
        except Exception:
            self.glob_loaded = 0
            return
        n = 0
        for k, j in g.get("nodes", {}).items():
            # dhash la chuoi HEX (xem ham dhash/_ham), KHONG ep int
            fp = (set(j.get("sig", [])), j.get("dhash", "0" * 16))
            nd = ExploreNode(k, fp, j.get("label", "?"), [], j.get("shot", ""))
            nd.edges = {dst: (e["via"], e["x"], e["y"])
                        for dst, e in j.get("edges", {}).items()}
            nd.tried = dict(j.get("tried", {}))   # cand_sig -> result
            self.nodes[k] = nd
            n += 1
        self.glob_loaded = n
        if self.verbose:
            print(f"nap global graph: {n} node tich luy", flush=True)

    def merge_global(self):
        """Hop nhat ky uc run nay vao explore_graph_global.json.
        self.nodes da chua CA global cu (nap luc init) + node moi run nay
        -> chi can serialize toan bo. Hop nhat 'cands' moi quan sat duoc de
        biet frontier (cand chua thu)."""
        g = {"nodes": {}, "schema": 1}
        for k, nd in self.nodes.items():
            # FIX1b: KHONG luu node loading/transient (lam sach graph tu dong).
            if self._is_transient(None, nd.fp):
                continue
            j = self._node_json(nd)
            # luu danh sach cand (sig) da QUAN SAT duoc -> tinh frontier sau nay
            if nd.cands:
                j["cands"] = [cand_sig(c[2], c[0], c[1]) for c in nd.cands
                              if self._worthy(c[2], c[3])]
            g["nodes"][k] = j
        # bo edge tro toi node loading da loai
        valid = set(g["nodes"].keys())
        for j in g["nodes"].values():
            j["edges"] = {d: e for d, e in j["edges"].items() if d in valid}
        tmp = self.global_path + ".tmp"
        json.dump(g, open(tmp, "w"), indent=1, ensure_ascii=False)
        os.replace(tmp, self.global_path)
        # thong ke frontier
        front = self._frontier(g)
        if self.verbose:
            print(f"merge global: {len(g['nodes'])} node tong, "
                  f"{len(front)} node con frontier (cand chua thu)", flush=True)
        self.log(ev="merge", n_nodes=len(g["nodes"]), n_frontier=len(front))

    @staticmethod
    def _frontier(g):
        """Node con candidate da quan sat nhung CHUA thu (con duong de di)."""
        out = []
        for k, j in g["nodes"].items():
            tried = set(j.get("tried", {}).keys())
            cands = set(j.get("cands", []))
            if cands - tried:
                out.append((k, j.get("label", "?"), len(cands - tried)))
        out.sort(key=lambda x: -x[2])
        return out

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

    # ---- nhan dien HUB (man Home) de reset moi phien ----
    # Home la man DUY NHAT co cum token nay cung luc (explore/town + summon/shop).
    HOME_TOK = {"explore", "town", "shikigami", "summon", "shop"}

    @classmethod
    def _is_home(cls, reader):
        toks = {_norm(t[0]) for t in reader.tappables()}
        return len(cls.HOME_TOK & toks) >= 3

    def _escape_to_home(self, max_steps=10):
        """Bam back/dismiss lien tiep cho den khi ve Home (hub).
        Xu ly dialog confirm-quit (Summon ket vong). Tra (ok, reader_o_home).
        DUNG dau moi phien -> KHONG bi ket goc nho nhu map_loop truoc."""
        cf = self.a.controls()
        for step in range(max_steps):
            if self.deadline is not None and time.time() > self.deadline:
                return False, None
            img = self.a.shot()
            r = ScreenReader(img)
            if self._is_home(r):
                return True, r
            # dialog confirm-quit -> Confirm
            if r.has("Confirm") and (r.has("Cancel") or r.has("quit")):
                h = r.find("Confirm")
                if h:
                    self.a.c.bgclick(h[1], h[2]); time.sleep(1.4); continue
            # nut dismiss (X/back-arrow) -> fallback back-arrow trai
            spot = (45, 68)
            if cf:
                try:
                    d = cf.find_dismiss(img, reader=r)
                    if d:
                        spot = d["center"]
                except Exception:
                    pass
            self.a.c.bgclick(spot[0], spot[1])
            time.sleep(1.2)
        return False, None

    def _pick_frontier_node(self):
        """Chon node con NHIEU cand chua thu nhat (frontier) trong memory.
        Tra ExploreNode hoac None. Bo qua node khong co edge tu Home (kho toi)."""
        best, best_n = None, 0
        for nd in self.nodes.values():
            if not nd.cands:
                continue
            tried = set(nd.tried.keys())
            unexp = [c for c in nd.cands
                     if self._worthy(c[2], c[3])
                     and cand_sig(c[2], c[0], c[1]) not in tried]
            if len(unexp) > best_n:
                best, best_n = nd, len(unexp)
        return best

    # ---- doc man hinh hien tai -> ExploreNode (tao moi neu chua thay) ----
    # ---- man hinh transient (loading/chuyen canh) -> KHONG tao node rac ----
    @staticmethod
    def _is_transient(reader, fp):
        toks = fp[0]
        if not toks:
            return True
        # 'onmyoj*' deu la LOGO (OCR doc lech: onmyoji/onmyojil/onmyg/onmg/nmyg...).
        # Man chi co logo + toi da 1 token la -> loading/chuyen canh.
        def is_logo(t):
            return t.startswith("onmyoj") or t in ("onmg", "nmyg", "omnyoji",
                                                    "ommgt", "lowng", "lownc")
        non_logo = {t for t in toks if not is_logo(t)}
        if any(is_logo(t) for t in toks) and len(non_logo) <= 1:
            return True
        return False

    def observe(self, hint_label=None):
        img = self.a.shot()
        if img is None:
            time.sleep(0.6)
            img = self.a.shot()
        r = ScreenReader(img)
        fp = fingerprint(r, img)
        # FIX1: bo qua man loading/chuyen canh -> doi roi doc lai (toi da 3 lan).
        # Tranh tao node rac "onmyoji/lowng" lam phong graph + lac duong.
        if hint_label is None:
            for _ in range(3):
                if not self._is_transient(r, fp):
                    break
                time.sleep(1.0)
                img2 = self.a.shot()
                if img2 is not None:
                    img, r = img2, ScreenReader(img2)
                    fp = fingerprint(r, img)
        # tim node trung trong memory (theo same_screen, ko chi sig_key)
        for k, nd in self.nodes.items():
            if same_screen(fp, nd.fp):
                self.cur_key = nd.key
                # node nap tu global co the chua co cands thuc (cands=[]) ->
                # bo sung tu anh hien tai de explore() co gi de thu (frontier).
                if not nd.cands:
                    nd.cands = candidates(r, img)
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
        Verify bang same_screen voi fp cua target.
        GHI EDGE 'back' khi man doi: truoc day back KHONG thanh canh -> graph
        1 chieu (32/53 hub->n nhung chi 4/53 n->hub), khong dieu huong nguoc."""
        target_fp = self.nodes[target_key].fp if target_key in self.nodes else None
        cf = self.a.controls()
        nd = None

        def _log_back_edge(frm_key, to_nd, via, xy):
            """Back lam doi man -> ghi canh dieu huong nguoc (frm --back--> to)."""
            if frm_key == to_nd.key or frm_key not in self.nodes:
                return
            frm_nd = self.nodes[frm_key]
            if to_nd.key not in frm_nd.edges:
                frm_nd.edges[to_nd.key] = (via, xy[0], xy[1])
                self.log(ev="edge", frm=frm_key, to=to_nd.key, via=via,
                         src="back", xy=list(xy), to_label=to_nd.label, new=False)

        for step in range(max_steps):
            # ton trong watchdog: het gio thi thoi backtrack (de run() ket thuc)
            if self.deadline is not None and time.time() > self.deadline:
                return False
            img = self.a.shot()
            r = ScreenReader(img)
            frm_key = self.cur_key
            # 1) dialog confirm-quit -> bam Confirm
            if r.has("Confirm") and (r.has("Cancel") or r.has("quit")):
                hit = r.find("Confirm")
                if hit:
                    self.a.c.bgclick(hit[1], hit[2])
                    time.sleep(1.4)
                    nd, _r, _i, _n = self.observe()
                    _log_back_edge(frm_key, nd, "confirm-quit", (hit[1], hit[2]))
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
            _log_back_edge(frm_key, nd, "back", clicked)
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

    # Tu khoa MENU CHINH (loi game) - uu tien click TRUOC banner event.
    # Bang chung: 9/12 edge Home di vao popup/loading vi click banner goc phai.
    MENU_WORDS = {
        "explore", "soul", "souls", "shikigami", "shop", "summon", "team",
        "guild", "town", "realm", "quest", "quests", "battle", "duel", "arena",
        "story", "chapter", "exploration", "draw", "evolve", "awaken", "book",
        "friends", "mail", "event", "bounty", "secret", "tower", "abyss",
    }

    def _order(self, cands):
        """Thu tu thu uu tien (da loc rac). DATA cho thay: click icon banner goc
        phai (x>900) toan dan vao popup event/loading. Vi vay uu tien:
          0) TEXT chua tu khoa MENU CHINH (loi game)
          1) ICON o GIUA/DAY man (x<900 hoac y>560) = tab menu, KHONG phai banner
          2) text khac co nghia
          3) ICON banner goc phai-tren (x>=900, y<560) = quang cao -> thu CUOI
        Tra list (idx, x, y, label, src)."""
        scored = []
        for idx, (x, y, clabel, src) in enumerate(cands):
            if not self._worthy(clabel, src):
                continue
            n = _norm(clabel)
            is_menu_word = any(w in n for w in self.MENU_WORDS)
            is_banner = (src == "icon" and x >= 900 and y < 560)
            if is_menu_word:
                pri = 0
            elif src == "icon" and not is_banner:
                pri = 1
            elif src == "text":
                pri = 2
            else:                       # icon banner goc phai
                pri = 3
            scored.append((pri, idx, x, y, clabel, src))
        scored.sort(key=lambda s: (s[0], s[1]))
        return [(idx, x, y, l, s) for _p, idx, x, y, l, s in scored]

    def explore(self, node, depth, max_depth, max_actions, max_per_node=None):
        if self._budget_done(max_actions) or depth > max_depth:
            return
        # FIX3: cap so cand thu MOI LAN o 1 node (per-node) de KHONG ngon het
        # budget o Home -> frontier loop kich hoat som, lan toi vung khac.
        done_here = 0
        # thu tung ung vien CHUA thu (da loc rac + sap uu tien). Khoa = cand_sig
        # (ben vung qua run: node.tried co the da nap tu global graph).
        for idx, x, y, clabel, src in self._order(node.cands):
            if self._budget_done(max_actions):
                return
            if max_per_node is not None and done_here >= max_per_node:
                return
            csig = cand_sig(clabel, x, y)
            if csig in node.tried:
                continue
            done_here += 1
            node.tried[csig] = "pending"
            self.n_actions += 1
            # ICON header/footer hay can politeclick; text dung sendclick truoc
            before = node.fp
            self._click(x, y, src)
            time.sleep(1.6)
            after_nd, r2, img2, is_new = self.observe()
            # NOOP-RETRY: truoc khi bo vinh vien, thu method NGUOC lai (politeclick
            # vs bgclick). Nhieu nut footer/header chi an bang politeclick that su.
            if same_screen(before, after_nd.fp):
                alt = "bg" if src == "icon" else "polite"
                self._click(x, y, src, method=alt)
                time.sleep(1.6)
                after_nd, r2, img2, is_new = self.observe()
            if same_screen(before, after_nd.fp):
                node.tried[csig] = "noop"
                self.log(ev="try", frm=node.key, idx=idx, label=clabel,
                         src=src, xy=[x, y], result="noop")
                continue
            # man da doi -> ghi edge
            node.tried[csig] = after_nd.key
            node.edges[after_nd.key] = (clabel, x, y)
            self.log(ev="edge", frm=node.key, to=after_nd.key,
                     via=clabel, src=src, xy=[x, y], to_label=after_nd.label,
                     new=is_new)
            self.save_graph()                       # luu NGAY (khong mat khi ket/kill)
            # de quy vao man moi (neu moi & con ngan sach)
            if is_new and depth + 1 <= max_depth:
                self.explore(after_nd, depth + 1, max_depth, max_actions, max_per_node)
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
                        self.explore(new_root, depth, max_depth, max_actions, max_per_node)
                return

    def _click(self, x, y, src, method=None):
        """Click 1 diem. method ep buoc ('polite'|'bg'); mac dinh suy tu src.
        icon (header/footer) -> politeclick tin cay hon; text -> sendclick."""
        m = method or ("polite" if src == "icon" else "bg")
        try:
            if m == "polite":
                self.a.c.politeclick(x, y)
            else:
                self.a.c.bgclick(x, y)
        except Exception:
            pass

    def _home_node(self):
        """Tra ExploreNode ung voi Home (hub) trong memory, neu co."""
        for nd in self.nodes.values():
            toks = nd.fp[0]
            if len(self.HOME_TOK & toks) >= 3:
                return nd
        return None

    def _bfs_path(self, src_key, dst_key):
        """Duong di ngan nhat src->dst theo edges da biet. List[(node_key, cand)].
        cand = (label,x,y) de click tu node truoc. None neu khong co duong."""
        if src_key == dst_key:
            return []
        from collections import deque
        prev = {src_key: None}
        q = deque([src_key])
        while q:
            k = q.popleft()
            nd = self.nodes.get(k)
            if not nd:
                continue
            for dst, via in nd.edges.items():
                if dst not in prev:
                    prev[dst] = (k, via)
                    if dst == dst_key:
                        # truy nguoc
                        path = []
                        cur = dst_key
                        while prev[cur] is not None:
                            pk, via = prev[cur]
                            path.append((cur, via))
                            cur = pk
                        path.reverse()
                        return path
                    q.append(dst)
        return None

    def _navigate_to(self, target_node):
        """Di tu Home toi target_node qua edges da biet. Tra True neu toi noi.
        Click tung edge, verify bang same_screen sau moi buoc."""
        home = self._home_node()
        if home is None:
            return False
        path = self._bfs_path(home.key, target_node.key)
        if path is None:
            self.log(ev="nav_nopath", target=target_node.key)
            return False
        for dst_key, (clabel, x, y) in path:
            if self.deadline is not None and time.time() > self.deadline:
                return False
            src = "icon" if clabel.startswith("icon@") else "text"
            self._click(x, y, src)
            time.sleep(1.6)
            nd, r, img, _ = self.observe()
            if nd.key != dst_key and not (
                    dst_key in self.nodes and same_screen(nd.fp, self.nodes[dst_key].fp)):
                self.log(ev="nav_lost", want=dst_key, now=nd.key)
                return False
        return self.cur_key == target_node.key or \
            same_screen(self.nodes[self.cur_key].fp, target_node.fp)

    def run(self, max_actions=50, max_depth=3, start_label=None, budget_sec=300,
            do_merge=True, max_per_node=6):
        self.deadline = time.time() + budget_sec
        # B2: dua cua so ve (0,0) tren man chinh TRUOC khi explore. FIX GOC:
        # window off-screen (4047,-72) lam politeclick footer/header that bai ->
        # menu chinh (summon/town/team/shop) noop. Sau move, click chuot that an.
        try:
            mv = self.a.c.movewin(0, 0)
            self.log(ev="movewin", res=str(mv))
        except Exception as e:
            self.log(ev="movewin_err", err=str(e))
        # 1) RESET ve Home (hub) -> khong ket goc nho nhu map_loop thu dong
        ok_home, r = self._escape_to_home()
        nd, r, img, _ = self.observe(hint_label=start_label)
        self.log(ev="start", root=nd.key, label=nd.label, budget_sec=budget_sec,
                 glob_loaded=getattr(self, "glob_loaded", 0), at_home=ok_home)
        # 2) vet can tu Home truoc (bung het cac nhanh hub)
        self.explore(nd, 0, max_depth, max_actions, max_per_node)
        # 3) FRONTIER-DRIVEN: lap - ve Home, chon node nhieu cand chua thu nhat,
        #    navigate toi do, explore tiep. Pha tran "ket 1 goc".
        while not self._budget_done(max_actions):
            tgt = self._pick_frontier_node()
            if tgt is None:
                self.log(ev="frontier_empty")
                break
            self._escape_to_home()
            if not self._navigate_to(tgt):
                # khong toi duoc -> danh dau de khong lap vo han (thu cand tu cho dung)
                self.log(ev="nav_fail", target=tgt.key, label=tgt.label)
                cur = self.nodes.get(self.cur_key)
                if cur and cur.key != tgt.key:
                    self.explore(cur, 0, max_depth, max_actions, max_per_node)
                # tranh chon lai cung node ket: danh dau cand chua thu cua tgt = skip
                for c in tgt.cands:
                    cs = cand_sig(c[2], c[0], c[1])
                    tgt.tried.setdefault(cs, "unreached")
                continue
            self.log(ev="frontier_reached", target=tgt.key, label=tgt.label)
            self.explore(self.nodes[self.cur_key], 0, max_depth, max_actions, max_per_node)
        self.save_graph()
        if do_merge:
            self.merge_global()             # hop nhat vao ky uc tich luy
        self.log(ev="done", n_nodes=len(self.nodes), n_actions=self.n_actions,
                 timed_out=time.time() > self.deadline)

    def save_graph(self):
        # luu graph RUN nay (snapshot) - de debug 1 phien
        g = {"nodes": {}, "run": self.run_id}
        for k, nd in self.nodes.items():
            g["nodes"][k] = self._node_json(nd)
        path = os.path.join(LOGDIR, f"explore_graph_{self.run_id}.json")
        json.dump(g, open(path, "w"), indent=1, ensure_ascii=False)
        if self.verbose:
            print(f"luu graph {path}: {len(self.nodes)} node", flush=True)

    @staticmethod
    def _node_json(nd):
        """Serialize 1 node (gom sig de nap lai fingerprint + tried/edges).
        sig = list token chu (text_signature) -> khoi phuc same_screen qua run."""
        return {
            "label": nd.label,
            "shot": os.path.basename(nd.shot),
            "sig": sorted(nd.fp[0]),       # text_signature (set token chu)
            "dhash": nd.fp[1],
            "n_cands": len(nd.cands),
            "edges": {dst: {"via": v[0], "x": v[1], "y": v[2]}
                      for dst, v in nd.edges.items()},
            "tried": {cs: (res if isinstance(res, str) else str(res))
                      for cs, res in nd.tried.items() if res != "pending"},
        }


def _print_frontier():
    """In frontier tu explore_graph_global.json (KHONG can game)."""
    p = os.path.join(LOGDIR, "explore_graph_global.json")
    if not os.path.exists(p):
        print("chua co global graph"); return
    g = json.load(open(p))
    front = Explorer._frontier(g)
    print(f"GLOBAL: {len(g['nodes'])} node, {len(front)} node con frontier\n")
    for k, lbl, n in front[:30]:
        print(f"  [{n:2} cand chua thu] {lbl[:46]}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("start_label", nargs="?", default=None)
    ap.add_argument("--max-actions", type=int, default=50)
    ap.add_argument("--max-depth", type=int, default=3)
    ap.add_argument("--budget-sec", type=int, default=300)
    ap.add_argument("--no-merge", action="store_true",
                    help="khong hop nhat vao global graph")
    ap.add_argument("--show-frontier", action="store_true",
                    help="chi in frontier global roi thoat (khong can game)")
    ap.add_argument("--max-per-node", type=int, default=6,
                    help="cap so cand thu moi lan o 1 node (bat frontier loop som)")
    args = ap.parse_args()
    if args.show_frontier:
        _print_frontier()
        return
    from agent import Agent
    a = Agent()
    try:
        Explorer(a).run(max_actions=args.max_actions,
                        max_depth=args.max_depth,
                        start_label=args.start_label,
                        budget_sec=args.budget_sec,
                        do_merge=not args.no_merge,
                        max_per_node=args.max_per_node)
    finally:
        os._exit(0)


if __name__ == "__main__":
    main()
