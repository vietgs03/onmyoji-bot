#!/usr/bin/env python3
"""
navigator.py - Dieu huong THONG MINH bang PAGE-GRAPH (OAS) + DYNAMIC OCR.

Y tuong (hybrid senior):
  - PAGE-GRAPH (knowledge/oas_pagegraph.json, trich tu OAS) cho ta biet LUONG:
    page nao -> bam nut gi -> toi page nao. 38 page, 66 link.
  - Nhung toa do OAS la cua client TQ 1280x720 + co the lech khi event doi UI.
    -> Thay vi bam mu theo toa do, ta dung DYNAMIC OCR (ScreenReader) tim text
    EN cua nut tren man THUC roi bam. Ben voi event.
  - Toa do OAS (da scale 1152x679) chi dung lam FALLBACK khi OCR khong thay text.

Moi page co:
  - en_keywords: text EN de OCR nhan dien dang o page nao (va de tap_text).
  - link EN label: text hien tren nut de OCR bam.

Dung:
  from navigator import Navigator
  nav = Navigator(agent)
  nav.goto('realm_raid')   # tu dau cung ve duoc, qua cac page trung gian
"""
import os, json, time, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(ROOT, "knowledge", "oas_pagegraph.json")

# Map page OAS -> tu khoa EN (de OCR nhan dien + bam). Ta dat thu cong vi OAS
# description la tieng TQ. Chi can vai tu dac trung cho moi page.
# key = ten page bo tien to 'page_'. 'check' = text de biet dang o page nay.
# 'enter' = text EN tren nut de VAO page nay (tu page cha).
PAGE_EN = {
    "main":            {"check": ["Explore", "Summon"], "enter": []},
    "summon":          {"check": ["Summon", "Scrolls"], "enter": ["Summon"]},
    "exploration":     {"check": ["Chapter", "Soul", "Realm"], "enter": ["Explore"]},
    "town":            {"check": ["Encounter", "Arena", "Demon"], "enter": ["Town"]},
    "soul_zones":      {"check": ["Soul"], "enter": ["Soul"]},
    "realm_raid":      {"check": ["Realm Raid", "Assault"], "enter": ["Realm"]},
    "goryou_realm":    {"check": ["Goryou"], "enter": ["Goryou"]},
    "delegation":      {"check": ["Dispatch", "Delegat"], "enter": ["Dispatch"]},
    "secret_zones":    {"check": ["Secret"], "enter": ["Secret"]},
    "area_boss":       {"check": ["Area Boss"], "enter": ["Boss"]},
    "six_gates":       {"check": ["Six", "Gates"], "enter": ["Gates"]},
    "bondling_fairyland": {"check": ["Bondling", "Fairyland"], "enter": ["Bondling"]},
    "hero_test":       {"check": ["Hero"], "enter": ["Hero"]},
    "awake_zones":     {"check": ["Awake"], "enter": ["Awake"]},
    "duel":            {"check": ["Duel"], "enter": ["Duel"]},
    "demon_encounter": {"check": ["Encounter"], "enter": ["Encounter"]},
    "hunt":            {"check": ["Hunt"], "enter": ["Hunt"]},
    "hyakkisen":       {"check": ["Hyakki"], "enter": ["Hyakki"]},
    "shikigami_records": {"check": ["Shikigami", "Preset"], "enter": ["Shikigami"]},
    "onmyodo":         {"check": ["Onmyodo"], "enter": ["Onmyodo"]},
    "friends":         {"check": ["Friends", "Guild"], "enter": ["Friends"]},
    "daily":           {"check": ["Quest"], "enter": ["Bonus"]},
    "mall":            {"check": ["Shop", "Mall"], "enter": ["Shop"]},
    "guild":           {"check": ["Guild"], "enter": ["Guild"]},
    "team":            {"check": ["Team"], "enter": ["Team"]},
    "collection":      {"check": ["Collection"], "enter": ["Collection"]},
}


class Navigator:
    def __init__(self, agent):
        self.a = agent
        g = json.load(open(GRAPH))
        self.res_dst = g["resolution_dst"]
        self.pages = g["pages"]
        # do thi rut gon: short_name -> {dst_short: button}
        self.graph = {}
        for pn, p in self.pages.items():
            s = pn[5:] if pn.startswith("page_") else pn
            links = {}
            for dst, btn in p["links"].items():
                ds = dst[5:] if dst.startswith("page_") else dst
                links[ds] = btn
            self.graph[s] = links

    # ---------- nhan dien dang o page nao ----------
    def current(self, r=None):
        """Doan page hien tai bang OCR (text EN cua page). Tra short_name hoac None."""
        r = r or self.a.read()
        best, best_n = None, 0
        for short, en in PAGE_EN.items():
            hits = sum(1 for kw in en["check"] if r.has(kw))
            if hits > best_n:
                best_n, best = hits, short
        return best if best_n > 0 else None

    # ---------- BFS tim duong ----------
    def _path(self, start, goal):
        q = collections.deque([[start]])
        seen = {start}
        while q:
            path = q.popleft()
            if path[-1] == goal:
                return path
            for nxt in self.graph.get(path[-1], {}):
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(path + [nxt])
        return None

    # ---------- bam 1 buoc: uu tien OCR text, fallback toa do OAS ----------
    def _step(self, dst):
        """Di toi page dst tu page hien tai (1 hop). Tra True neu doi page."""
        # 1) thu OCR: bam text EN 'enter' cua page dich
        for kw in PAGE_EN.get(dst, {}).get("enter", []):
            ok, r = self.a.tap_text(kw)
            if ok:
                time.sleep(1.5)
                if self.current() == dst:
                    return True
        # 2) fallback: toa do OAS (da scale)
        btn = None
        cur = self.current()
        if cur and dst in self.graph.get(cur, {}):
            btn = self.graph[cur][dst]
        if btn and btn.get("center"):
            cx, cy = btn["center"]
            self.a.c.bgclick(cx, cy)
            time.sleep(1.8)
            return self.current() == dst
        return False

    # ---------- API chinh ----------
    def goto(self, target, max_hops=6):
        """Di toi page `target` (short name) tu dau cung duoc.
        Tu dong ve HOME truoc neu khong biet dang o dau, roi di theo duong ngan nhat."""
        target = target.replace("page_", "")
        cur = self.current()
        if cur == target:
            return True
        # neu khong biet dang o dau -> ve HOME
        if cur is None:
            self.a.back(home=True)
            cur = self.current() or "main"
        path = self._path(cur, target)
        if not path:
            # thu tu HOME
            self.a.back(home=True)
            path = self._path("main", target)
            if not path:
                return False
        for i in range(len(path) - 1):
            if not self._step(path[i+1]):
                # re-plan tu vi tri thuc
                cur2 = self.current()
                if cur2 == target:
                    return True
                np = self._path(cur2 or "main", target) if cur2 else None
                if not np:
                    return False
                path = path[:i+1] + np  # noi duong moi
        return self.current() == target


def main():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from agent import Agent
    a = Agent()
    nav = Navigator(a)
    if len(sys.argv) > 1 and sys.argv[1] == "where":
        print("dang o page:", nav.current())
    elif len(sys.argv) > 2 and sys.argv[1] == "goto":
        ok = nav.goto(sys.argv[2])
        print(f"goto {sys.argv[2]}: {'OK' if ok else 'FAIL'} (dang o {nav.current()})")
    a.c.close()


if __name__ == "__main__":
    main()
