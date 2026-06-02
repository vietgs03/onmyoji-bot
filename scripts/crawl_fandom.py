#!/usr/bin/env python3
"""
Crawler nap data Onmyoji tu Fandom (MediaWiki API).
Luu wikitext + parsed cua cac trang quan trong vao data/fandom/.
Chay lap: moi lan bo sung them dataset. Idempotent (skip neu da co, tru khi --force).
"""
import json, os, sys, time, urllib.parse, urllib.request, re

API = "https://onmyoji.fandom.com/api.php"
UA = "onmyoji-research-bot/1.0 (educational)"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "fandom")
os.makedirs(OUT, exist_ok=True)

def api(params):
    params = {**params, "format": "json"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 2:
                print(f"  ! api fail {e}", file=sys.stderr); return {}
            time.sleep(1.5)

def category_members(cat, limit=500):
    out, cont = [], None
    while True:
        p = {"action": "query", "list": "categorymembers",
             "cmtitle": f"Category:{cat}", "cmlimit": min(limit, 500)}
        if cont: p["cmcontinue"] = cont
        d = api(p)
        out += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        cont = d.get("continue", {}).get("cmcontinue")
        if not cont or len(out) >= limit: break
        time.sleep(0.3)
    return out

def page_wikitext(title):
    d = api({"action": "query", "prop": "revisions", "rvprop": "content",
             "rvslots": "main", "titles": title})
    pages = d.get("query", {}).get("pages", {})
    for _, pg in pages.items():
        revs = pg.get("revisions")
        if revs:
            return revs[0]["slots"]["main"]["*"]
    return None

def save(name, obj):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"  saved {name} ({len(json.dumps(obj))} bytes)")

def crawl_pages(titles, out_name, force=False):
    """Tai wikitext cho danh sach trang, luu thanh 1 file json {title: wikitext}."""
    path = os.path.join(OUT, out_name)
    existing = {}
    if os.path.exists(path) and not force:
        existing = json.load(open(path, encoding="utf-8"))
    result = dict(existing)
    new = 0
    for t in titles:
        if t in result and result[t]: continue
        wt = page_wikitext(t)
        if wt:
            result[t] = wt; new += 1
            print(f"  + {t} ({len(wt)} chars)")
        time.sleep(0.25)
    save(out_name, result)
    print(f"  -> {new} new, {len(result)} total in {out_name}")
    return result

DATASETS = {
    "shikigami": lambda: crawl_pages(
        [t for t in [page_title for page_title in
                     _list_from("Shikigami/List/All")] ] or category_members("Shikigami"),
        "shikigami.json"),
}

def _list_from(list_page):
    """Lay danh sach link [[...]] tu 1 trang list."""
    wt = page_wikitext(list_page) or ""
    return list(dict.fromkeys(re.findall(r"\[\[([^\|\]#]+)", wt)))

if __name__ == "__main__":
    force = "--force" in sys.argv
    # Dataset 1: danh sach + category quan trong
    print("[1] Category indexes")
    index = {}
    for cat in ["Shikigami", "SP", "SSR", "SR", "R", "N", "Soul",
                "Exploration", "Boss", "Event", "Bondling", "Skill"]:
        index[cat] = category_members(cat)
        print(f"  Category:{cat} -> {len(index[cat])}")
        time.sleep(0.3)
    save("category_index.json", index)

    # Dataset 2: trang list shikigami
    print("[2] Shikigami list pages")
    list_pages = ["Shikigami/List", "Shikigami/List/All"]
    crawl_pages(list_pages, "shikigami_list.json", force=force)

    # Dataset 3: Souls (御魂) - full wikitext moi soul
    print("[3] Souls (Mitama)")
    souls = [s for s in category_members("Soul")
             if not s.startswith(("Template:", "Category:", "Boss Souls"))]
    crawl_pages(souls, "souls.json", force=force)

    # Dataset 4: Exploration / chapters & game-mode pages
    print("[4] Exploration & game modes")
    modes = category_members("Exploration") + [
        "Realm Raid", "Soul (Mode)", "Secret Zone", "Area Boss",
        "Bonding", "Hunt", "Demon Encounter", "Hyakki Yakou",
        "Duel", "Kekkai", "Orochi", "Evolve Zone", "Totem",
    ]
    crawl_pages(list(dict.fromkeys(modes)), "game_modes.json", force=force)

    # Dataset 5: core/glossary pages (UI / mechanic terms)
    print("[5] Core mechanic pages")
    core = ["Onmyoji", "Courtyard", "Talisman", "Equipment", "Mitama",
            "Soul", "Awaken", "Evolve", "Skin", "Demon Parade",
            "Stamina", "Jade", "AP", "Soul Pass"]
    crawl_pages(core, "core_pages.json", force=force)

    print("\nDONE. Data in data/fandom/")
