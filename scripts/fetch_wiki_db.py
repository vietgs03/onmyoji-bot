#!/usr/bin/env python3
"""
fetch_wiki_db.py - Keo TOAN BO database tu Supabase cua trmzaiu/onmyoji_wiki.

Wiki nay luu data o Supabase (REST API mo, anon key public read-only). Chua data
GIA TRI NHAT: tung shikigami voi skill/profile/stat day du, da ngon ngu (en/cn/jp/vn).

Tables (so row): Shikigami 271, Soul 64, Onmyoji 6, Effect 480, Tag 33,
                 Evolution 13, Illustration 1156.

Du lieu nay -> sau nay xay chuc nang PHAN TICH (team builder, skill lookup, counter...).

Ra: data/wiki_db/<table>.json

Dung: python scripts/fetch_wiki_db.py
"""
import os, json, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "wiki_db")

SB_URL = "https://ytgbbokrmirexfxhxvrw.supabase.co"
SB_KEY = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJl"
          "ZiI6Inl0Z2Jib2tybWlyZXhmeGh4dnJ3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3"
          "NTk0NTQ2NjYsImV4cCI6MjA3NTAzMDY2Nn0.tnCrfVKRjWOmqtuYviUX3nM6_fpIMEP_nR8ypv9L0-8")

TABLES = ["Shikigami", "Soul", "Onmyoji", "Effect", "Tag", "Evolution", "Illustration"]
PAGE = 1000


def fetch_table(name):
    rows = []
    offset = 0
    while True:
        q = urllib.parse.urlencode({"select": "*", "order": "id", "limit": PAGE, "offset": offset})
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/{name}?{q}",
            headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
        batch = json.load(urllib.request.urlopen(req, timeout=30))
        rows += batch
        if len(batch) < PAGE:
            break
        offset += PAGE
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    for t in TABLES:
        try:
            rows = fetch_table(t)
            json.dump(rows, open(os.path.join(OUT, f"{t}.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            print(f"  {t}: {len(rows)} rows -> data/wiki_db/{t}.json")
        except Exception as e:
            print(f"  {t}: LOI {e}")
    print(f"XONG -> {OUT}")


if __name__ == "__main__":
    main()
