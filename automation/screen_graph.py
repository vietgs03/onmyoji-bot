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
# ----------------------------------------------------------------------
# PHAN LOAI NODE (theo yeu cau user). Moi node mang 2 nhan de agent HIEU
# ban chat man, khong chi dieu huong mu:
#   kind     : khong gian hien thi
#       "flat"    = 1 frame chua TRON man (menu/battle/select) -> state = 1 anh.
#       "spatial" = khong gian RONG hon man, pan/scroll lo them (HOME courtyard,
#                   board game) -> can ghep panorama/mosaic, KHONG coi moi goc nhin
#                   la 1 state khac. (xem PROMPT_OPUS_BATTLE_GRAPH.md insight SLAM)
#   category : chuc nang -> giup agent gom nhom muc tieu, chon viec.
#       hub        : man trung chuyen (HOME/exploration/town) - chi de di tiep.
#       combat     : danh PvE farm (soul/boss/raid...).
#       pvp        : danh nguoi (duel/draft).
#       event      : su kien theo mua (heian/fairyland/hyakkiyakou).
#       util       : tien ich (shop/team/collection/settings/daily).
#       social     : xa hoi (friends/guild/mentor).
#       idle       : farm thu dong (delegation).
# verified : True = identify/toa do da kiem chung LIVE; False = suy tu OAS/ten game,
#            bot phai tu xac minh & sua khi toi noi (KHONG tin mu).
# ----------------------------------------------------------------------
NODES: dict[str, dict] = {
    "HOME": {
        # HOME dac trung: co dong thoi nhieu nut menu chinh + KHONG co nut Back.
        # spatial: courtyard rong hon man, pan lo Forum/Support... (da do dx=-285px).
        "kind": "spatial", "category": "hub", "verified": True,
        "identify": ["Explore", "Summon", "Friends", "Shikigami"],
        "avoid": ["Back"],
        "parent": None,
        "exits": {
            "exploration": {"text": ["Explore"],   "center": [608, 192]},
            "town":        {"text": ["Town"],       "center": [162, 602]},
            "summon":      {"text": ["Summon"],     "center": [991, 194]},
            # footer icons (y~600-630): NeoX KHONG nhan SendMessage o footer -> polite.
            # tap_text co the click trung label o cho khac -> bo text, dung center+polite.
            "shikigami":   {"center": [1011, 600], "polite": True},
            "onmyodo":     {"center": [881, 573]},
            "friends":     {"center": [813, 600],  "polite": True},
            "event":       {"text": ["Event"],      "center": [1078, 195]},
            "shop":        {"center": [613, 600],  "polite": True},
            "guild":       {"center": [520, 600],  "polite": True},
            # gear goc tren trai -> Settings; nut goc duoi -> Cosmetics (toa do tu world.json).
            "settings":    {"text": [],             "center": [59, 88]},
            "cosmetics":   {"text": [],             "center": [309, 628]},
        },
    },
    "exploration": {
        "kind": "flat", "category": "hub", "verified": True,
        # identify = nut footer DAC TRUNG cua man Explore (Dispatch/Totem/Venture chi
        # co o day). Tranh dung ten farm-mode (Realm/Soul...) vi node con cung mang ten
        # do -> de bi node con cuop nhan dien (xem bug bondling_fairyland 2026-06-04).
        "identify": ["Dispatch", "Totem", "Venture", "Realm", "Soul"],
        "parent": "HOME",
        "exits": {
            "realm_raid":   {"text": ["Realm"],  "center": [260, 621]},
            "soul_zones":   {"text": ["Soul"],   "center": [168, 620]},
            "area_boss":    {"text": ["Boss"],   "center": [599, 623]},
            "awake_zones":  {"text": ["Awake"],  "center": [80, 615]},
            "secret_zones": {"text": ["Secret"], "center": [518, 616]},
            "six_gates":    {"text": ["Gates"],  "center": [859, 623]},
            # --- canh bo sung tu OAS (chua kiem chung toa do -> bot tu tim qua OCR text) ---
            "goryou_realm": {"text": ["Goryou"]},
            "delegation":   {"text": ["Delegation"]},
            "heian_kitan":  {"text": ["Heian", "Strange"]},
            "bondling_fairyland": {"text": ["Fairyland", "Bondling"]},
            "hero_test":    {"text": ["Hero Trial", "Trial"]},
        },
    },
    "town": {
        # Town = co dong thoi nhieu nut hoat dong + KHONG co Back (la hub cap 1).
        "kind": "flat", "category": "hub", "verified": True,
        "identify": ["Arena", "Mystic Trader", "Demon Parade"],
        "avoid": ["Back"],
        "parent": "HOME",
        "exits": {
            "duel":            {"text": ["Duel"],      "center": [701, 166]},
            "demon_encounter": {"text": ["Encounter"], "center": [578, 162]},
            "hunt":            {"text": ["Hunt"],      "center": [448, 162]},
            "hyakkisen":       {"text": ["Hyakki"],    "center": [194, 168]},
            # --- canh bo sung tu OAS ---
            "hunt_kirin":      {"text": ["Kirin"]},
            "draft_duel":      {"text": ["Draft"]},
            "hyakkiyakou":     {"text": ["Yakou"]},
        },
    },
    # --- man con cap 1 (duoi HOME). verified=True = da kiem chung LIVE ---
    "summon":    {"kind": "flat", "category": "util", "verified": True,
                  "identify": ["Summon", "Scrolls"],   "parent": "HOME"},
    "shikigami": {"kind": "flat", "category": "util", "verified": True,
                  "identify": ["Shikigami", "Preset"], "parent": "HOME"},
    "onmyodo":   {"kind": "flat", "category": "util", "verified": True,
                  "identify": ["Onmyodo"],             "parent": "HOME"},
    # friends: tab ban be (Add Friend / Guild Invite / Recommended). Mentor la
    # tab ke ben (cung co Apprentices) -> phan biet bang nut dac trung friends.
    "friends":   {"kind": "flat", "category": "social", "verified": True,
                  # man Friends that: tab Friends/Latest, nut Add/Co-op/Page/Send,
                  # 'Friend Pts', 'Online', 'Group'. Tranh dung 'Friends' don (HOME
                  # footer cung co) -> dung to hop Co-op+Send+Online dac trung.
                  "identify": ["Co-op", "Friend Pts", "Send", "Online", "Latest"],
                  "parent": "HOME",
                  # Mentor (Mentorship) mo tu trong man Friends -> forward edge.
                  "exits": {"mentor": {"text": ["Mentorship"], "center": [928, 314]}}},
    "shop":      {"kind": "flat", "category": "util", "verified": True,
                  "identify": ["Garment", "Mall", "Stellar Omen", "Consignment", "General"],
                  "parent": "HOME"},
    # --- man tien ich / su kien (duoi HOME) ---
    # Event: banner su kien. 16 anh that = NHIEU sub-man (Event/Overview/Mileage/...)
    # -> identify rong de phu cac tab (Overview/Mileage/Benefits/Record tu OCR that).
    # Shrine Pass mo tu trong Event (banner goc duoi phai) -> forward edge.
    "event":     {"kind": "flat", "category": "event", "verified": True,
                  "identify": ["Version Event", "Memory Scroll", "Gilded Echoes",
                               "Overview", "Mileage", "Benefits", "Record"],
                  "parent": "HOME",
                  "exits": {"shrine_pass": {"text": ["Shrine"], "center": [955, 601]}}},
    # Settings: bang cai dat (Audio/Music/SFX/Nameplate). Mo tu gear goc HOME.
    "settings":  {"kind": "flat", "category": "util", "verified": True,
                  "identify": ["Settings", "Audio", "Nameplate", "Notif", "Music"],
                  "parent": "HOME"},
    # Guild: san guild (Guild Grounds, decorations). Nut Guild day HOME.
    "guild":     {"kind": "spatial", "category": "social", "verified": True,
                  "identify": ["Guild Grounds", "Guild Hall"], "parent": "HOME",
                  # Dokan (Ryou Dokan, dao quan dot pha) mo tu trong Guild.
                  "exits": {"dokan": {"text": ["Dokan"]}}},
    # Shrine Pass: battle pass (Mystic Scroll, Knowledge). Vao tu banner.
    "shrine_pass": {"kind": "flat", "category": "util", "verified": True,
                  "identify": ["Shrine Pass", "Mystic Scroll"], "parent": "event"},
    # Cosmetics: skin/frame shop (Cosmetic Scene/Skin/Frame). Tranh nham Shop.
    "cosmetics": {"kind": "flat", "category": "util", "verified": True,
                  "identify": ["Cosmetic", "Frame", "Ranking"],
                  "avoid": ["Garment"], "parent": "HOME"},
    # --- man con cap 2 (duoi exploration) ---
    "realm_raid":   {"kind": "flat", "category": "combat", "verified": True,
                     "identify": ["Realm Raid", "Assault"], "parent": "exploration",
                     "exits": {"kekkai_toppa": {"text": ["Kekkai", "Toppa"]}}},
    "soul_zones":   {"kind": "flat", "category": "combat", "verified": True,
                     "identify": ["Soul Zones", "Harvest"], "parent": "exploration"},
    "area_boss":    {"kind": "flat", "category": "combat", "verified": True,
                     "identify": ["Area Boss"],            "parent": "exploration"},
    "awake_zones":  {"kind": "flat", "category": "combat", "verified": True,
                     "identify": ["Awaken", "Awake"],      "parent": "exploration"},
    "secret_zones": {"kind": "flat", "category": "combat", "verified": True,
                     "identify": ["Secret Zone"],         "parent": "exploration"},
    "six_gates":    {"kind": "flat", "category": "combat", "verified": True,
                     "identify": ["Six Gates"],           "parent": "exploration"},
    # --- man con cap 2 (duoi town) ---
    "duel":            {"kind": "flat", "category": "pvp", "verified": True,
                        "identify": ["Duel", "Season"],     "parent": "town"},
    # demon_encounter: man trong; tranh nham voi nut "Demon Parade" cua Town
    # bang avoid cac nut hub Town (Arena/Mystic). Title that = "Demon Encounter".
    "demon_encounter": {"kind": "flat", "category": "combat", "verified": True,
                        "identify": ["Demon Encounter"],
                        "avoid": ["Arena", "Mystic Trader"], "parent": "town",
                        "exits": {"demon_encounter_realworld": {"text": ["Realworld", "Real World"]}}},
    "hunt":            {"kind": "flat", "category": "combat", "verified": True,
                        "identify": ["Hunt"],               "parent": "town"},
    "hyakkisen":       {"kind": "flat", "category": "combat", "verified": True,
                        "identify": ["Hyakki"],             "parent": "town"},
    # Mentor: tab su phu (Mentorship Channel/Notice, No Recommendation). Ke ben
    # tab Friends; phan biet bang avoid nut chi-Friends (Add Friend/Guild Invite).
    "mentor":          {"kind": "flat", "category": "social", "verified": True,
                        "identify": ["Mentorship", "Apprentices"],
                        "avoid": ["Add Friend", "Guild Invite"], "parent": "friends"},

    # ==================================================================
    # NODE BO SUNG tu OAS pagegraph (38 page). verified=False: identify suy
    # tu ten game EN/desc OAS, CHUA kiem chung LIVE -> bot tu xac minh khi toi
    # (cap nhat identify/them exits + dat verified=True sau khi thay that).
    # ==================================================================
    # -- combat farm (duoi exploration) --
    "goryou_realm":   {"kind": "flat", "category": "combat", "verified": False,
                       "identify": ["Goryou", "Spirit Beast"], "parent": "exploration"},
    "hero_test":      {"kind": "flat", "category": "combat", "verified": False,
                       "identify": ["Hero Trial", "Trial"], "parent": "exploration"},
    # Delegation = uy thac farm thu dong (idle).
    "delegation":     {"kind": "flat", "category": "idle", "verified": False,
                       "identify": ["Delegation", "Delegate"], "parent": "exploration"},
    # -- event (duoi exploration/town) --
    "heian_kitan":    {"kind": "flat", "category": "event", "verified": False,
                       "identify": ["Heian", "Strange Tales"], "parent": "exploration"},
    # Fairyland: vuon co tich, co the la man co khong gian (board) -> spatial?
    "bondling_fairyland": {"kind": "spatial", "category": "event", "verified": False,
                       "identify": ["Fairyland", "Bondling"], "parent": "exploration"},
    # Hyakki Yakou: dem tram quy = board game co ban do -> spatial.
    "hyakkiyakou":    {"kind": "spatial", "category": "event", "verified": False,
                       "identify": ["Hyakki Yakou", "Yakou"], "parent": "town"},
    # -- combat/pvp (duoi town) --
    "hunt_kirin":     {"kind": "flat", "category": "combat", "verified": False,
                       "identify": ["Kirin"], "parent": "town"},
    "draft_duel":     {"kind": "flat", "category": "pvp", "verified": False,
                       "identify": ["Draft Duel", "Draft"], "parent": "town"},
    # -- man con cap 3 --
    "kekkai_toppa":   {"kind": "flat", "category": "combat", "verified": False,
                       "identify": ["Kekkai Toppa", "Toppa"], "parent": "realm_raid"},
    "demon_encounter_realworld": {"kind": "flat", "category": "combat", "verified": False,
                       "identify": ["Realworld", "Real World"], "parent": "demon_encounter"},
    "dokan":          {"kind": "flat", "category": "combat", "verified": False,
                       "identify": ["Dokan", "Ryou Dokan"], "parent": "guild"},
    # -- tien ich (duoi HOME, mo tu footer) --
    "shikigami_records": {"kind": "flat", "category": "util", "verified": False,
                       "identify": ["Records", "Encounter Log"], "parent": "HOME"},
    "daily":          {"kind": "flat", "category": "util", "verified": False,
                       "identify": ["Daily Quests", "Quests"], "parent": "HOME"},
    "team":           {"kind": "flat", "category": "util", "verified": False,
                       "identify": ["Team", "Lineup"], "parent": "HOME"},
    "collection":     {"kind": "flat", "category": "util", "verified": False,
                       "identify": ["Collection"], "parent": "HOME"},
    "travel":         {"kind": "flat", "category": "util", "verified": False,
                       "identify": ["Traveler", "Travel"], "parent": "HOME"},
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
#   click@x,y : bam toa do co dinh (vd nut Confirm/X co hitbox lech, OCR khong bat).
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
    # Dialog 'Bonus ... Enable it again?' (pop khi vao battle sau bonus tat 15').
    # Confirm hitbox LECH @ (660,410) - OCR/dismiss thuong KHONG bat -> click toa do.
    # identify dung tu DON (OCR hay tach cum -> has() khop tung tu, tranh miss).
    # 'Enable' la tin hieu MANH cua dialog bonus (man khac hiem khi co tu nay).
    "bonus_enable":   {"identify": ["Enable"], "kind": "popup",
                       "resolve": "click@660,410"},
    # Popup event 'Parade Privilege' / 'Soul Zone Privileges' -> X dong @ (975,135).
    "parade_privilege":{"identify": ["Privilege", "Privileges"],
                       "kind": "popup", "resolve": "click@975,135"},
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

        Xep hang theo (hits, verified, depth):
          1) hits     : so identify khop (nhieu = chac hon).
          2) verified : node DA KIEM CHUNG LIVE thang node suy doan (verified=False).
             -> tranh bug node con verified=False (vd 'bondling_fairyland' co nut
             'Fairyland' o footer man cha) CUOP nhan dien cua man cha verified.
          3) depth    : bang nhau thi node SAU (con) thang (vao sau = cu the hon).
        """
        best = None          # (hits, verified, tiebreak, name)
        best_total = 1
        for name, d in table.items():
            ident = d.get("identify", [])
            if not ident or any(reader.has(w) for w in d.get("avoid", [])):
                continue                                    # khong co identify / bi avoid
            hits = sum(1 for w in ident if reader.has(w))
            if hits == 0:
                continue
            vflag = 1 if d.get("verified", True) else 0     # overlay khong co field -> coi nhu tin
            tie = depth_fn(name) if depth_fn else 0
            key = (hits, vflag, tie)
            if best is None or key > best[:3]:
                best, best_total = (hits, vflag, tie, name), len(ident)
        if best is None:
            return None, 0.0
        return best[3], best[0] / best_total

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
    def detect_overlay(self, reader=None, min_conf: float = 0.5) -> tuple[Optional[str], float]:
        """Tra (ten overlay, conf) neu man dang bi overlay/popup che, else (None,0).
        Mot so overlay (loading) KHONG co text dac trung -> dung detector rieng
        (dhash) khai bao qua field 'detector' thay vi OCR keyword.

        min_conf: nguong (so keyword khop / tong) de tin la overlay THAT. Mac dinh
        0.5 -> overlay nhieu keyword can >=1/2 khop (tranh false-positive nhu man
        Explore co 'Champion' lam khop le select_champion 1/3)."""
        r = reader if reader is not None else (self.a.read() if self.a else None)
        if r is None:
            return None, 0.0
        # 1) detector dac biet (vd loading qua dhash) - uu tien, chac hon OCR.
        if self.a is not None:
            for name, d in OVERLAYS.items():
                det = d.get("detector")
                if det == "loading" and self.a.is_loading_screen(r.img):
                    return name, 1.0
        # 2) OCR keyword - chi nhan khi conf >= min_conf (du keyword khop).
        name, conf = self._match(r, OVERLAYS)
        if name is not None and conf < min_conf:
            return None, 0.0
        return name, conf

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
        elif how.startswith("click@"):                  # bam toa do co dinh (hitbox lech)
            x, y = (int(v) for v in how[len("click@"):].split(","))
            self.a.click(x, y)
            self.a.wait_stable()
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
    def _go_edge(self, src: str, dst: str, retry: int = 0) -> None:
        """Di 1 hop src->dst. LUI -> dismiss; TIEN -> click theo OCR (fallback xy).
        KHONG kiem tra ket qua o day - goto() doc where() 1 lan/hop de re-plan.

        retry: so lan canh nay da FAIL lien tiep. retry>0 -> DOI cach click:
          - lan dau (retry=0): uu tien OCR text (ben voi event), fallback center.
          - retry>=1: OCR co the click trung text o cho khac (vd 'Friends' trong
            world-chat) -> uu tien CENTER (toa do footer co dinh) truoc.
        """
        if self._is_back_edge(src, dst):
            self.a.back()                                   # lui = dismiss (controls)
            return
        btn = self._exits(src).get(dst)
        if not btn:
            return
        center = btn.get("center")
        polite = btn.get("polite", False)               # nut footer NeoX can chuot that
        # retry>=1 & co toa do center -> click center truoc (OCR text co the lac).
        if retry >= 1 and center:
            self.a.click(*center, polite=polite)
            return
        # binh thuong: uu tien OCR text, fallback toa do center.
        for kw in btn.get("text", []):
            ok, _ = self.a.tap_text(kw)
            if ok:
                return
        if center:                                          # fallback toa do
            self.a.click(*center, polite=polite)

    def goto(self, target: str, max_hops: int = 12, verbose: bool = True,
             max_stuck: int = 3) -> bool:
        """Di toi `target` tu BAT KY dau. Re-plan moi hop (doc lai vi tri thuc).
        Moi hop: doc man 1 LAN -> (1) co overlay/popup? resolve roi tiep;
        (2) lac/nghi ngo? escape; (3) tinh Dijkstra, di 1 hop.

        HOC ONLINE: moi hop ta biet vi tri THUC sau hop truoc -> cham diem canh vua
        di (toi dung dst = success, khong = fail) + latency. Stats cap nhat -> lan
        sau Dijkstra ne canh hay fail / tuong chan. Tra True neu toi noi.

        PHAT HIEN KET (chong lap 12 lan vo ich): neu di 1 canh ma vi tri KHONG doi
        (cur == src cu) -> dem stuck. Lan stuck dau doi cach click (center). Sau
        `max_stuck` lan lien tiep tren CUNG canh -> tang cost manh + escape (re-plan
        duong khac). Het cach -> bo som thay vi lap het max_hops.
        """
        if target not in self.nodes:
            raise ValueError(f"node khong ton tai: {target}")

        pending = None      # (src, dst, t0) canh vua di, cho cham diem o hop sau
        stuck_edge = None   # (src, dst) canh dang ket
        stuck_n = 0         # so lan ket lien tiep tren canh do

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
                # PHAT HIEN KET: di canh src->dst nhung van o src (khong nhuc nhich).
                if not ok and cur == src:
                    if stuck_edge == (src, dst):
                        stuck_n += 1
                    else:
                        stuck_edge, stuck_n = (src, dst), 1
                    if verbose:
                        print(f"[goto]   canh {src}->{dst} KET lan {stuck_n} (van o '{cur}')")
                else:
                    stuck_edge, stuck_n = None, 0      # co tien trien -> reset
                    if verbose and not ok:
                        print(f"[goto]   canh {src}->{dst} lech (toi '{cur}') -> tang cost")
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

            nxt = p[1]
            # canh sap di dang KET qua nhieu lan -> phat cost nang + escape re-plan.
            if stuck_edge == (cur, nxt) and stuck_n >= max_stuck:
                if verbose:
                    print(f"[goto]   canh {cur}->{nxt} ket {stuck_n} lan -> phat cost + escape")
                for _ in range(5):                     # phat manh: ghi them fail
                    self.stats.record(cur, nxt, False, latency=0.0)
                stuck_edge, stuck_n = None, 0
                self.escape()
                continue

            pending = (p[0], nxt, time.time())         # nho de cham diem hop sau
            # neu canh nay dang ket -> doi cach click (retry>=1 dung center).
            retry = stuck_n if stuck_edge == (cur, nxt) else 0
            self._go_edge(p[0], nxt, retry=retry)

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
    """In cay node (parent -> con) kem PHAN LOAI (kind/category/verified)."""
    children = defaultdict(list)
    for n, d in NODES.items():
        children[d.get("parent")].append(n)

    def rec(node: str, depth: int) -> None:
        d = NODES.get(node, {})
        kind = d.get("kind", "?")[:4]
        cat = d.get("category", "?")
        vmark = "" if d.get("verified", False) else "  [chua kiem chung]"
        print("  " * depth + f"{node:24s} <{kind}|{cat}>{vmark}")
        for c in sorted(children.get(node, [])):
            rec(c, depth + 1)

    rec(HOME, 0)
    # thong ke phan loai
    from collections import Counter
    kc = Counter(d.get("kind", "?") for d in NODES.values())
    cc = Counter(d.get("category", "?") for d in NODES.values())
    nv = sum(1 for d in NODES.values() if not d.get("verified", False))
    print(f"\nTONG {len(NODES)} node | kind={dict(kc)} | category={dict(cc)} | chua kiem chung={nv}")


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
