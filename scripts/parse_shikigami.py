#!/usr/bin/env python3
"""Parse shikigami list wikitext -> structured JSON (id, names EN/CN/JP/GL, rarity)."""
import json, os, re

BASE = os.path.join(os.path.dirname(__file__), "..", "data", "fandom")
src = json.load(open(os.path.join(BASE, "shikigami_list.json"), encoding="utf-8"))
wt = src.get("Shikigami/List/All", "")

# Split table rows by "|-"
rows = wt.split("|-")
out = []
for row in rows:
    # id: a line that is just a number
    m_id = re.search(r"\|\s*(\d{2,4})\s*\n", row)
    if not m_id:
        continue
    sid = int(m_id.group(1))
    # name link [[Name]] and following names line
    m_name = re.search(r"\[\[([^\|\]#]+)\]\]<br\s*/?>([^\n|]*)", row)
    if not m_name:
        m_name2 = re.search(r"\|\s*\[\[([^\|\]#]+)\]\]", row)
        en = m_name2.group(1).strip() if m_name2 else None
        others = ""
    else:
        en = m_name.group(1).strip()
        others = m_name.group(2).strip()
    # rarity from data-sort-value
    m_rar = re.search(r'data-sort-value="([^"]+)"', row)
    rarity = m_rar.group(1) if m_rar else None
    # parse others "CN - JP - GL"
    parts = [p.strip() for p in re.split(r"\s*-\s*", others) if p.strip()]
    cn = parts[0] if len(parts) >= 1 else None
    jp = parts[1] if len(parts) >= 2 else None
    gl = parts[2] if len(parts) >= 3 else None
    if en:
        out.append({"id": sid, "name_en": en, "name_cn": cn,
                    "name_jp": jp, "name_gl": gl, "rarity": rarity})

out.sort(key=lambda x: x["id"])
path = os.path.join(BASE, "shikigami_parsed.json")
json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
# summary
from collections import Counter
c = Counter(x["rarity"] for x in out)
print(f"Parsed {len(out)} shikigami -> {path}")
print("Rarity:", dict(c))
print("Sample:", json.dumps(out[:3], ensure_ascii=False))
