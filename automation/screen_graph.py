#!/usr/bin/env python3
"""
screen_graph.py - GRAPH DIEU HUONG hop nhat (nguon su that DUY NHAT).

Triet ly (xem docs/navigation_architecture.md): moi MAN = 1 NODE khai bao trong
DATA, moi logic dieu huong dung THUAT TOAN CHUNG (BFS) - KHONG if long vong.
Them man moi = them 1 entry DATA, khong sua thuat toan.

Moi NODE:
  identify : [tu khoa OCR] de nhan dien dang o man nay
  exits    : { man_dich : {via:'ocr', text:[...]} | {via:'xy', center:[x,y]} }
  dismiss  : cach thoat -> man cha. 'auto' = dung controls.find_dismiss (back/X/cancel)
  parent   : man cha (de escape & kiem tra cay)

API CHUNG (khong phu thuoc so node):
  where()       : quet identify moi node -> node hien tai
  goto(target)  : BFS tren exits -> di tung hop
  escape()      : dismiss lien tuc ve HOME

Build DATA tu OAS pagegraph + PAGE_EN: python screen_graph.py build
Xem cay:                                python screen_graph.py tree
Tim duong:                              python screen_graph.py path HOME realm_raid
"""
import os, json, sys, collections, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH_JSON = os.path.join(ROOT, "knowledge", "screen_graph.json")
OAS_GRAPH = os.path.join(ROOT, "knowledge", "oas_pagegraph.json")

HOME = "HOME"


# ======================================================================
# DATA: khai bao NODE. Day la NGUON SU THAT. Them man = them o day.
# Moi node: identify (OCR), exits (canh), parent (cay). dismiss mac dinh 'auto'.
# Toa do center (neu co) la fallback 1152x679; uu tien click theo text (OCR).
# ======================================================================
NODES = {
    "HOME": {
        "identify": ["Explore", "Summon", "Friends"],
        "parent": None,
        "exits": {
            "exploration": {"via": "ocr", "text": ["Explore"], "center": [464, 144]},
            "town":        {"via": "ocr", "text": ["Town"],    "center": [662, 262]},
            "summon":      {"via": "ocr", "text": ["Summon"],  "center": [991, 194]},
            "shikigami":   {"via": "ocr", "text": ["Shikigami"], "center": [997, 586]},
            "onmyodo":     {"via": "ocr", "text": ["Onmyodo"], "center": [881, 573]},
            "friends":     {"via": "ocr", "text": ["Friends"], "center": [785, 582]},
        },
    },
    "exploration": {
        "identify": ["Chapter", "Soul", "Realm"],
        "parent": "HOME",
        "exits": {
            "realm_raid": {"via": "ocr", "text": ["Realm"], "center": [260, 621]},
            "soul_zones": {"via": "ocr", "text": ["Soul"],  "center": [168, 620]},
            "area_boss":  {"via": "ocr", "text": ["Boss"],  "center": [599, 623]},
            "awake_zones":{"via": "ocr", "text": ["Awake"], "center": [80, 615]},
            "secret_zones":{"via": "ocr", "text": ["Secret"], "center": [518, 616]},
            "six_gates":  {"via": "ocr", "text": ["Gates"], "center": [859, 623]},
        },
    },
    "town": {
        "identify": ["Encounter", "Arena", "Duel"],
        "parent": "HOME",
        "exits": {
            "duel":            {"via": "ocr", "text": ["Duel"], "center": [701, 166]},
            "demon_encounter": {"via": "ocr", "text": ["Encounter"], "center": [578, 162]},
            "hunt":            {"via": "ocr", "text": ["Hunt"], "center": [448, 162]},
            "hyakkisen":       {"via": "ocr", "text": ["Hyakki"], "center": [194, 168]},
        },
    },
    "summon":    {"identify": ["Summon", "Scrolls"], "parent": "HOME", "exits": {}},
    "shikigami": {"identify": ["Shikigami", "Preset"], "parent": "HOME", "exits": {}},
    "onmyodo":   {"identify": ["Onmyodo"], "parent": "HOME", "exits": {}},
    "friends":   {"identify": ["Friends", "Guild"], "parent": "HOME", "exits": {}},
    "shop":      {"identify": ["Garment", "Mall", "Stellar Omen"], "parent": "HOME", "exits": {}},
    # man con cap 2 - duoi exploration
    "realm_raid":  {"identify": ["Realm Raid", "Assault"], "parent": "exploration", "exits": {}},
    "soul_zones":  {"identify": ["Soul"], "parent": "exploration", "exits": {}},
    "area_boss":   {"identify": ["Area Boss"], "parent": "exploration", "exits": {}},
    "awake_zones": {"identify": ["Awake"], "parent": "exploration", "exits": {}},
    "secret_zones":{"identify": ["Secret"], "parent": "exploration", "exits": {}},
    "six_gates":   {"identify": ["Six", "Gates"], "parent": "exploration", "exits": {}},
    # man con cap 2 - duoi town
    "duel":            {"identify": ["Duel"], "parent": "town", "exits": {}},
    "demon_encounter": {"identify": ["Encounter"], "parent": "town", "exits": {}},
    "hunt":            {"identify": ["Hunt"], "parent": "town", "exits": {}},
    "hyakkisen":       {"identify": ["Hyakki"], "parent": "town", "exits": {}},
}


