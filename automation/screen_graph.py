#!/usr/bin/env python3
"""
screen_graph.py - GRAPH DIEU HUONG hop nhat (nguon su that DUY NHAT).

Triet ly (xem docs/navigation_architecture.md): moi MAN = 1 NODE khai bao trong
DATA, moi logic dieu huong dung THUAT TOAN CHUNG - KHONG if long vong tung man.
Them man moi = them 1 entry DATA, khong dung den thuat toan.

Moi NODE (xem NODES ben duoi):
  identify : [tu khoa OCR] de nhan dien dang o man nay (CO mat = +1 diem)
  avoid    : [tu khoa] neu co thi LOAI node nay (chong nham, vd HOME khong co 'Back')
  exits    : { man_dich : {text:[OCR keywords], center:[x,y], cost:float} }
  parent   : man cha (canh LUI = dismiss; de escape + kiem tra cay)

API CHUNG (khong phu thuoc so node):
  where(reader)      -> (node, confidence) hoac (None, 0.0)
  path(start, goal)  -> [node,...]  (Dijkstra: duong RE & CHAC nhat)
  goto(target)       -> bool        (di tung hop, re-plan khi drift)
  escape()           -> node        (dismiss lien tuc ve HOME)

CLI:  python screen_graph.py {build|tree|path A B|where|goto X}
"""
from __future__ import annotations

import heapq
import json
import os
import sys
from collections import defaultdict
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH_JSON = os.path.join(ROOT, "knowledge", "screen_graph.json")

HOME = "HOME"

# Chi phi canh mac dinh. Canh cang dat -> Dijkstra cang tranh.
COST_DEFAULT = 1.0
COST_BACK = 1.5     # canh LUI (dismiss) hoi dat: de gap popup, kem chac hon tien

# Diem tin cay toi thieu de coi where() la "chac". Duoi nguong -> goto nghi ngo,
# uu tien escape ve HOME roi di lai cho an toan.
CONF_MIN = 0.5


# ======================================================================
# DATA: khai bao NODE. Day la NGUON SU THAT. Them man = them o day.
# Toa do center la fallback 1152x679; uu tien click theo OCR text (ben voi event).
# ======================================================================
NODES: dict[str, dict] = {
    "HOME": {
        # HOME dac trung: co dong thoi nhieu nut menu chinh + KHONG co nut Back.
        "identify": ["Explore", "Summon", "Friends", "Shikigami"],
        "avoid": ["Back"],
        "parent": None,
        "exits": {
            "exploration": {"text": ["Explore"],   "center": [464, 144]},
            "town":        {"text": ["Town"],       "center": [662, 262]},
            "summon":      {"text": ["Summon"],     "center": [991, 194]},
            "shikigami":   {"text": ["Shikigami"],  "center": [997, 586]},
            "onmyodo":     {"text": ["Onmyodo"],    "center": [881, 573]},
            "friends":     {"text": ["Friends"],    "center": [785, 582]},
        },
    },
    "exploration": {
        "identify": ["Chapter", "Realm Raid", "Soul Zones"],
        "parent": "HOME",
        "exits": {
            "realm_raid":   {"text": ["Realm"],  "center": [260, 621]},
            "soul_zones":   {"text": ["Soul"],   "center": [168, 620]},
            "area_boss":    {"text": ["Boss"],   "center": [599, 623]},
            "awake_zones":  {"text": ["Awake"],  "center": [80, 615]},
            "secret_zones": {"text": ["Secret"], "center": [518, 616]},
            "six_gates":    {"text": ["Gates"],  "center": [859, 623]},
        },
    },
    "town": {
        # Town = co dong thoi nhieu nut hoat dong + KHONG co Back (la hub cap 1).
        "identify": ["Arena", "Mystic Trader", "Demon Parade"],
        "avoid": ["Back"],
        "parent": "HOME",
        "exits": {
            "duel":            {"text": ["Duel"],      "center": [701, 166]},
            "demon_encounter": {"text": ["Encounter"], "center": [578, 162]},
            "hunt":            {"text": ["Hunt"],      "center": [448, 162]},
            "hyakkisen":       {"text": ["Hyakki"],    "center": [194, 168]},
        },
    },
    # --- man con cap 1 (duoi HOME) ---
    "summon":    {"identify": ["Summon", "Scrolls"],   "parent": "HOME"},
    "shikigami": {"identify": ["Shikigami", "Preset"], "parent": "HOME"},
    "onmyodo":   {"identify": ["Onmyodo"],             "parent": "HOME"},
    "friends":   {"identify": ["Friends", "Guild"],    "parent": "HOME"},
    "shop":      {"identify": ["Garment", "Mall", "Stellar Omen"], "parent": "HOME"},
    # --- man con cap 2 (duoi exploration) ---
    "realm_raid":   {"identify": ["Realm Raid", "Assault"], "parent": "exploration"},
    "soul_zones":   {"identify": ["Soul Zones", "Harvest"], "parent": "exploration"},
    "area_boss":    {"identify": ["Area Boss"],            "parent": "exploration"},
    "awake_zones":  {"identify": ["Awaken", "Awake"],      "parent": "exploration"},
    "secret_zones": {"identify": ["Secret Zone"],         "parent": "exploration"},
    "six_gates":    {"identify": ["Six Gates"],           "parent": "exploration"},
    # --- man con cap 2 (duoi town) ---
    "duel":            {"identify": ["Duel", "Season"],     "parent": "town"},
    # demon_encounter: man trong; tranh nham voi nut "Demon Parade" cua Town
    # bang avoid cac nut hub Town (Arena/Mystic). Title that = "Demon Encounter".
    "demon_encounter": {"identify": ["Demon Encounter"],
                        "avoid": ["Arena", "Mystic Trader"], "parent": "town"},
    "hunt":            {"identify": ["Hunt"],               "parent": "town"},
    "hyakkisen":       {"identify": ["Hyakki"],             "parent": "town"},
}


