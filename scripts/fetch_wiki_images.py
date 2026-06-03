#!/usr/bin/env python3
"""
fetch_wiki_images.py - Tai anh EN tu repo trmzaiu/onmyoji_wiki (GitHub).

Nguon GIA TRI: 6005 anh EN, ten file = ten EN chuan. Ta lay cac bo dung de
NHAN DIEN trong UI game:
  shikigami/icons  (461)  -> avatar shikigami trong doi hinh/sanctuary
  souls/icons             -> icon ngu hon (mitama)
  onmyoji/icons           -> icon onmyoji (SSR nhan vat)
  images/stats            -> icon chi so (ATK/HP/Crit/rank A-S...)
  images/rarity           -> khung do hiem (N/R/SR/SSR/SP)

Ra: data/external/wiki/<bo>/<ten>.webp  (gitignored, regen qua rebuild_assets)

Dung: python scripts/fetch_wiki_images.py [list_file]
"""
import os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "external", "wiki")
RAW = "https://raw.githubusercontent.com/trmzaiu/onmyoji_wiki/HEAD/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def bucket(path):
    if "shikigami/icons/" in path: return "shikigami_icons"
    if "souls/icons/" in path: return "soul_icons"
    if "onmyoji/icons/" in path: return "onmyoji_icons"
    if "images/stats/" in path: return "stats"
    if "images/rarity/" in path: return "rarity"
    return "misc"


def main():
    lst = sys.argv[1] if len(sys.argv) > 1 else "/tmp/wiki_imgs.txt"
    paths = [l.strip() for l in open(lst) if l.strip()]
    ok = fail = 0
    for i, p in enumerate(paths, 1):
        b = bucket(p)
        d = os.path.join(OUT, b)
        os.makedirs(d, exist_ok=True)
        name = os.path.basename(p)
        dst = os.path.join(d, name)
        if os.path.exists(dst):
            ok += 1
            continue
        try:
            req = urllib.request.Request(RAW + p, headers={"User-Agent": UA})
            data = urllib.request.urlopen(req, timeout=20).read()
            open(dst, "wb").write(data)
            ok += 1
        except Exception as e:
            fail += 1
            if fail <= 5:
                print(f"  FAIL {name}: {e}")
        if i % 100 == 0:
            print(f"  {i}/{len(paths)} (ok={ok} fail={fail})")
        time.sleep(0.03)
    print(f"XONG: ok={ok} fail={fail} -> {OUT}")


if __name__ == "__main__":
    main()
