#!/usr/bin/env python3
"""Parse souls.json wikitext -> structured (no, names, type, combo2, combo4, location)."""
import json, os, re

BASE = os.path.join(os.path.dirname(__file__), "..", "data", "fandom")
src = json.load(open(os.path.join(BASE, "souls.json"), encoding="utf-8"))

def field(wt, key):
    m = re.search(rf"\|\s*{key}\s*=\s*(.*?)(?=\n\s*\||\n\}}\}}|\Z)", wt, re.S)
    if not m: return None
    v = m.group(1).strip()
    v = re.sub(r"<br\s*/?>", " / ", v)
    v = re.sub(r"\[\[([^\|\]]+)\|([^\]]+)\]\]", r"\2", v)
    v = re.sub(r"\[\[([^\]]+)\]\]", r"\1", v)
    v = re.sub(r"\s+", " ", v).strip()
    return v or None

out = []
for name, wt in src.items():
    if not wt or "{{MitamaBox" not in wt:
        continue
    out.append({
        "name": name,
        "no": field(wt, "no"),
        "name_cn": field(wt, "name_cn"),
        "name_jp": field(wt, "name_jp"),
        "name_en": field(wt, "name_en") or name,
        "type": field(wt, "type"),
        "combo2": field(wt, "combo2"),
        "combo4": field(wt, "combo4"),
    })

def sort_key(s):
    try: return int(s["no"])
    except: return 9999
out.sort(key=sort_key)
path = os.path.join(BASE, "souls_parsed.json")
json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Parsed {len(out)} souls -> {path}")
for s in out[:4]:
    print(f"  #{s['no']:>3} {s['name_en']:<16} [{s['type']}] 2:{s['combo2']}")