class ScreenGraph:
    """Graph dieu huong. Toan bo logic qua BFS/escape - khong if tung man."""

    def __init__(self, agent=None, nodes=None):
        self.a = agent
        self.nodes = nodes or NODES
        # canh: {src: {dst: button}}
        self.edges = {n: d.get("exits", {}) for n, d in self.nodes.items()}

    # do sau cua node (HOME=0) - de tie-break: man con uu tien hon man cha
    def _depth(self, name):
        d = 0
        cur = name
        while cur and self.nodes.get(cur, {}).get("parent"):
            cur = self.nodes[cur]["parent"]
            d += 1
            if d > 20:
                break
        return d

    # ---------- nhan dien (1 ham chung quet moi node) ----------
    def where(self, reader=None, img=None):
        """Node hien tai = node co nhieu tu khoa identify khop nhat.
        Tie-break: node SAU hon (con) thang (vd Summon co 'Summon' nhung khong phai
        HOME). Quy tac chung: HOME KHONG co nut back -> neu thay back arrow thi loai HOME.
        None neu khong ro."""
        r = reader or (self.a.read() if self.a else None)
        if r is None:
            return None
        # HOME khong co nut back/dismiss. Neu co back-arrow -> chac chan KHONG o HOME.
        has_back = False
        if self.a is not None:
            cf = self.a.controls()
            shot = img if img is not None else getattr(r, "img", None)
            if cf is not None and shot is not None:
                has_back = cf.find(shot, kind="back") is not None

        scored = []
        for name, d in self.nodes.items():
            if name == HOME and has_back:
                continue                         # loai HOME khi co nut back
            n = sum(1 for kw in d["identify"] if r.has(kw))
            if n > 0:
                scored.append((n, self._depth(name), name))
        if not scored:
            return None
        # nhieu tu khop nhat; hoa thi node sau hon (depth lon) thang
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return scored[0][2]

    # ---------- BFS tim duong (thuat toan chung) ----------
    def path(self, start, goal):
        """Duong ngan nhat start->goal theo canh exits. None neu khong toi duoc.
        Neu can di NGUOC (ra man cha) thi them canh dismiss vao BFS."""
        if start == goal:
            return [start]
        q = collections.deque([[start]])
        seen = {start}
        while q:
            p = q.popleft()
            cur = p[-1]
            # canh tien (exits) + canh lui (ve parent qua dismiss)
            neighbors = list(self.edges.get(cur, {}).keys())
            par = self.nodes.get(cur, {}).get("parent")
            if par:
                neighbors.append(par)
            for nxt in neighbors:
                if nxt not in seen:
                    seen.add(nxt)
                    np = p + [nxt]
                    if nxt == goal:
                        return np
                    q.append(np)
        return None

    # ---------- thao tac (dung lop chung: controls/ocr) ----------
    def _go_edge(self, src, dst):
        """Di 1 hop src->dst. Neu dst la parent (lui) -> dismiss. Nguoc lai bam exits."""
        if dst == self.nodes.get(src, {}).get("parent") and dst not in self.edges.get(src, {}):
            self.a.back()                       # lui ve cha = dismiss (controls)
            return self.where() == dst
        btn = self.edges.get(src, {}).get(dst)
        if not btn:
            return False
        # uu tien OCR text (ben voi event), fallback toa do
        for kw in btn.get("text", []):
            ok, _ = self.a.tap_text(kw)
            if ok and self.where() == dst:
                return True
        if btn.get("center"):
            self.a.click(*btn["center"])
            return self.where() == dst
        return False

    def goto(self, target, max_hops=8):
        """Di toi `target` tu dau cung duoc (BFS). Re-plan neu drift."""
        cur = self.where()
        if cur is None:                          # khong ro -> ve HOME truoc
            self.escape()
            cur = self.where() or HOME
        for _ in range(max_hops):
            if cur == target:
                return True
            p = self.path(cur, target)
            if not p or len(p) < 2:
                self.escape()                    # bi tat -> ve HOME thu lai
                cur = self.where() or HOME
                p = self.path(cur, target)
                if not p or len(p) < 2:
                    return False
            self._go_edge(p[0], p[1])
            cur = self.where()                   # doc lai vi tri thuc (re-plan)
        return self.where() == target

    def escape(self, max_steps=8):
        """Dismiss lien tuc ve HOME (dung Agent.back home=True)."""
        if self.a:
            self.a.back(home=True)
        return self.where()


