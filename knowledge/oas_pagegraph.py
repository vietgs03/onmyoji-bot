#!/usr/bin/env python3
"""
oas_pagegraph.py - Trich PAGE-GRAPH (do thi dieu huong) tu OAS.

OAS (research/OAS) la bot Onmyoji Trung Quoc, co san KIEN THUC dieu huong:
  - tasks/GameUi/page.py    : do thi page. Moi page co check_button + links
                               (bam button X -> toi page Y).
  - tasks/*/assets.py       : dinh nghia I_* = RuleImage(roi_front=(x,y,w,h),
                               file=template.png, description). roi_front la vi tri
                               THUC cua nut tren man 1280x720.

Ta KHONG import OAS (deps nang) ma parse bang regex. Ket qua:
  knowledge/oas_pagegraph.json:
    {
      "resolution_src": [1280,720],
      "resolution_dst": [1152,679],
      "pages": {
        "page_main": {
          "check": [{"name":"I_CHECK_MAIN","roi":[x,y,w,h],"center":[cx,cy],"desc":...}],
          "links": {"page_summon": {"button":"I_MAIN_GOTO_SUMMON","roi":...,"center":...}},
          "additional": [...]   # nut dong popup/quang cao
        }, ...
      }
    }

Toa do da SCALE ve 1152x679 (game Steam EN cua ta) o truong *_dst.
Agent dung graph nay de biet LUONG (man -> nut -> man dich), roi dung dynamic OCR
tim toa do THUC (ben voi event) thay vi hardcode template TQ.

Dung:
  python oas_pagegraph.py build   -> sinh json
  python oas_pagegraph.py show     -> in do thi
  python oas_pagegraph.py path page_main page_realm_raid  -> tim duong di
"""
import os, re, json, glob, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OAS = os.path.join(ROOT, "research", "OAS")
PAGE_PY = os.path.join(OAS, "tasks", "GameUi", "page.py")
OUT = os.path.join(ROOT, "knowledge", "oas_pagegraph.json")

# OAS dung 1280x720, game Steam EN cua ta 1152x679
SRC_W, SRC_H = 1280, 720
DST_W, DST_H = 1152, 679

# ---------- 1. parse assets.py (moi task) -> {I_NAME: {roi, center, file, desc}} ----------
_RULE_RE = re.compile(
    r"(\w+)\s*=\s*RuleImage\(\s*roi_front=\((\d+),(\d+),(\d+),(\d+)\)"
    r".*?(?:file=\"([^\"]*)\")?\s*\)", re.S)
_OCR_RE = re.compile(
    r"(\w+)\s*=\s*RuleOcr\(\s*roi=\((\d+),(\d+),(\d+),(\d+)\)"
    r".*?keyword=\"([^\"]*)\".*?\)", re.S)
# description nam tren dong truoc (comment # ...)
_COMMENT_RE = re.compile(r"#\s*(.+)")


