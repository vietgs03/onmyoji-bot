#!/usr/bin/env python3
"""
Crawl guidemyoji.com qua Wayback Machine (vuot Cloudflare).
1. CDX API -> liet ke tat ca URL bai viet da luu.
2. Tai ban luu moi URL (snapshot moi nhat) -> trich title + text.
Luu vao data/guidemyoji/posts.json. Idempotent theo URL.
"""
import json, os, sys, time, urllib.request, urllib.parse, re, html

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "guidemyoji")
os.makedirs(OUT, exist_ok=True)
UA = "onmyoji-research-bot/1.0"

def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            if a == 2:
                print(f"  ! {e}", file=sys.stderr); return None
            time.sleep(2)

def list_urls():
    cdx = ("http://web.archive.org/cdx/search/cdx?url=guidemyoji.com*"
           "&output=json&filter=statuscode:200&filter=mimetype:text/html"
           "&collapse=urlkey&fl=original,timestamp")
    raw = fetch(cdx, timeout=60)
    if not raw: return []
    rows = json.loads(raw)[1:]
    # keep article-like urls (skip tag/category/page listings, feeds)
    out = []
    for orig, ts in rows:
        if re.search(r"/(tag|category|page|feed|wp-json|author|comments)/", orig):
            continue
        if orig.rstrip("/").endswith("guidemyoji.com"):
            continue
        out.append((orig, ts))
    return out

def strip(h):
    h = re.sub(r"<script.*?</script>", " ", h, flags=re.S)
    h = re.sub(r"<style.*?</style>", " ", h, flags=re.S)
    # try to grab main article content
    m = re.search(r"<article\b.*?</article>", h, flags=re.S)
    body = m.group(0) if m else h
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(body)
    body = re.sub(r"\s{2,}", " ", body)
    return body.strip()

def title_of(h):
    m = re.search(r"<title>(.*?)</title>", h, flags=re.S)
    return html.unescape(m.group(1)).replace(" - GUIDEMYOJI", "").strip() if m else ""

def main():
    force = "--force" in sys.argv
    limit = None
    for a in sys.argv:
        if a.startswith("--limit="): limit = int(a.split("=")[1])

    path = os.path.join(OUT, "posts.json")
    existing = {}
    if os.path.exists(path) and not force:
        existing = {p["url"]: p for p in json.load(open(path, encoding="utf-8"))}

    urls = list_urls()
    print(f"Found {len(urls)} archived urls")
    if limit: urls = urls[:limit]

    data = dict(existing)
    new = 0
    for i, (orig, ts) in enumerate(urls):
        if orig in data and not force:
            continue
        wb = f"http://web.archive.org/web/{ts}id_/{orig}"
        h = fetch(wb)
        if not h:
            continue
        text = strip(h)
        if len(text) < 200:
            continue
        data[orig] = {"url": orig, "timestamp": ts,
                      "title": title_of(h), "text": text[:20000]}
        new += 1
        if new % 10 == 0:
            print(f"  {new} fetched... last: {data[orig]['title'][:50]}")
        time.sleep(0.5)

    out = sorted(data.values(), key=lambda x: x["url"])
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nSaved {len(out)} posts ({new} new) -> {path}")

if __name__ == "__main__":
    main()