# ======================================================================
# BUILD: hop nhat / kiem tra DATA. (Hien DATA viet tay - sach hon graph TQ.)
# Bo sung toa do/canh tu OAS pagegraph neu thieu.
# ======================================================================
def build():
    """Xuat DATA ra JSON (de cong cu khac dung) + kiem tra tinh hop le cua cay."""
    g = ScreenGraph()
    # kiem tra: moi parent ton tai, khong canh tro toi node la
    errs = []
    for n, d in NODES.items():
        par = d.get("parent")
        if par and par not in NODES:
            errs.append(f"{n}: parent '{par}' khong ton tai")
        for dst in d.get("exits", {}):
            if dst not in NODES:
                errs.append(f"{n}: exit '{dst}' khong ton tai")
    out = {"home": HOME, "nodes": NODES}
    json.dump(out, open(GRAPH_JSON, "w"), indent=1, ensure_ascii=False)
    print(f"luu {GRAPH_JSON}: {len(NODES)} node")
    if errs:
        print("LOI cay:")
        for e in errs:
            print("  ", e)
    else:
        print("cay HOP LE (moi parent/exit ton tai)")


def show_tree():
    """In cay node (parent->con) de de kiem tra, khong lan man."""
    children = collections.defaultdict(list)
    for n, d in NODES.items():
        children[d.get("parent")].append(n)

    def rec(node, depth):
        print("  " * depth + node)
        for c in sorted(children.get(node, [])):
            rec(c, depth + 1)
    rec(HOME, 0)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "tree":
        show_tree()
    elif cmd == "path":
        g = ScreenGraph()
        print(" -> ".join(g.path(sys.argv[2], sys.argv[3]) or ["KHONG CO DUONG"]))
    elif cmd == "where":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from agent import Agent
        a = Agent()
        print("dang o:", ScreenGraph(a).where())
        a.c.close()
    elif cmd == "goto":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from agent import Agent
        a = Agent()
        g = ScreenGraph(a)
        ok = g.goto(sys.argv[2])
        print(f"goto {sys.argv[2]}: {'OK' if ok else 'FAIL'} (dang o {g.where()})")
        a.c.close()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
