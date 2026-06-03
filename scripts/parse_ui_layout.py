#!/usr/bin/env python3
"""
parse_ui_layout.py - Trich UI LAYOUT goc cua game tu res.npk (CocoStudio widgetTree).

res.npk chua 2184 file UI layout: moi file la 1 panel/man hinh voi cay widget
(Button/Label/ImageView...) kem TOA DO chinh xac (designWidth 1136 x designHeight 640).
Day la "ban thiet ke UI goc" -> bot biet chinh xac nut nao o dau, ten gi, anh gi.

Quan trong: toa do la he 1136x640 (goc duoi-trai, CocoStudio). Client Steam cua ban
1152x679 -> can scale + flip Y khi dung. Script nay chi TRICH; viec map sang toa do
man hinh thuc lam khi co screenshot.

Ra: knowledge/ui_layouts.json  (list panel -> widgets[name,class,x,y,w,h,image])

Dung:
  python parse_ui_layout.py <thumuc_json_da_extract>   # vd /tmp/res_json/json
"""
import os, sys, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "knowledge", "ui_layouts.json")

# class widget dang chu y (tuong tac)
INTERACTIVE = {"Button", "CheckBox", "Slider", "ListView", "ScrollView"}


def widget_info(node):
    o = node.get("options", {})
    cls = node.get("classname") or o.get("classname")
    name = o.get("name") or node.get("name")
    info = {
        "class": cls,
        "name": name,
        "x": o.get("x") or o.get("positionX"),
        "y": o.get("y") or o.get("positionY"),
        "w": o.get("width") or o.get("scaleWidth"),
        "h": o.get("height") or o.get("scaleHeight"),
    }
    # anh dai dien
    nd = o.get("normalData") or {}
    if nd.get("path"):
        info["image"] = nd["path"]
    fd = o.get("fileNameData") or o.get("fileData") or {}
    if isinstance(fd, dict) and fd.get("path"):
        info["image"] = fd["path"]
    # text label
    if o.get("text"):
        info["text"] = o["text"]
    return info


def flatten(node, out, panel_name=None):
    info = widget_info(node)
    if info.get("class"):
        out.append(info)
    for c in node.get("children", []):
        flatten(c, out, panel_name)


def parse_file(path):
    try:
        d = json.load(open(path))
    except Exception:
        return None
    if not isinstance(d, dict) or "widgetTree" not in d:
        return None
    widgets = []
    flatten(d["widgetTree"], widgets)
    # chi giu cac widget co ten (co y nghia)
    named = [w for w in widgets if w.get("name")]
    interactive = [w for w in named if w["class"] in INTERACTIVE]
    return {
        "file": os.path.basename(path),
        "designW": d.get("designWidth"),
        "designH": d.get("designHeight"),
        "textures": d.get("textures", []),
        "n_widgets": len(widgets),
        "interactive": interactive,
        "named_widgets": named,
    }


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/res_json/json"
    files = glob.glob(os.path.join(src, "*.json"))
    print(f"quet {len(files)} json...")
    out = []
    for f in files:
        r = parse_file(f)
        if r and r["named_widgets"]:
            out.append(r)
    # de-dup theo (textures + n_widgets) - res.npk thuong co ban CN va EN trung
    out.sort(key=lambda z: -z["n_widgets"])
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_btn = sum(len(r["interactive"]) for r in out)
    print(f"trich {len(out)} UI panel, {n_btn} widget tuong tac co ten -> {OUT}\n")
    for r in out[:12]:
        names = ", ".join(w["name"] for w in r["interactive"][:5])
        print(f"  {r['file']} [{r['designW']}x{r['designH']}] "
              f"{len(r['interactive'])} btn: {names}  tex={r['textures'][:1]}")


if __name__ == "__main__":
    main()
