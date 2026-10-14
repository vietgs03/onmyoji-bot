#!/usr/bin/env python3
"""ui_coords.py - Tra cuu FULL TOA DO nut UI tu data/ui_coords/.

Hai nguon (cung duc tu res.npk, khong can game chay):
  coords_all.jsonl  : 2.189 layout JSON (Cocos 1.x widgetTree), 22.178 nut
  coords_csb.jsonl  : 4.348 layout CSB full-screen (Cocos Studio 2.x FlatBuffers),
                      layout id dang 'csb:<id>'. Sinh bang research/fx/csb_index.py
Cong thuc: screen_x = canvas_x ; screen_y = 640 - canvas_y.

API:
  load()                      -> [dict] tat ca nut
  find(name=..., layout=..., feature=..., text=...)  -> [nut]
  by_feature('soul')          -> [nut] theo chuc nang
  by_layout('43447')          -> [nut] trong 1 layout
  screen(name, layout=None)   -> (x,y) cua nut

CLI:
  python automation/ui_coords.py --feature soul
  python automation/ui_coords.py --name guildBtn
  python automation/ui_coords.py --layout 43447
  python automation/ui_coords.py --stats
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "ui_coords", "coords_all.jsonl")
PATH_CSB = os.path.join(ROOT, "data", "ui_coords", "coords_csb.jsonl")
_C = None


def load(path=None):
    global _C
    if _C is None or path:
        rows = []
        for p in ([path] if path else [PATH, PATH_CSB]):
            if not os.path.exists(p):
                continue
            with open(p, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        _C = rows
    return _C


def find(name=None, layout=None, feature=None, text=None, man=None, touch_only=True):
    """Tra nut theo ten/layout/chuc nang/text/man. Khop chuoi con, khong phan biet hoa."""
    out = []
    for r in load():
        if touch_only and not r.get("touch") and r.get("class") != "Button":
            continue
        if name and name.lower() not in (r.get("name") or "").lower():
            continue
        if layout and str(r.get("layout")) != str(layout):
            continue
        if man and man.lower() not in (r.get("man") or "").lower():
            continue
        if feature and feature not in (r.get("features") or []):
            continue
        if text and text.lower() not in (r.get("text") or "").lower():
            continue
        out.append(r)
    return out


def by_feature(feat):
    return find(feature=feat)


def by_layout(idx):
    return find(layout=idx)


def screen(name, layout=None):
    """Toa do (x,y) cua nut dau tien khop ten (va layout neu co)."""
    hits = find(name=name, layout=layout)
    return tuple(hits[0]["screen"]) if hits else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name"); ap.add_argument("--layout"); ap.add_argument("--feature")
    ap.add_argument("--text"); ap.add_argument("--man")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()
    if a.stats:
        rows = load()
        import collections
        c = collections.Counter(ft for r in rows for ft in (r.get("features") or []))
        print(f"tong nut: {len(rows)}  |  layout: {len({r['layout'] for r in rows})}")
        for k, v in c.most_common():
            print(f"  {k:12s} {v}")
        return
    rows = find(a.name, a.layout, a.feature, a.text, a.man)
    print(f"{len(rows)} nut khop")
    for r in rows[: a.limit]:
        print(f"  {r['layout']:>10s} {str(r['name'])[:22]:22s} screen={str(r['screen']):12s} "
              f"{str(r['size']):12s} {(r.get('text') or '')[:12]:12s} {','.join(r.get('features') or [])}")


if __name__ == "__main__":
    main()
