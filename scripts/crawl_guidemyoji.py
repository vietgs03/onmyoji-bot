#!/usr/bin/env python3
"""
Crawler guidemyoji.com (WordPress REST API).
Nap toan bo posts (title, slug, category, content text) vao data/guidemyoji/posts.json.
Idempotent: skip post da co (theo id) tru khi --force.
"""
import json, os, sys, time, urllib.request, urllib.parse, re, html

BASE_URL = "https://guidemyoji.com/wp-json/wp/v2"
UA = "onmyoji-research-bot/1.0 (educational)"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "guidemyoji")
os.makedirs(OUT, exist_ok=True)

def get(path, **params):
    url = f"{BASE_URL}/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r), dict(r.headers)
        except Exception as e:
            if a == 2:
                print(f"  ! {e}", file=sys.stderr); return [], {}
            time.sleep(2)

def strip_html(s):
    s = re.sub(r"<script.*?</script>", "", s, flags=re.S)
    s = re.sub(r"<style.*?</style>", "", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"\s+\n", "\n", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()

def main():
    force = "--force" in sys.argv
    # category id -> slug
    cats, _ = get("categories", per_page=100)
    cat_map = {c["id"]: c["slug"] for c in cats}

    path = os.path.join(OUT, "posts.json")
    existing = {}
    if os.path.exists(path) and not force:
        existing = {str(p["id"]): p for p in json.load(open(path, encoding="utf-8"))}

    page, total_pages = 1, 1
    seen = dict(existing)
    new = 0
    while page <= total_pages:
        posts, headers = get("posts", per_page=20, page=page,
                              _fields="id,slug,date,title,content,categories,link")
        total_pages = int(headers.get("X-WP-TotalPages", total_pages))
        if not posts:
            break
        for p in posts:
            pid = str(p["id"])
            if pid in seen and not force:
                continue
            entry = {
                "id": p["id"],
                "slug": p.get("slug"),
                "date": p.get("date"),
                "link": p.get("link"),
                "title": strip_html(p["title"]["rendered"]),
                "categories": [cat_map.get(c, str(c)) for c in p.get("categories", [])],
                "text": strip_html(p["content"]["rendered"]),
            }
            seen[pid] = entry
            new += 1
            print(f"  + [{','.join(entry['categories'])}] {entry['title'][:60]} ({len(entry['text'])} chars)")
        print(f"  page {page}/{total_pages} done")
        page += 1
        time.sleep(0.4)

    data = sorted(seen.values(), key=lambda x: x["id"])
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    from collections import Counter
    c = Counter(cat for p in data for cat in p["categories"])
    print(f"\nSaved {len(data)} posts ({new} new) -> {path}")
    print("By category:", dict(c.most_common(12)))

if __name__ == "__main__":
    main()
