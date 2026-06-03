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
import time
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
            "event":       {"text": ["Event"],      "center": [1078, 195]},
            "shop":        {"text": ["Shop"],       "center": [624, 625]},
            "guild":       {"text": ["Guild"],      "center": [525, 625]},
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
    # friends: tab ban be (Add Friend / Guild Invite / Recommended). Mentor la
    # tab ke ben (cung co Apprentices) -> phan biet bang nut dac trung friends.
    "friends":   {"identify": ["Add Friend", "Guild Invite", "Recommended"],
                  "parent": "HOME"},
    "shop":      {"identify": ["Garment", "Mall", "Stellar Omen", "Consignment", "General"],
                  "parent": "HOME"},
    # --- man tien ich / su kien (duoi HOME) ---
    # Event: banner su kien. 16 anh that = NHIEU sub-man (Event/Overview/Mileage/...)
    # -> identify rong de phu cac tab (Overview/Mileage/Benefits/Record tu OCR that).
    "event":     {"identify": ["Version Event", "Memory Scroll", "Gilded Echoes",
                               "Overview", "Mileage", "Benefits", "Record"],
                  "parent": "HOME"},
    # Settings: bang cai dat (Audio/Music/SFX/Nameplate). Mo tu gear goc HOME.
    "settings":  {"identify": ["Settings", "Audio", "Nameplate", "Notif", "Music"],
                  "parent": "HOME"},
    # Guild: san guild (Guild Grounds, decorations). Nut Guild day HOME.
    "guild":     {"identify": ["Guild Grounds", "Guild Hall"], "parent": "HOME"},
    # Shrine Pass: battle pass (Mystic Scroll, Knowledge). Vao tu banner.
    "shrine_pass": {"identify": ["Shrine Pass", "Mystic Scroll"], "parent": "HOME"},
    # Cosmetics: skin/frame shop (Cosmetic Scene/Skin/Frame). Tranh nham Shop.
    "cosmetics": {"identify": ["Cosmetic", "Frame", "Ranking"],
                  "avoid": ["Garment"], "parent": "HOME"},
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
    # Mentor: tab su phu (Mentorship Channel/Notice, No Recommendation). Ke ben
    # tab Friends; phan biet bang avoid nut chi-Friends (Add Friend/Guild Invite).
    "mentor":          {"identify": ["Mentorship", "Apprentices"],
                        "avoid": ["Add Friend", "Guild Invite"], "parent": "friends"},
}


# ======================================================================
# OVERLAYS: trang thai KHONG phai dich dieu huong, can RESOLVE (cho qua / thoat).
# Tach rieng NODES vi ban chat khac: ta khong "goto" toi overlay, ma phat hien
# roi xu ly. where() check overlay TRUOC node (overlay che node ben duoi).
#
# kind:
#   transient : man tam (Loading/Animation) -> CHO qua hoac Skip, khong dismiss.
#   popup     : cua so noi (Showcase/Group Buying) -> dismiss (back/X/Cancel).
# resolve:
#   wait      : doi wait_stable (loading).
#   skip      : OCR tim nut Skip roi bam.
#   dismiss   : controls.find_dismiss (back/X/Cancel).
# ======================================================================
OVERLAYS: dict[str, dict] = {
    "loading":   {"identify": ["Tap to"], "detector": "loading",
                  "kind": "transient", "resolve": "wait"},
    "animation": {"identify": ["Skip"],   "kind": "transient", "resolve": "skip"},
    # popup che man -> dismiss ve man duoi
    "char_showcase":  {"identify": ["Showcase", "Promote", "Liking"],
                       "kind": "popup", "resolve": "dismiss"},
    "group_buying":   {"identify": ["Group Buying"], "kind": "popup", "resolve": "dismiss"},
    "select_champion":{"identify": ["Offensive", "Support", "Champion"],
                       "kind": "popup", "resolve": "dismiss"},
    "create_float":   {"identify": ["Create Float", "Greeting"],
                       "kind": "popup", "resolve": "dismiss"},
    "cosmetic_quests":{"identify": ["Realm Skins", "Blossom"],
                       "kind": "popup", "resolve": "dismiss"},
}


