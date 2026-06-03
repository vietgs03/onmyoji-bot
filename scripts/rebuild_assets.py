#!/usr/bin/env python3
"""
rebuild_assets.py - Tai tao MOI asset/data tu source game + web (de tai su dung).

Cac asset anh nang KHONG commit (gitignore) -> script nay dung lai tat ca tu dau
khi can (vd clone repo moi, hoac game update). Chay tung buoc hoac --all.

Buoc:
  ui        : giai ma res.npk -> ui_layouts.json (UI panel/button toa do)   [tracked]
  sprites   : giai ma res.npk -> data/game_assets/res_npk/png (UI sprite)
  assets_en : copy asset EN lo thien (loading/face/headicon) tu game
  fandom    : keo 265 anh shikigami EN tu Fandom wiki
  oas       : trich 52 feature tu research/OAS -> oas_features.json          [tracked]

Dung:
  python scripts/rebuild_assets.py --all
  python scripts/rebuild_assets.py ui sprites
"""
import os, sys, shutil, subprocess, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = "/mnt/c/Program Files (x86)/Steam/steamapps/common/Onmyoji"
DOCS = os.path.join(GAME, "Documents")
PY = os.path.join(ROOT, ".venv", "bin", "python")


def _run(cmd):
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def step_ui():
    """res.npk -> json -> ui_layouts.json (tracked)."""
    tmp = "/tmp/rebuild_uijson"
    shutil.rmtree(tmp, ignore_errors=True)
    _run([PY, "scripts/nxpk_extract.py", "extract",
          os.path.join(GAME, "res.npk"), tmp, "--filter", "json"])
    _run([PY, "scripts/parse_ui_layout.py", os.path.join(tmp, "json")])
    shutil.rmtree(tmp, ignore_errors=True)


def step_sprites():
    """res.npk -> data/game_assets/res_npk/png (UI sprite)."""
    out = os.path.join(ROOT, "data/game_assets/res_npk")
    os.makedirs(out, exist_ok=True)
    _run([PY, "scripts/nxpk_extract.py", "extract",
          os.path.join(GAME, "res.npk"), out, "--filter", "png"])


def step_assets_en():
    """Copy asset EN lo thien tu game/Documents."""
    jobs = [
        (os.path.join(DOCS, "mulnation/en"), "data/game_assets/en_loading", ".png"),
        (os.path.join(DOCS, "face_big"), "data/game_assets/face_big", ".png"),
        (os.path.join(DOCS, "headicon"), "data/game_assets/headicon", ".png"),
    ]
    for src, dst_rel, ext in jobs:
        dst = os.path.join(ROOT, dst_rel)
        os.makedirs(dst, exist_ok=True)
        n = 0
        for f in glob.glob(os.path.join(src, "**", f"*{ext}"), recursive=True):
            shutil.copy2(f, dst)
            n += 1
        print(f"  {dst_rel}: {n} files")


def step_fandom():
    _run([PY, "scripts/fetch_fandom_images.py"])


def step_wiki():
    """trmzaiu/onmyoji_wiki -> 582 anh EN (shikigami/soul/onmyoji icons + stats + rarity)."""
    import urllib.request
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    api = "https://api.github.com/repos/trmzaiu/onmyoji_wiki/git/trees/HEAD?recursive=1"
    req = urllib.request.Request(api, headers={"User-Agent": UA})
    import json as _j
    tree = _j.load(urllib.request.urlopen(req, timeout=30))["tree"]
    keep = [x["path"] for x in tree if x["type"] == "blob" and x["path"].endswith(".webp")
            and any(s in x["path"] for s in ["shikigami/icons/", "souls/icons/",
                    "onmyoji/icons/", "images/stats/", "images/rarity/"])]
    open("/tmp/wiki_imgs.txt", "w").write("\n".join(keep))
    _run([PY, "scripts/fetch_wiki_images.py", "/tmp/wiki_imgs.txt"])


def step_qidu():
    """qiduQD/Onmyoji-Auto-Assistant -> 44 button template (CN, dung augment)."""
    import urllib.request, json as _j
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    out = os.path.join(ROOT, "data/external/qidu_templates")
    os.makedirs(out, exist_ok=True)
    api = "https://api.github.com/repos/qiduQD/Onmyoji-Auto-Assistant/git/trees/HEAD?recursive=1"
    req = urllib.request.Request(api, headers={"User-Agent": UA})
    tree = _j.load(urllib.request.urlopen(req, timeout=30))["tree"]
    raw = "https://raw.githubusercontent.com/qiduQD/Onmyoji-Auto-Assistant/HEAD/"
    n = 0
    for x in tree:
        if x["path"].endswith(".png"):
            dst = os.path.join(out, os.path.basename(x["path"]))
            if os.path.exists(dst):
                n += 1; continue
            r = urllib.request.Request(raw + x["path"], headers={"User-Agent": UA})
            open(dst, "wb").write(urllib.request.urlopen(r, timeout=20).read())
            n += 1
    print(f"  qidu_templates: {n} files")


def step_wiki_db():
    """Keo DB Supabase (271 shikigami/64 soul/480 effect ...) - data phan tich."""
    _run([PY, "scripts/fetch_wiki_db.py"])


def step_oas():
    _run([PY, "scripts/extract_oas_tasks.py"])


STEPS = {"ui": step_ui, "sprites": step_sprites, "assets_en": step_assets_en,
         "fandom": step_fandom, "wiki": step_wiki, "qidu": step_qidu, "wiki_db": step_wiki_db, "oas": step_oas}


def main():
    os.chdir(ROOT)
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    todo = list(STEPS) if "--all" in args else [a for a in args if a in STEPS]
    for name in todo:
        print(f"\n=== [{name}] ===")
        try:
            STEPS[name]()
        except Exception as e:
            print(f"  LOI: {e}")
    print("\nXONG.")


if __name__ == "__main__":
    main()
