#!/usr/bin/env python3
"""Parse skill information from raw Onmyoji fandom wikitext.

Input : data/fandom/shikigami_full.json  (dict: name -> raw wikitext)
Output: data/fandom/shikigami_skills.json
        dict: name -> {"rarity": str|None, "skills": [{"name": str, "desc": str}, ...]}

Robust to format variations; entries that cannot be parsed are skipped gracefully.
"""
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_PATH = os.path.join(BASE, "data", "fandom", "shikigami_full.json")
OUT_PATH = os.path.join(BASE, "data", "fandom", "shikigami_skills.json")


def clean_wikitext(text):
    """Strip common MediaWiki markup, returning readable plain text."""
    if not text:
        return ""
    s = text

    # Templates: {{Item|Fire3|10}} -> Fire3 ; {{ShikiIcon|348|SP X}} -> SP X
    # Repeatedly collapse innermost templates.
    tmpl = re.compile(r"\{\{([^{}]*)\}\}")
    for _ in range(10):
        new = tmpl.sub(lambda m: _render_template(m.group(1)), s)
        if new == s:
            break
        s = new

    # Links: [[Page|Label]] -> Label ; [[Page]] -> Page
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", s)
    # External links: [http://x Label] -> Label ; [http://x] -> ""
    s = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", s)
    s = re.sub(r"\[https?://\S+\]", "", s)

    # Bold/italic
    s = re.sub(r"'{2,5}", "", s)
    # <ref>...</ref>
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<ref[^>]*/>", "", s)
    # Line breaks -> space; other simple html tags stripped
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<sup>(.*?)</sup>", r"(\1)", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", "", s)

    # HTML entities (common)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

    # Collapse whitespace
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()


def _render_template(inner):
    """Render a single template's inner content to plain text best-effort."""
    parts = [p.strip() for p in inner.split("|")]
    if not parts:
        return ""
    name = parts[0].strip()
    # Self-referential / formatting templates: drop
    if name.upper().startswith("PAGENAME") or name == ":":
        return ""
    # Item/Icon style: take a meaningful trailing arg if present
    args = [p for p in parts[1:] if p and "=" not in p]
    if args:
        return args[-1]
    return name


def find_balanced_templates(text, tmpl_name):
    """Yield inner content of {{tmpl_name ...}} handling nested braces."""
    results = []
    pat = "{{" + tmpl_name
    i = 0
    low = text.lower()
    target = pat.lower()
    while True:
        start = low.find(target, i)
        if start == -1:
            break
        # Walk forward tracking brace depth
        depth = 0
        j = start
        n = len(text)
        while j < n - 1:
            two = text[j:j + 2]
            if two == "{{":
                depth += 1
                j += 2
                continue
            if two == "}}":
                depth -= 1
                j += 2
                if depth == 0:
                    break
                continue
            j += 1
        inner = text[start + 2 + len(tmpl_name):j - 2]
        results.append(inner)
        i = j
    return results


def parse_template_fields(inner):
    """Parse top-level |key = value fields from a template body."""
    fields = {}
    # Split on top-level pipes (ignore pipes inside nested {{ }} or [[ ]]).
    segs = []
    depth_c = depth_b = 0
    cur = []
    k = 0
    while k < len(inner):
        two = inner[k:k + 2]
        if two == "{{":
            depth_c += 1
            cur.append(two)
            k += 2
            continue
        if two == "}}":
            depth_c -= 1
            cur.append(two)
            k += 2
            continue
        if two == "[[":
            depth_b += 1
            cur.append(two)
            k += 2
            continue
        if two == "]]":
            depth_b -= 1
            cur.append(two)
            k += 2
            continue
        ch = inner[k]
        if ch == "|" and depth_c == 0 and depth_b == 0:
            segs.append("".join(cur))
            cur = []
            k += 1
            continue
        cur.append(ch)
        k += 1
    segs.append("".join(cur))

    for seg in segs:
        if "=" not in seg:
            continue
        key, val = seg.split("=", 1)
        fields[key.strip().lower()] = val.strip()
    return fields


