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

    def wait_stable(self, max_wait=12.0, poll=0.6, min_buttons=2, settle=1):
        """Doi man dung de DOC: het loading toi + co du button conf cao.
        Tra ngay khi on dinh 'settle' lan (mac dinh 1 = lan dau du dieu kien).
        Khong cho 'dung yen tuyet doi' (HOME co timer/badge dong) -> tranh treo."""
        from screen_reader import ScreenReader
        t = 0.0
        ok_cnt = 0
        last = None
        while t < max_wait:
            img = self.shot()
            if not is_loading(img):
                r = ScreenReader(img)
                taps = r.tappables()
                n_hi = sum(1 for _, _, _, c in taps if c >= 80)
                if n_hi >= min_buttons:
                    ok_cnt += 1
                    last = (img, r)
                    if ok_cnt >= settle:
                        return img, r
                else:
                    ok_cnt = 0
            time.sleep(poll); t += poll
        return last if last else (img, ScreenReader(img))

    def tap_text(self, target, wait=2.0, fuzzy=0.8):
        """Tim text tren man (OCR) roi click. Tra (True/False, ScreenReader moi)."""
        r = self.read()
        hit = r.find(target, fuzzy=fuzzy)
        if not hit:
            return False, r
        self.c.bgclick(hit[1], hit[2])
        time.sleep(wait)
        return True, self.wait_stable()[1]

    def back(self, wait=2.0, home=False):
        """Thoat man hien tai THONG MINH:
          1. Neu co nut X (popup) -> bam X (find_close_button)
          2. Nguoc lai bam mui ten back goc tren-trai. Vi tri back khac nhau
             theo man (Town~90, Summon Room~45,48) -> thu tung vi tri.
        home=True: bam lien tuc cho den khi ve HOME (xu ly man co nhieu lop/tab)."""
        from perception import find_close_button, dhash, hamming
        from screen_reader import ScreenReader
        positions = [(60, 90), (45, 48), (58, 55), (60, 72)]
        for attempt in range(6 if home else 1):
            img = self.shot()
            r = ScreenReader(img)
            if home and r.has('Explore') and r.has('Summon'):
                return r  # da ve HOME
            cb = find_close_button(img)
            if cb:
                self.c.bgclick(cb[0], cb[1])
                time.sleep(wait)
                if not home:
                    return self.wait_stable()[1]
                continue
            before = dhash(img)
            for bx, by in positions:
                self.c.bgclick(bx, by)
                time.sleep(1.2)
                after = dhash(self.shot())
                if before is None or after is None or hamming(before, after) > 4:
                    break  # man da doi -> back co tac dung
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
