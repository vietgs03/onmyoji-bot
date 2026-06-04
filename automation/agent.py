#!/usr/bin/env python3
"""
agent.py - Lop dieu phoi AUTOMATION cho Onmyoji bot.

Ket hop moi thanh phan da xay:
  - control_client: dieu khien game (fgclick, bgshot)
  - world_model: graph UI da hoc (BFS navigate theo label logic)
  - ml.screen_clf: nhan dien man hinh tu anh (bo tro dhash)
  - ml.affordance: uu tien diem click co tac dung
  - ml.ocr: doc text/tai nguyen
  - knowledge.vectordb: tra cuu tri thuc game

API chinh:
  agent = Agent()
  agent.where()                 # man hinh hien tai (sid, label)
  agent.goto("HOME")            # navigate toi man co label
  agent.tap(x, y)               # click + cho + tra man moi
  agent.resources()             # doc tai nguyen (OCR)
  agent.ask("cau hoi KB")       # tra cuu vector DB

Dung: python agent.py [where|goto <label>|resources|ask <q>]
"""
import os, sys, time
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "ml"))
sys.path.insert(0, os.path.join(ROOT, "knowledge"))
sys.path.insert(0, os.path.join(ROOT, "automation"))

from control_client import Controller
from world_model import WorldModel
from perception import dhash, is_loading