class ScreenGraph:
    """Graph dieu huong. Toan bo logic qua Dijkstra/dismiss - khong if tung man.

    `agent` co the None (test offline cac thuat toan tinh: path/tree/where-voi-reader).
    """

    def __init__(self, agent=None, nodes: Optional[dict] = None):
        self.a = agent
        self.nodes = nodes if nodes is not None else NODES

    # ------------------------------------------------------------------
    # Tien ich cau truc cay
    # ------------------------------------------------------------------
    def _parent(self, name: str) -> Optional[str]:
        return self.nodes.get(name, {}).get("parent")

    def _exits(self, name: str) -> dict:
        return self.nodes.get(name, {}).get("exits", {})

    def _is_back_edge(self, src: str, dst: str) -> bool:
        """dst la canh LUI cua src (ve parent, khong phai exit tien)."""
        return dst == self._parent(src) and dst not in self._exits(src)

    def _depth(self, name: str) -> int:
        """Do sau (HOME=0). Dung tie-break where(): man con uu tien man cha."""
        d, cur, seen = 0, name, set()
        while cur and self._parent(cur) and cur not in seen:
            seen.add(cur)
            cur = self._parent(cur)
            d += 1
        return d

    # ------------------------------------------------------------------
    # NHAN DIEN: 1 ham chung quet moi node. Tra (node, confidence in [0,1]).
    # confidence = (so identify khop) / (tong identify cua node) -> [0,1].
    # ------------------------------------------------------------------
    def where(self, reader=None) -> tuple[Optional[str], float]:
        """Node hien tai = node co diem khop cao nhat.

        Diem 1 node = so tu khoa identify xuat hien tren man. avoid co mat -> loai.
        Tie-break khi bang diem: node SAU hon (con) thang (vd man Summon co chu
        'Summon' nhung khong phai HOME). Tra (None, 0.0) neu khong nhan dien duoc.

        `reader`: ScreenReader da co (tranh OCR lai). None -> tu doc tu agent.
        """
        r = reader if reader is not None else (self.a.read() if self.a else None)
        if r is None:
            return None, 0.0

        best = None          # (hits, depth, name)
        best_total = 1
        for name, d in self.nodes.items():
            ident = d.get("identify", [])
            if not ident:
                continue
            if any(r.has(w) for w in d.get("avoid", [])):
                continue                                    # bi loai boi avoid
            hits = sum(1 for w in ident if r.has(w))
            if hits == 0:
                continue
            key = (hits, self._depth(name))
            if best is None or key > best[:2]:
                best, best_total = (hits, self._depth(name), name), len(ident)
        if best is None:
            return None, 0.0
        return best[2], best[0] / best_total

    # ------------------------------------------------------------------
    # TIM DUONG: Dijkstra trong so = chi phi/do tin cay canh.
    # Vi sao Dijkstra (khong chi BFS): cac canh KHONG bang nhau - nut nho hay
    # truot OCR thi dat; canh lui de gap popup thi dat. Cost=1 deu -> == BFS.
    # ------------------------------------------------------------------
    def _edge_cost(self, src: str, dst: str, btn: Optional[dict]) -> float:
        if btn and "cost" in btn:
            return btn["cost"]
        return COST_BACK if self._is_back_edge(src, dst) else COST_DEFAULT

    def _neighbors(self, name: str) -> dict:
        """Canh tien (exits) + canh LUI (ve parent). Tra {dst: btn|None}."""
        nb = dict(self._exits(name))
        par = self._parent(name)
        if par and par not in nb:
            nb[par] = None                                  # canh lui = dismiss
        return nb

    def path(self, start: str, goal: str) -> Optional[list[str]]:
        """Duong RE NHAT start->goal (Dijkstra). None neu khong toi duoc."""
        if start == goal:
            return [start]
        pq: list[tuple[float, str, list[str]]] = [(0.0, start, [start])]
        best_cost = {start: 0.0}
        while pq:
            cost, cur, p = heapq.heappop(pq)
            if cur == goal:
                return p
            if cost > best_cost.get(cur, float("inf")):
                continue
            for nxt, btn in self._neighbors(cur).items():
                nc = cost + self._edge_cost(cur, nxt, btn)
                if nc < best_cost.get(nxt, float("inf")):
                    best_cost[nxt] = nc
                    heapq.heappush(pq, (nc, nxt, p + [nxt]))
        return None

    # ------------------------------------------------------------------
    # THAO TAC: dung lop chung (controls/ocr/wait). 1 hop = 1 lan doc lai.
    # ------------------------------------------------------------------
    def _go_edge(self, src: str, dst: str) -> None:
        """Di 1 hop src->dst. LUI -> dismiss; TIEN -> click theo OCR (fallback xy).
        KHONG kiem tra ket qua o day - goto() doc where() 1 lan/hop de re-plan.
        """
        if self._is_back_edge(src, dst):
            self.a.back()                                   # lui = dismiss (controls)
            return
        btn = self._exits(src).get(dst)
        if not btn:
            return
        # uu tien OCR text (ben voi event); chi click 1 nut tim thay dau tien.
        for kw in btn.get("text", []):
            ok, _ = self.a.tap_text(kw)
            if ok:
                return
        if btn.get("center"):                               # fallback toa do
            self.a.click(*btn["center"])

    def goto(self, target: str, max_hops: int = 12, verbose: bool = True) -> bool:
        """Di toi `target` tu BAT KY dau. Re-plan moi hop (doc lai vi tri thuc).
        Tu phuc hoi: khi lac (where None / conf thap / khong co duong) -> escape
        ve HOME roi di lai. Tra True neu toi noi.
        """
        if target not in self.nodes:
            raise ValueError(f"node khong ton tai: {target}")

        for hop in range(max_hops):
            cur, conf = self.where()
            if verbose:
                print(f"[goto] hop {hop}: o '{cur}' (conf {conf:.2f}) -> '{target}'")
            if cur == target:
                return True

            # lac duong: khong ro vi tri, hoac qua nghi ngo -> ve HOME lam moc.
            if cur is None or conf < CONF_MIN:
                if verbose:
                    print("[goto] lac/nghi ngo -> escape ve HOME")
                self.escape()
                continue

            p = self.path(cur, target)
            if not p or len(p) < 2:
                if verbose:
                    print(f"[goto] khong co duong {cur}->{target} -> escape")
                self.escape()
                continue

            self._go_edge(p[0], p[1])
        # het hop: kiem tra lan cuoi
        return self.where()[0] == target

    def escape(self, max_steps: int = 8) -> Optional[str]:
        """Dismiss lien tuc ve HOME (Agent.back home=True lo nhieu lop/tab)."""
        if self.a is not None:
            self.a.back(home=True)
        return self.where()[0]


