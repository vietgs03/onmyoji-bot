#!/usr/bin/env python3
"""
parse_ui_layout.py - Trich UI LAYOUT goc cua game tu res.npk (CocoStudio widgetTree).

CocoStudio: moi widget co (x,y) tuong doi voi CHA + anchorPoint + scale.
Goc toa do CocoStudio = duoi-trai (y len tren). Client Steam = tren-trai (y xuong).

Script nay:
  1. Duyet cay widget, CONG DON toa do cha -> toa do TUYET DOI trong canvas designW x designH.
  2. Tinh CENTER cua moi widget (de click).
  3. Flip Y: y_top = designH - y_bottom  -> he tren-trai chuan man hinh.
  4. Xuat ca toa do chuan-hoa (cx_norm, cy_norm in [0,1]) -> map sang BAT KY do phan giai
     client bang cach nhan voi (client_w, client_h). KHONG phu thuoc res cu the.

Ra: knowledge/ui_layouts.json
  panel -> buttons[{name, class, cx_norm, cy_norm, w_norm, h_norm, img, text}]

Dung: python parse_ui_layout.py <thumuc_json_da_extract>
"""
import os, sys, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "knowledge", "ui_layouts.json")

INTERACTIVE = {"Button", "CheckBox", "Slider", "ListView", "ScrollView", "ImageView"}


def _f(o, *keys, default=0.0):
    for k in keys:
        v = o.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return default


def _img(o):
    for key in ("normalData", "fileNameData", "fileData", "backGroundImageData"):
        d = o.get(key)
        if isinstance(d, dict) and d.get("path"):
            return d["path"]
    return None


def walk(node, parent_x, parent_y, parent_sx, parent_sy, design_w, design_h, out):
    """Cong don toa do; (parent_x,parent_y) = goc duoi-trai cua vung cha (absolute)."""
    o = node.get("options", {})
    cls = node.get("classname") or o.get("classname")

    x = _f(o, "x", "positionX")
    y = _f(o, "y", "positionY")
    w = _f(o, "width")
    h = _f(o, "height")
    ax = _f(o, "anchorPointX")
    ay = _f(o, "anchorPointY")
    sx = _f(o, "scaleX", default=1.0) or 1.0
    sy = _f(o, "scaleY", default=1.0) or 1.0

    # vi tri absolute cua goc duoi-trai widget = cha + offset*scale_cha
    abs_x = parent_x + x * parent_sx
    abs_y = parent_y + y * parent_sy
    eff_w = w * parent_sx * sx
    eff_h = h * parent_sy * sy

    # widget chiem [abs_x - ax*eff_w, abs_x - ax*eff_w + eff_w]
    left = abs_x - ax * eff_w
    bottom = abs_y - ay * eff_h
    cx = left + eff_w / 2.0
    cy_bottom = bottom + eff_h / 2.0  # tu goc duoi
    cy_top = design_h - cy_bottom     # flip sang goc tren-trai

    name = o.get("name") or node.get("name")
    if cls in INTERACTIVE and name and design_w and design_h:
        out.append({
            "name": name,
            "class": cls,
            "cx_norm": round(cx / design_w, 4),
            "cy_norm": round(cy_top / design_h, 4),
            "w_norm": round(eff_w / design_w, 4),
            "h_norm": round(eff_h / design_h, 4),
            "img": _img(o),
            "text": o.get("text") or None,
        })

    # con: goc cua chung tinh tu (left, bottom) cua widget nay
    for c in node.get("children", []):
        walk(c, left, bottom, parent_sx * sx, parent_sy * sy, design_w, design_h, out)


def parse_file(path):
    try:
        d = json.load(open(path))
    except Exception:
        return None
    if not isinstance(d, dict) or "widgetTree" not in d:
        return None
    dw = d.get("designWidth") or 1136
    dh = d.get("designHeight") or 640
    out = []
    walk(d["widgetTree"], 0.0, 0.0, 1.0, 1.0, dw, dh, out)
    # chi giu trong khung [0,1] (loai widget an / scroll content ngoai man)
    out = [b for b in out if -0.05 <= b["cx_norm"] <= 1.05 and -0.05 <= b["cy_norm"] <= 1.05]
    if not out:
        return None
    return {
        "file": os.path.basename(path),
        "designW": dw, "designH": dh,
        "textures": d.get("textures", []),
        "n_btn": len(out),
        "buttons": out,
    }


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/uijson/json"
    files = glob.glob(os.path.join(src, "*.json"))
    print(f"quet {len(files)} json...")
    out = [r for f in files if (r := parse_file(f))]

    # de-dup: panel CN va EN trung textures+layout -> giu ban co 'en' trong textures
    seen = {}
    for r in out:
        key = (tuple(sorted(t for t in r["textures"] if "en" not in t.lower())), r["n_btn"])
        prev = seen.get(key)
        has_en = any("en" in t.lower() for t in r["textures"])
        if prev is None or (has_en and not any("en" in t.lower() for t in prev["textures"])):
            seen[key] = r
    out = sorted(seen.values(), key=lambda z: -z["n_btn"])

    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_btn = sum(r["n_btn"] for r in out)
    print(f"trich {len(out)} panel, {n_btn} button (toa do chuan-hoa 0..1) -> {OUT}\n")
    for r in out[:10]:
        names = ", ".join(f"{b['name']}({b['cx_norm']},{b['cy_norm']})" for b in r["buttons"][:4])
        print(f"  {r['file']} {r['n_btn']}btn: {names}")


if __name__ == "__main__":
    main()