def extract_rarity(wikitext):
    boxes = find_balanced_templates(wikitext, "ShikigamiBox")
    for inner in boxes:
        f = parse_template_fields(inner)
        if "rarity" in f and f["rarity"]:
            return clean_wikitext(f["rarity"]) or None
    # Fallback: regex
    m = re.search(r"\|\s*rarity\s*=\s*([^\n|]+)", wikitext, re.I)
    if m:
        r = clean_wikitext(m.group(1))
        return r or None
    return None


def extract_name(wikitext, fallback):
    boxes = find_balanced_templates(wikitext, "ShikigamiBox")
    for inner in boxes:
        f = parse_template_fields(inner)
        for key in ("name_gl", "name"):
            if f.get(key):
                nm = clean_wikitext(f[key])
                # name_gl is usually a clean english name
                if nm:
                    return nm
    return fallback


def extract_skills(wikitext):
    """Extract skills from SkillBox / Skill templates and ==Skills== sections."""
    skills = []
    seen = set()

    # 1. {{SkillBox ...}} and {{Skill ...}} templates
    for tmpl in ("SkillBox", "Skill"):
        for inner in find_balanced_templates(wikitext, tmpl):
            f = parse_template_fields(inner)
            name = f.get("name") or f.get("skillname") or f.get("title")
            desc = f.get("description") or f.get("desc") or f.get("effect") or f.get("text")
            name = clean_wikitext(name) if name else ""
            desc = clean_wikitext(desc) if desc else ""
            if not name and not desc:
                continue
            key = (name, desc)
            if key in seen:
                continue
            seen.add(key)
            skills.append({"name": name, "desc": desc})

    # 2. ==Skills== section with sub-headers (=== Skill Name ===) as fallback
    if not skills:
        sec = re.search(r"==+\s*Skills?\s*==+\s*(.*?)(?:\n==+[^=]|\Z)", wikitext, re.S | re.I)
        if sec:
            body = sec.group(1)
            # sub-headers define skill names
            parts = re.split(r"\n==+\s*([^=\n]+?)\s*==+\s*\n", body)
            if len(parts) > 1:
                # parts: [pre, name1, body1, name2, body2, ...]
                it = iter(parts[1:])
                for name, sbody in zip(it, it):
                    nm = clean_wikitext(name)
                    ds = clean_wikitext(sbody)
                    if not nm and not ds:
                        continue
                    key = (nm, ds)
                    if key in seen:
                        continue
                    seen.add(key)
                    skills.append({"name": nm, "desc": ds})
            else:
                ds = clean_wikitext(body)
                if ds:
                    skills.append({"name": "", "desc": ds})

    return skills


def main():
    with open(IN_PATH, encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, list):
        # normalize list of dicts to name-keyed
        norm = {}
        for item in data:
            if isinstance(item, dict):
                nm = item.get("name") or item.get("title")
                wt = item.get("wikitext") or item.get("raw") or ""
                if nm:
                    norm[nm] = wt
        data = norm

    result = {}
    parsed_with_skills = 0
    total_skills = 0
    errors = 0

    for name, wikitext in data.items():
        try:
            if not isinstance(wikitext, str):
                continue
            rarity = extract_rarity(wikitext)
            skills = extract_skills(wikitext)
            display = extract_name(wikitext, name)
            result[display] = {"rarity": rarity, "skills": skills}
            if skills:
                parsed_with_skills += 1
                total_skills += len(skills)
        except Exception as e:  # robust: never crash on one bad entry
            errors += 1
            sys.stderr.write(f"[warn] failed to parse {name!r}: {e}\n")
            continue

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    size = os.path.getsize(OUT_PATH)

    print(f"Total shikigami processed : {len(result)}")
    print(f"Shikigami with >=1 skill  : {parsed_with_skills}")
    print(f"Total skills extracted    : {total_skills}")
    print(f"Parse errors (skipped)    : {errors}")
    print(f"Output file               : {OUT_PATH}")
    print(f"Output size               : {size} bytes ({size/1024:.1f} KiB)")

    # Sample entries (prefer ones with skills)
    samples = [k for k, v in result.items() if v["skills"]][:2]
    if len(samples) < 2:
        samples += [k for k in result if k not in samples][: 2 - len(samples)]
    print("\n--- Sample entries ---")
    for s in samples:
        print(json.dumps({s: result[s]}, ensure_ascii=False, indent=2)[:1200])


if __name__ == "__main__":
    main()