# ======================================================================
# VALIDATION + BUILD (1 cho duy nhat - test_screen_graph.py import lai)
# ======================================================================
def validate(nodes: dict = NODES) -> list[str]:
    """Kiem tra cay hop le. Tra list loi (rong = OK)."""
    errs = []
    for n, d in nodes.items():
        par = d.get("parent")
        if par and par not in nodes:
            errs.append(f"{n}: parent '{par}' khong ton tai")
        # phat hien vong cha
        seen, cur = set(), n
        while cur:
            if cur in seen:
                errs.append(f"{n}: vong parent")
                break
            seen.add(cur)
            cur = nodes.get(cur, {}).get("parent")
        for dst in d.get("exits", {}):
            if dst not in nodes:
                errs.append(f"{n}: exit '{dst}' khong ton tai")
    if HOME not in nodes:
        errs.append(f"thieu node goc '{HOME}'")
    return errs


def build() -> None:
    """Xuat DATA ra JSON (cho cong cu khac) + bao cao tinh hop le cua cay."""
    errs = validate()
    json.dump({"home": HOME, "nodes": NODES}, open(GRAPH_JSON, "w"),
              indent=1, ensure_ascii=False)
    print(f"luu {GRAPH_JSON}: {len(NODES)} node")
    if errs:
        print("LOI cay:")
        for e in errs:
            print("  ", e)
    else:
        print("cay HOP LE (moi parent/exit ton tai, khong vong)")


def show_tree() -> None:
    """In cay node (parent -> con) de de doi chieu, khong lan man."""
    children = defaultdict(list)
    for n, d in NODES.items():
        children[d.get("parent")].append(n)

    def rec(node: str, depth: int) -> None:
        print("  " * depth + node)
        for c in sorted(children.get(node, [])):
            rec(c, depth + 1)

    rec(HOME, 0)


def _make_agent():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from agent import Agent
    return Agent()


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "tree":
        show_tree()
    elif cmd == "path":
        p = ScreenGraph().path(sys.argv[2], sys.argv[3])
        print(" -> ".join(p) if p else "KHONG CO DUONG")
    elif cmd == "where":
        a = _make_agent()
        try:
            node, conf = ScreenGraph(a).where()
            print(f"dang o: {node} (conf {conf:.2f})")
        finally:
            a.c.close()
    elif cmd == "goto":
        a = _make_agent()
        try:
            g = ScreenGraph(a)
            ok = g.goto(sys.argv[2])
            print(f"goto {sys.argv[2]}: {'OK' if ok else 'FAIL'} (o {g.where()[0]})")
        finally:
            a.c.close()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