def _scale(x, y, w, h):
    sx, sy = DST_W / SRC_W, DST_H / SRC_H
    rx, ry, rw, rh = round(x*sx), round(y*sy), round(w*sx), round(h*sy)
    return [rx, ry, rw, rh], [rx + rw // 2, ry + rh // 2]


def parse_assets():
    """Quet tat ca assets.py -> dict {I_NAME: {...}}. Comment ngay tren = description."""
    out = {}
    for f in glob.glob(os.path.join(OAS, "tasks", "**", "assets.py"), recursive=True):
        txt = open(f, encoding="utf-8", errors="ignore").read()
        # bat description: dong comment ngay truoc khai bao
        lines = txt.split("\n")
        prev_comment = {}
        last_cmt = ""
        for ln in lines:
            m = _COMMENT_RE.match(ln.strip())
            if m:
                last_cmt = m.group(1).strip()
            elif "RuleImage(" in ln or "RuleOcr(" in ln:
                nm = ln.strip().split("=")[0].strip()
                if nm:
                    prev_comment[nm] = last_cmt
                last_cmt = ""
            elif ln.strip():
                last_cmt = ""
        for m in _RULE_RE.finditer(txt):
            name, x, y, w, h, file = m.group(1), *map(int, m.groups()[1:5]), m.group(6)
            roi, center = _scale(x, y, w, h)
            out[name] = {"name": name, "roi_src": [x, y, w, h], "roi": roi,
                         "center": center, "file": file or "",
                         "desc": prev_comment.get(name, ""), "kind": "image"}
        for m in _OCR_RE.finditer(txt):
            name, x, y, w, h, kw = m.group(1), *map(int, m.groups()[1:5]), m.group(6)
            roi, center = _scale(x, y, w, h)
            out[name] = {"name": name, "roi_src": [x, y, w, h], "roi": roi,
                         "center": center, "keyword": kw,
                         "desc": prev_comment.get(name, kw), "kind": "ocr"}
    return out


# ---------- 2. parse page.py -> graph (page -> check_button, links) ----------
_PAGE_RE = re.compile(r"(\w+)\s*=\s*Page\(\s*(?:check_button=)?(.+?)\)", re.S)
_LINK_RE = re.compile(r"(\w+)\.link\(\s*button=([\w.]+)\s*,\s*destination=(\w+)\s*\)")
_ADD_RE = re.compile(r"(\w+)\.additional\s*=\s*\[(.+?)\]", re.S)
_ASSET_REF = re.compile(r"(?:G|GGA|[\w]+Assets)\.(\w+)")


def _resolve(ref, assets):
    """G.I_CHECK_MAIN -> asset dict (chi lay ten cuoi sau dau .)"""
    m = _ASSET_REF.findall(ref)
    out = []
    for nm in m:
        if nm in assets:
            out.append(assets[nm])
        else:
            out.append({"name": nm, "unresolved": True})
    return out


def parse_pagegraph(assets):
    txt = open(PAGE_PY, encoding="utf-8").read()
    pages = {}
    for m in _PAGE_RE.finditer(txt):
        pname, check = m.group(1), m.group(2)
        if not pname.startswith("page_"):
            continue
        pages[pname] = {"name": pname, "check": _resolve(check, assets),
                        "links": {}, "additional": []}
    for m in _LINK_RE.finditer(txt):
        src, button, dst = m.groups()
        if src in pages:
            btn = _resolve(button, assets)
            pages[src]["links"][dst] = btn[0] if btn else {"name": button}
    for m in _ADD_RE.finditer(txt):
        pname, body = m.groups()
        if pname in pages:
            pages[pname]["additional"] = _resolve(body, assets)
    return pages


def build():
    assets = parse_assets()
    pages = parse_pagegraph(assets)
    data = {"resolution_src": [SRC_W, SRC_H], "resolution_dst": [DST_W, DST_H],
            "n_assets": len(assets), "pages": pages}
    json.dump(data, open(OUT, "w"), indent=1, ensure_ascii=False)
    nlink = sum(len(p["links"]) for p in pages.values())
    print(f"built {OUT}")
    print(f"  {len(assets)} assets, {len(pages)} pages, {nlink} links (edges)")
    # bao cao chat luong: bao nhieu nut resolve duoc toa do
    unres = sum(1 for p in pages.values() for b in p["links"].values()
                if b.get("unresolved"))
    print(f"  links chua resolve toa do: {unres}/{nlink}")
    return data


# ---------- truy van ----------
def load():
    return json.load(open(OUT))


def show():
    g = load()
    for pn, p in g["pages"].items():
        chk = ", ".join(c.get("name", "?") for c in p["check"])
        print(f"\n{pn}  (check: {chk})")
        for dst, b in p["links"].items():
            c = b.get("center")
            d = b.get("desc", "")
            print(f"   --[{b.get('name','?')} {c} {d}]--> {dst}")


def find_path(start, goal):
    """BFS tren do thi page -> list (page, button-de-bam-tu-page-do)."""
    g = load()["pages"]
    if start not in g or goal not in g:
        return None
    q = collections.deque([[start]])
    seen = {start}
    while q:
        path = q.popleft()
        cur = path[-1]
        if cur == goal:
            steps = []
            for i in range(len(path) - 1):
                btn = g[path[i]]["links"][path[i+1]]
                steps.append((path[i], path[i+1], btn))
            return steps
        for nxt in g[cur]["links"]:
            if nxt not in seen:
                seen.add(nxt)
                q.append(path + [nxt])
    return None


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "show":
        show()
    elif cmd == "path":
        steps = find_path(sys.argv[2], sys.argv[3])
        if not steps:
            print("khong tim duoc duong")
            return
        for src, dst, btn in steps:
            print(f"{src} --[{btn.get('name')} center={btn.get('center')} "
                  f"{btn.get('desc','')}]--> {dst}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
