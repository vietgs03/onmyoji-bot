#!/usr/bin/env python3
"""
ui_lookup.py - Tra cuu UI layout goc cua game -> toa do click chinh xac.

Du lieu: knowledge/ui_layouts.json (toa do chuan-hoa 0..1, da flip-Y ve goc tren-trai).
Map sang client bang: px = cx_norm * client_w, py = cy_norm * client_h.

Dung trong code:
  from knowledge.ui_lookup import UILookup
  ui = UILookup(client_w=1152, client_h=679)
  ui.find("auto")                 # tim button theo ten -> [(panel, name, px, py, img)]
  ui.panel_buttons("combat")      # liet ke button cua panel co texture chua 'combat'
  ui.click_point("button_auto")   # toa do trung binh cua button ten do

CLI:
  python knowledge/ui_lookup.py find auto
  python knowledge/ui_lookup.py panel combat
"""
import os, sys, json
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "ui_layouts.json")


class UILookup:
    def __init__(self, client_w=1152, client_h=679, data=DATA):
        self.w, self.h = client_w, client_h
        self.panels = json.load(open(data, encoding="utf-8"))
        # index ten button -> list (panel_file, button)
        self.by_name = defaultdict(list)
        for p in self.panels:
            tex = p.get("textures", [])
            for b in p["buttons"]:
                if b.get("name"):
                    self.by_name[b["name"].lower()].append((p["file"], tex, b))

    def _px(self, b):
        return int(round(b["cx_norm"] * self.w)), int(round(b["cy_norm"] * self.h))

    def find(self, query, only_button=True):
        """Tim button co ten chua query."""
        q = query.lower()
        res = []
        for name, lst in self.by_name.items():
            if q in name:
                for pfile, tex, b in lst:
                    if only_button and b.get("class") != "Button":
                        continue
                    px, py = self._px(b)
                    res.append({
                        "panel": pfile, "name": b["name"], "class": b["class"],
                        "px": px, "py": py, "img": b.get("img"),
                        "texture": tex[0] if tex else None,
                    })
        return res

    def click_point(self, name):
        """Toa do trung binh (px,py) cua button ten chinh xac (gop moi panel)."""
        lst = self.by_name.get(name.lower(), [])
        pts = [self._px(b) for _, _, b in lst if b.get("class") == "Button"]
        if not pts:
            return None
        return (sum(p[0] for p in pts) // len(pts), sum(p[1] for p in pts) // len(pts))

    def panel_buttons(self, texture_substr):
        """Liet ke button cua panel co texture chua substr (vd 'combat','summon')."""
        s = texture_substr.lower()
        res = []
        for p in self.panels:
            if any(s in t.lower() for t in p.get("textures", [])):
                for b in p["buttons"]:
                    if b.get("class") == "Button" and b.get("name"):
                        px, py = self._px(b)
                        res.append({"panel": p["file"], "name": b["name"],
                                    "px": px, "py": py, "img": b.get("img")})
        return res


def main():
    ui = UILookup()
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, arg = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
    if cmd == "find":
        for r in ui.find(arg):
            print(f"  {r['name']:24s} ({r['px']:4d},{r['py']:4d}) "
                  f"tex={r['texture']} img={r['img']}")
    elif cmd == "panel":
        for r in ui.panel_buttons(arg):
            print(f"  {r['name']:24s} ({r['px']:4d},{r['py']:4d}) img={r['img']}")
    elif cmd == "point":
        print(ui.click_point(arg))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
