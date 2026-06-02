#!/usr/bin/env python3
"""
World Model: graph trang thai game tu hoc.

Node = state (man hinh), dinh danh boi dHash on dinh (canonical, gop gan giong).
Edge = (from_state, click_point) -> to_state.

Luu tru:
  exploration/world.json   { states: {sid: {dhash, label, desc, screenshot}},
                             edges: [{from, click, to}] }

API:
  wm = WorldModel(); wm.load()
  sid, isnew, img = wm.observe()                 # chup + canonicalize
  wm.add_edge(from_sid, (x,y), to_sid)
  wm.untried_buttons(sid, all_buttons)           # nut chua thu o state nay
  wm.save()
"""
import json, os
import cv2
from perception import bgshot, dhash, hamming, state_id, detect_buttons

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "exploration")
SCREENS = os.path.join(EXP, "screens")
WORLD = os.path.join(EXP, "world.json")
os.makedirs(SCREENS, exist_ok=True)

CANON_THR = 12  # hamming <= -> cung 1 state


class WorldModel:
    def __init__(self):
        self.states = {}   # sid -> {dhash,label,desc,screenshot,buttons_tried:[[x,y]]}
        self.edges = []    # {from,click,to}

    def load(self):
        if os.path.exists(WORLD):
            d = json.load(open(WORLD, encoding="utf-8"))
            self.states = d.get("states", {})
            self.edges = d.get("edges", [])
        return self

    def save(self):
        json.dump({"states": self.states, "edges": self.edges},
                  open(WORLD, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    def canonicalize(self, dh, img):
        """Tra (sid, isnew). Gop man hinh gan giong ve cung sid."""
        for sid, st in self.states.items():
            if hamming(dh, st["dhash"]) <= CANON_THR:
                return sid, False
        sid = state_id(dh)
        path = os.path.join(SCREENS, f"{sid}.png")
        cv2.imwrite(path, img)
        self.states[sid] = {
            "dhash": dh, "label": None, "desc": None,
            "screenshot": os.path.relpath(path, ROOT),
            "buttons_tried": [],
        }
        return sid, True

    def observe(self):
        img = bgshot()
        if img is None:
            return None, False, None
        dh = dhash(img)
        sid, isnew = self.canonicalize(dh, img)
        return sid, isnew, img

    def add_edge(self, frm, click, to):
        e = {"from": frm, "click": list(click), "to": to}
        if e not in self.edges:
            self.edges.append(e)

    def _same_label_sids(self, sid):
        """Cac sid cung LABEL (de gop buttons_tried theo man hinh logic).
        Neu chua co label, chi tinh ban than sid."""
        lbl = self.states.get(sid, {}).get("label")
        if not lbl:
            return [sid]
        return [s for s, st in self.states.items() if st.get("label") == lbl]

    def mark_tried(self, sid, click):
        bt = self.states[sid]["buttons_tried"]
        if list(click) not in bt:
            bt.append(list(click))

    def is_tried(self, sid, click, tol=18):
        # gop buttons_tried cua TAT CA states cung label (man hinh logic)
        for s in self._same_label_sids(sid):
            for bx, by in self.states[s].get("buttons_tried", []):
                if abs(bx - click[0]) <= tol and abs(by - click[1]) <= tol:
                    return True
        return False

    def neighbors(self, sid):
        return [(tuple(e["click"]), e["to"]) for e in self.edges if e["from"] == sid]

    def _logical(self, sid):
        """Khoa logic cua state: label neu co, nguoc lai chinh sid.
        Cac state cung label duoc coi la 1 node (chia se edges)."""
        lbl = self.states.get(sid, {}).get("label")
        return f"L:{lbl}" if lbl else sid

    def bfs_path(self, src, dst):
        """Tim duong click ngan nhat src->dst (theo node LOGIC = cung label gop chung).
        Tra list click hoac None."""
        from collections import deque
        # map logic -> cac click-edge: (click, logic_dst)
        adj = {}
        for e in self.edges:
            lf = self._logical(e["from"])
            lt = self._logical(e["to"])
            adj.setdefault(lf, []).append((tuple(e["click"]), lt))
        lsrc, ldst = self._logical(src), self._logical(dst)
        if lsrc == ldst:
            return []
        q = deque([(lsrc, [])]); seen = {lsrc}
        while q:
            cur, path = q.popleft()
            if cur == ldst:
                return path
            for click, nxt in adj.get(cur, []):
                if nxt not in seen:
                    seen.add(nxt)
                    q.append((nxt, path + [click]))
        return None

    def stats(self):
        return {"states": len(self.states), "edges": len(self.edges),
                "labeled": sum(1 for s in self.states.values() if s.get("label"))}
