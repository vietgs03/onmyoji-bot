#!/usr/bin/env python3
"""Crawl full wikitext cua tung shikigami (SSR + SP + SR) -> data/fandom/shikigami_full.json."""
import json, os, sys, time, urllib.parse, urllib.request

API = "https://onmyoji.fandom.com/api.php"
UA = "onmyoji-research-bot/1.0"
BASE = os.path.join(os.path.dirname(__file__), "..", "data", "fandom")

def api(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:
            if a == 2: return {}
            time.sleep(1.5)

def wikitext(title):
    d = api({"action": "query", "prop": "revisions", "rvprop": "content",
             "rvslots": "main", "titles": title})
    for _, pg in d.get("query", {}).get("pages", {}).items():
        revs = pg.get("revisions")
        if revs: return revs[0]["slots"]["main"]["*"]
    return None

def main():
    force = "--force" in sys.argv
    idx = json.load(open(os.path.join(BASE, "category_index.json"), encoding="utf-8"))
    titles = []
    for r in ["SSR", "SP", "SR", "R", "N"]:
        titles += [t for t in idx.get(r, []) if ":" not in t]
    titles = list(dict.fromkeys(titles))

    path = os.path.join(BASE, "shikigami_full.json")
    data = {}
    if os.path.exists(path) and not force:
        data = json.load(open(path, encoding="utf-8"))

    new = 0
    for i, t in enumerate(titles):
        if t in data and data[t]: continue
        wt = wikitext(t)
        if wt:
            data[t] = wt; new += 1
            if new % 20 == 0:
                print(f"  {new} fetched... ({i+1}/{len(titles)})")
        time.sleep(0.2)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Saved {len(data)} shikigami full ({new} new) -> {path}")

if __name__ == "__main__":
    main()