class ScreenGraph:
    """Graph dieu huong. Toan bo logic qua Dijkstra/dismiss - khong if tung man.

    `agent` co the None (test offline cac thuat toan tinh: path/tree/where-voi-reader).
    """

    def __init__(self, agent=None, nodes: Optional[dict] = None, stats=None):
        self.a = agent
        self.nodes = nodes if nodes is not None else NODES
        # Kho thong ke canh (hoc online do tin cay). None -> tu tao.
        if stats is None:
            from edge_stats import EdgeStats
            stats = EdgeStats()
        self.stats = stats

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
    # NHAN DIEN: scan 1 bang (NODES hoac OVERLAYS) tim entry khop nhat.
    # confidence = (so identify khop) / (tong identify cua entry) -> [0,1].
    # ------------------------------------------------------------------
    @staticmethod
    def _match(reader, table: dict, depth_fn=None) -> tuple[Optional[str], float]:
        """Tra (ten, confidence) cua entry khop nhat trong `table`, hoac (None, 0).
        depth_fn(name)->int de tie-break (entry sau hon thang khi bang diem)."""
        best = None          # (hits, tiebreak, name)
        best_total = 1
        for name, d in table.items():
            ident = d.get("identify", [])
            if not ident or any(reader.has(w) for w in d.get("avoid", [])):
                continue                                    # khong co identify / bi avoid
            hits = sum(1 for w in ident if reader.has(w))
            if hits == 0:
                continue
            tie = depth_fn(name) if depth_fn else 0
            if best is None or (hits, tie) > best[:2]:
                best, best_total = (hits, tie, name), len(ident)
        if best is None:
            return None, 0.0
        return best[2], best[0] / best_total

    def where(self, reader=None) -> tuple[Optional[str], float]:
        """Node hien tai = node co diem khop cao nhat (tie-break: node con thang).
        Tra (None, 0.0) neu khong nhan dien. `reader`: ScreenReader san (tranh OCR lai).
        LUU Y: chi quet NODES (man dich). Overlay/popup dung detect_overlay().
        """
        r = reader if reader is not None else (self.a.read() if self.a else None)
        if r is None:
            return None, 0.0
        return self._match(r, self.nodes, self._depth)

    # ------------------------------------------------------------------
    # OVERLAY: trang thai tam/popup che man. Phat hien + xu ly rieng NODES.
    # ------------------------------------------------------------------
    def detect_overlay(self, reader=None) -> tuple[Optional[str], float]:
        """Tra (ten overlay, conf) neu man dang bi overlay/popup che, else (None,0).
        Mot so overlay (loading) KHONG co text dac trung -> dung detector rieng
        (dhash) khai bao qua field 'detector' thay vi OCR keyword."""
        r = reader if reader is not None else (self.a.read() if self.a else None)
        if r is None:
            return None, 0.0
        # 1) detector dac biet (vd loading qua dhash) - uu tien, chac hon OCR.
        if self.a is not None:
            for name, d in OVERLAYS.items():
                det = d.get("detector")
                if det == "loading" and self.a.is_loading_screen(r.img):
                    return name, 1.0
        # 2) OCR keyword nhu binh thuong.
        return self._match(r, OVERLAYS)

    def resolve_overlay(self, name: str) -> None:
        """Xu ly 1 overlay theo 'resolve' khai bao trong DATA (wait/skip/dismiss)."""
        if self.a is None:
            return
        how = OVERLAYS.get(name, {}).get("resolve", "dismiss")
        if how == "wait":
            self.a.wait_stable()                        # cho loading qua
        elif how == "skip":
            ok, _ = self.a.tap_text("Skip")
            if not ok:
                self.a.wait_stable()                    # khong co Skip -> cho
        else:                                           # dismiss (popup)
            self.a.back()

    # ------------------------------------------------------------------
    # TIM DUONG: Dijkstra tren do thi XAC SUAT (Stochastic Shortest Path).
    # Cost canh = cost tinh (base) + rui ro hoc duoc (-log P_success) + latency.
    # Canh bi CHAN (gated/het han) -> cost COST_CEIL (rat dat, chi di neu BAT BUOC).
    # -> Dijkstra TU NE tuong va chon duong tin cay nhat. base=1 + chua co data
    # -> ~ Dijkstra cu (tuong thich nguoc).
    # ------------------------------------------------------------------
    def _base_cost(self, src: str, dst: str, btn: Optional[dict]) -> float:
        if btn and "cost" in btn:
            return btn["cost"]
        return COST_BACK if self._is_back_edge(src, dst) else COST_DEFAULT

    def _edge_cost(self, src: str, dst: str, btn: Optional[dict]) -> float:
        """Cost cuoi = base dieu chinh boi thong ke hoc duoc (do tin cay/latency)."""
        return self.stats.learned_cost(src, dst, self._base_cost(src, dst, btn))

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
        Moi hop: doc man 1 LAN -> (1) co overlay/popup? resolve roi tiep;
        (2) lac/nghi ngo? escape; (3) tinh Dijkstra, di 1 hop.

        HOC ONLINE: moi hop ta biet vi tri THUC sau hop truoc -> cham diem canh vua
        di (toi dung dst = success, khong = fail) + latency. Stats cap nhat -> lan
        sau Dijkstra ne canh hay fail / tuong chan. Tra True neu toi noi.
        """
        if target not in self.nodes:
            raise ValueError(f"node khong ton tai: {target}")

        pending = None      # (src, dst, t0) canh vua di, cho cham diem o hop sau

        for hop in range(max_hops):
            r = self.a.read() if self.a else None      # doc 1 lan, dung lai cho ca 2 check

            ov, ovc = self.detect_overlay(reader=r)
            if ov:                                     # overlay che man -> xu ly truoc
                if verbose:
                    print(f"[goto] hop {hop}: overlay '{ov}' (conf {ovc:.2f}) -> resolve")
                self.resolve_overlay(ov)
                continue                               # khong tinh la hop dieu huong

            cur, conf = self.where(reader=r)

            # cham diem canh da di o hop truoc (biet vi tri thuc bay gio = cur)
            if pending is not None:
                src, dst, t0 = pending
                ok = (cur == dst)
                self.stats.record(src, dst, ok, latency=time.time() - t0)
                if verbose and not ok:
                    print(f"[goto]   canh {src}->{dst} FAIL (toi '{cur}') -> tang cost")
                pending = None

            if verbose:
                print(f"[goto] hop {hop}: o '{cur}' (conf {conf:.2f}) -> '{target}'")
            if cur == target:
                self.stats.save()
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

            pending = (p[0], p[1], time.time())        # nho de cham diem hop sau
            self._go_edge(p[0], p[1])

        # het hop: cham diem canh cuoi + ket luan
        final = self.where()[0]
        if pending is not None:
            src, dst, t0 = pending
            self.stats.record(src, dst, final == dst, latency=time.time() - t0)
        self.stats.save()
        return final == target

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
