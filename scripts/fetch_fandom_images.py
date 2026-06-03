#!/usr/bin/env python3
"""
fetch_fandom_images.py - Keo anh shikigami EN tu Onmyoji Fandom (ten EN chuan).

Nguon Global/EN sach nhat cho data nhan dien nhan vat. Voi moi shikigami trong KB,
goi MediaWiki API tim file anh (portrait/icon/illustration) va tai ve.

Ra: data/fandom_images/<name>.png + _index.json (map name -> file, rarity...)

Dung: python fetch_fandom_images.py [limit]
"""
import os, sys, json, time, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "fandom_images")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
API = "https://onmyoji.fandom.com/api.php"


def api(params):
    q = urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
    return json.load(urllib.request.urlopen(req, timeout=25))


def page_image(title):
    """Lay URL anh dai dien (pageimage) cua 1 trang shikigami."""
    try:
        d = api({"action": "query", "titles": title, "prop": "pageimages",
                 "piprop": "original|thumbnail", "pithumbsize": "400"})
        pages = d.get("query", {}).get("pages", {})
        for pid, pg in pages.items():
            if int(pid) < 0:
                return None
            orig = pg.get("original", {}).get("source")
            thumb = pg.get("thumbnail", {}).get("source")
            return orig or thumb
    except Exception:
        return None
    return None


def download(url, path):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        data = urllib.request.urlopen(req, timeout=25).read()
        if len(data) < 500:
            return False
        with open(path, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False


def shikigami_names():
    kb = os.path.join(ROOT, "data", "fandom", "shikigami_skills.json")
    data = json.load(open(kb))
    return list(data.keys())


def main():
    os.makedirs(OUT, exist_ok=True)
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
    names = shikigami_names()[:limit]
    print(f"keo anh cho {len(names)} shikigami...")
    index = {}
    ok = fail = 0
    for i, name in enumerate(names):
        safe = name.replace("/", "_").replace(" ", "_")
        path = os.path.join(OUT, safe + ".png")
        if os.path.exists(path):
            index[name] = safe + ".png"; ok += 1; continue
        url = page_image(name)
        if url and download(url, path):
            index[name] = safe + ".png"; ok += 1
        else:
            fail += 1
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(names)}  ok={ok} fail={fail}")
            json.dump(index, open(os.path.join(OUT, "_index.json"), "w"), indent=1)
        time.sleep(0.15)  # lich su voi server
    json.dump(index, open(os.path.join(OUT, "_index.json"), "w"), indent=1)
    print(f"\nXONG: {ok} anh, {fail} khong tim thay -> {OUT}")


if __name__ == "__main__":
    main()