class Agent:
    def __init__(self):
        self.c = Controller()
        self.wm = WorldModel().load()
        self._screen_clf = None
        self._screen_ocr = None
        self._afford = None
        self._vdb = None

    # ---------- lazy load ML ----------
    @property
    def screen_clf(self):
        if self._screen_clf is None:
            try:
                from screen_clf import ScreenClf
                self._screen_clf = ScreenClf.load()
            except Exception:
                self._screen_clf = False
        return self._screen_clf or None

    @property
    def screen_ocr(self):
        if self._screen_ocr is None:
            try:
                import screen_ocr as _so
                _so._model()  # nem neu chua build
                self._screen_ocr = _so
            except Exception:
                self._screen_ocr = False
        return self._screen_ocr or None

    @property
    def afford(self):
        if self._afford is None:
            try:
                from affordance import Affordance
                self._afford = Affordance.load()
            except Exception:
                self._afford = False
        return self._afford or None

    @property
    def vdb(self):
        if self._vdb is None:
            try:
                from vectordb import VectorDB
                self._vdb = VectorDB.load()
            except Exception:
                self._vdb = False
        return self._vdb or None

    # ---------- perception ----------
    def shot(self):
        return self.c.bgshot()

    # ---------- doc man hinh DONG (ben voi event/man moi) ----------
    def read(self, img=None, min_conf=55):
        """Tra ScreenReader cua man hien tai (OCR text + tim element)."""
        from screen_reader import ScreenReader
        img = img if img is not None else self.shot()
        return ScreenReader(img, min_conf=min_conf)

    _loading_db = None

    def is_loading_screen(self, img):
        """HOP NHAT 3 detector loading (OR):
          1. is_loading() dark-ratio  -> boot/splash toi (vd man nui noi khoi dong).
          2. LoadingDB pHash 260 artwork -> loading-tip artwork (shikigami), ham<45.
          3. (wait_stable tu lo) it button that -> loading chuyen canh chung.
        Tra True neu (1) hoac (2). (3) do wait_stable xu ly qua dem button."""
        if is_loading(img):
            return True
        if Agent._loading_db is None:
            try:
                from loading_db import LoadingDB
                Agent._loading_db = LoadingDB()
            except Exception:
                Agent._loading_db = False
        if Agent._loading_db:
            return Agent._loading_db.is_loading(img)
        return False

    def wait_stable(self, max_wait=12.0, poll=0.6, min_buttons=2, settle=1):
        """Doi man dung de DOC: het loading (TOI hoac ARTWORK sang) + co du button.
        Tra ngay khi on dinh 'settle' lan (mac dinh 1 = lan dau du dieu kien).
        Khong cho 'dung yen tuyet doi' (HOME co timer/badge dong) -> tranh treo.

        XU LY 2 loai loading screen Onmyoji:
          1. Loading TOI (den + chu 'Onmyoji')           -> is_loading() bat duoc.
          2. Loading ARTWORK sang (tranh + watermark)      -> chi co watermark, KHONG
             co button that. Ta bo qua watermark roi dem button con lai; neu < min
             thi coi nhu CHUA on dinh (van dang chuyen canh)."""
        from screen_reader import ScreenReader
        t = 0.0
        ok_cnt = 0
        last = None
        while t < max_wait:
            img = self.shot()
            if not self.is_loading_screen(img):
                r = ScreenReader(img)
                taps = r.tappables()
                # bo watermark 'onmyoji' + token loading khoi dem button that
                n_hi = sum(1 for txt, _, _, c in taps
                           if c >= 80 and not self._is_watermark(txt))
                if n_hi >= min_buttons:
                    ok_cnt += 1
                    last = (img, r)
                    if ok_cnt >= settle:
                        return img, r
                else:
                    ok_cnt = 0
            time.sleep(poll); t += poll
        return last if last else (img, ScreenReader(img))

    # watermark / token thuong xuat hien tren LOADING screen (khong phai button that).
    # Loading Onmyoji = artwork + logo 'ONMYOJI' + 1 dong tip ('...Soul and receive a
    # 16 Speed Jizo Statue', 'is challenging EXP Spirit'...). Sau khi loai het cac tu
    # nay thi loading con 0 button -> phan biet voi man UI (>=10 button) rat ro.
    _WATERMARK = {
        "onmyoji", "onmyojil", "onmyg", "nm", "myc", "omyg", "ommyg", "mmyg",
        "and", "is", "has", "the", "a", "to", "tapto", "join", "an", "of", "in",
        "receivea", "receive", "soul", "speed", "defbonus", "souledge", "tengashi",
        "obtained", "opened", "premium", "bag", "jizostatue", "jizo", "statue",
        "challenging", "exp", "spirit", "othe", "others", "requested",
        "rebateful", "uade", "joul", "ommyojl", "ail",
    }

    def _is_watermark(self, txt):
        """True neu text la watermark/loading-noise, khong phai button dieu huong."""
        import re
        words = re.findall(r"[a-z]+", txt.lower())
        if not words:
            return True  # so/icon, khong tinh la button text
        return all(w in self._WATERMARK for w in words)

    def click(self, x, y, wait=2.5, settle_buttons=2, polite=False):
        """Click 1 toa do roi DOI cho qua loading + on dinh. Dung cho MOI click
        co the chuyen canh (vd vao 1 page moi). Tra ScreenReader man moi.

        Vi sao can: moi click co the trigger LOADING screen (chuyen canh). Neu doc
        ngay se doc nham watermark. Ta click -> ngu ngan -> wait_stable (bo qua
        loading ca 2 loai) -> tra man dich on dinh.

        polite=True: dung politeclick (chuot that + tra ve cho cu). Mot so nut
        (footer HOME: Friends/Shop/Guild...) NeoX KHONG nhan SendMessage -> can
        chuot that. politeclick tin cay nhat cho cac nut nay (xem LEARNINGS muc 7)."""
        if polite and hasattr(self.c, "politeclick"):
            self.c.politeclick(x, y)
        else:
            self.c.bgclick(x, y)
        time.sleep(wait)
        return self.wait_stable(min_buttons=settle_buttons)[1]

    def tap_text(self, target, wait=2.0, fuzzy=0.8):
        """Tim text tren man (OCR) roi click. Tra (True/False, ScreenReader moi)."""
        r = self.read()
        hit = r.find(target, fuzzy=fuzzy)
        if not hit:
            return False, r
        self.c.bgclick(hit[1], hit[2])
        time.sleep(wait)
        return True, self.wait_stable()[1]

    _ctrl = None

    def controls(self):
        """ControlFinder (template match nut back/close tu OAS). Lazy-load."""
        if Agent._ctrl is None:
            try:
                from controls import ControlFinder
                Agent._ctrl = ControlFinder()
            except Exception:
                Agent._ctrl = False
        return Agent._ctrl or None

    _nav = None

    @property
    def nav(self):
        """ScreenGraph - CONG DIEU HUONG CHINH (graph clean: where/goto/escape).
        Dung thay cho Agent.goto/where cu (world-model dhash) o cac task moi.
        Lazy-load + cache tren instance."""
        if self._nav is None:
            from screen_graph import ScreenGraph
            self._nav = ScreenGraph(self)
        return self._nav

    def back(self, wait=2.0, home=False):
        """Thoat man hien tai - dung find_dismiss (controls.py) tim CHINH XAC nut thoat:
          1. Icon back (mui ten) / close (X popup) bang TEMPLATE MATCH.
          2. Nut CHU thoat/huy (Cancel/Exit/Quit/Leave/Skip) bang OCR - cho popup EN
             khong co icon (vd 'Download Illustration' -> Cancel, cutscene -> Skip).
          3. Fallback: find_close_button HSV + cac vi tri doan cu.
        home=True: lap den khi ve HOME (xu ly man nhieu lop/tab nhu Summon Room).

        Bai hoc: nut thoat KHONG chi la back/X - con co Cancel/Exit/Skip dang chu.
        find_dismiss gop het: back@(55,62) Summon, Cancel@(437,488) popup, Skip cutscene."""
        from perception import find_close_button, dhash, hamming
        from screen_reader import ScreenReader
        cf = self.controls()
        fallback_pos = [(60, 90), (45, 48), (58, 55), (60, 72)]
        for _ in range(6 if home else 1):
            img = self.shot()
            r = ScreenReader(img)
            if home and r.has('Explore') and r.has('Summon'):
                return r  # da ve HOME

            clicked = None
            if cf:
                # find_dismiss: icon back/close (template) HOAC chu Cancel/Exit/Skip
                # (OCR). Tai dung ScreenReader r de tranh OCR lai.
                d = cf.find_dismiss(img, reader=r)
                if d:
                    clicked = d["center"]
            if clicked is None:
                cb = find_close_button(img)
                if cb:
                    clicked = cb
            if clicked is not None:
                self.c.bgclick(clicked[0], clicked[1])
                time.sleep(wait)
                if not home:
                    return self.wait_stable()[1]
                continue

            # fallback cuoi: doan nhieu vi tri (truong hop template khong match)
            before = dhash(img)
            for bx, by in fallback_pos:
                self.c.bgclick(bx, by)
                time.sleep(1.2)
                after = dhash(self.shot())
                if before is None or after is None or hamming(before, after) > 4:
                    break
            if not home:
                time.sleep(max(0.0, wait - 1.2))
                return self.wait_stable()[1]
        return self.wait_stable()[1]

    def where(self, img=None):
        """Tra (sid, label, source). source='dhash' neu khop graph, 'clf' neu doan ML."""
        img = img if img is not None else self.shot()
        dh = dhash(img)
        if dh is None:
            return None, None, "badshot"
        sid, isnew = self.wm.canonicalize(dh, img)
        lbl = self.wm.states.get(sid, {}).get("label")
        if lbl:
            return sid, lbl, "dhash"
        # chua co nhan -> uu tien OCR text (manh nhat cho client EN)
        if self.screen_ocr:
            try:
                plbl, sc, _ = self.screen_ocr.predict(img)
                if sc >= 0.15:  # nguong score chuan hoa
                    return sid, plbl, f"ocr:{sc:.2f}"
            except Exception:
                pass
        # cuoi cung: screen classifier theo grid feature
        if self.screen_clf:
            plbl, prob = self.screen_clf.predict(img)
            if prob >= 0.5:
                return sid, plbl, f"clf:{prob:.2f}"
        return sid, lbl, "dhash"

    def resources(self, img=None):
        from ocr import read_resources
        img = img if img is not None else self.shot()
        return read_resources(img)

    # ---------- navigation ----------
    def tap(self, x, y, wait=1.3):
        self.c.bgclick(x, y)
        time.sleep(wait)
        return self.where()

    def drag(self, x0, y0, x1, y1, steps=14, wait=0.0):
        """Keo/scroll KHONG chiem chuot (vd scroll list stage Soul)."""
        self.c.bgdrag(x0, y0, x1, y1, steps)
        if wait:
            time.sleep(wait)

    def goto(self, target_label, max_steps=8):
        """Navigate toi man co label = target_label bang BFS tren graph da hoc.
        Tra True neu toi noi."""
        for _ in range(max_steps):
            sid, lbl, _ = self.where()
            if lbl == target_label:
                return True
            if sid is None:
                time.sleep(1.0); continue
            # tim 1 state bat ky co label target de BFS toi
            dst = next((s for s, st in self.wm.states.items()
                        if st.get("label") == target_label), None)
            if dst is None:
                print(f"  goto: khong biet man '{target_label}' trong graph")
                return False
            path = self.wm.bfs_path(sid, dst)
            if not path:
                print(f"  goto: khong co duong {lbl} -> {target_label}")
                return False
            for (cx, cy) in path:
                self.c.bgclick(cx, cy); time.sleep(1.3)
        return self.where()[1] == target_label

    # ---------- knowledge ----------
    def ask(self, query, k=5, type_filter=None):
        if not self.vdb:
            return []
        return self.vdb.search(query, k=k, type_filter=type_filter)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "where"
    a = Agent()
    if cmd == "where":
        sid, lbl, src = a.where()
        print(f"sid={sid} label={lbl} source={src}")
    elif cmd == "goto":
        target = sys.argv[2]
        ok = a.goto(target)
        print(f"goto {target}: {'OK' if ok else 'FAILED'} (now: {a.where()[1]})")
    elif cmd == "resources":
        print(a.resources())
    elif cmd == "ask":
        q = " ".join(sys.argv[2:])
        for r in a.ask(q):
            print(f"  [{r['score']:.3f}] ({r['type']}) {r['title']}: {r['text'][:90]}...")
    else:
        print("usage: agent.py [where|goto <label>|resources|ask <q>]")


if __name__ == "__main__":
    main()
