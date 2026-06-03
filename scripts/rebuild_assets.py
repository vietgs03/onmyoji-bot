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


def step_oas():
    _run([PY, "scripts/extract_oas_tasks.py"])


STEPS = {"ui": step_ui, "sprites": step_sprites, "assets_en": step_assets_en,
         "fandom": step_fandom, "oas": step_oas}


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
