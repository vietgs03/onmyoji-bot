#!/usr/bin/env python3
"""Build a complete shikigami SKILLS knowledge base for Onmyoji (Global/EN).

Fetches "<name_en>/Main" subpages from onmyoji.fandom.com, parses the
{{SkillBox}} templates, cleans the wikitext, and writes a structured
skills JSON. Raw wikitext is cached so reruns don't refetch.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

BASE = os.path.join(os.path.dirname(__file__), "..", "data", "fandom")
PARSED = os.path.join(BASE, "shikigami_parsed.json")
RAW_CACHE = os.path.join(BASE, "shikigami_main_raw.json")
OUT = os.path.join(BASE, "shikigami_skills.json")

UA = "Mozilla/5.0 (Onmyoji research/knowledge-base bot)"


def fetch(page):
    url = (
        "https://onmyoji.fandom.com/api.php?action=parse&page="
        + urllib.parse.quote(page)
        + "&format=json&prop=wikitext"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.load(resp)


def fetch_wikitext(page):
    """Return wikitext for page, or None on error/404."""
    try:
        r = fetch(page)
    except Exception as e:  # network / HTTP errors
        print(f"    fetch error for {page!r}: {e}")
        return None
    if "error" in r:
        return None
    try:
        return r["parse"]["wikitext"]["*"]
    except (KeyError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Wikitext cleaning
# ---------------------------------------------------------------------------
def clean_wikitext(text):
    if not text:
        return ""
    s = text
    # Strip <ref>...</ref> blocks
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<ref[^>]*/>", "", s, flags=re.IGNORECASE)
    # Drop File/Image links entirely: [[File:...]] / [[Image:...]]
    s = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", s, flags=re.IGNORECASE)
    # [[a|b]] -> b , [[a]] -> a
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    # Remove leftover templates {{...}} (non-greedy, repeated for nesting)
    for _ in range(3):
        new = re.sub(r"\{\{[^{}]*\}\}", "", s)
        if new == s:
            break
        s = new
    # Bold/italic markup '''x''' / ''x''
    s = s.replace("'''", "").replace("''", "")
    # <br> variants -> space
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.IGNORECASE)
    # Other simple tags
    s = re.sub(r"</?[a-zA-Z][^>]*>", " ", s)
    # Definition/list markers at line starts (; and :)
    s = re.sub(r"^[;:#*]+\s*", " ", s, flags=re.MULTILINE)
    # Horizontal rules
    s = re.sub(r"-{3,}", " ", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_templates(wikitext, template_name="SkillBox"):
    """Yield the inner body of each {{SkillBox ...}} (brace-balanced)."""
    bodies = []
    needle = "{{" + template_name
    idx = 0
    n = len(wikitext)
    while True:
        start = wikitext.find(needle, idx)
        if start == -1:
            break
        # Walk to matching closing braces
        depth = 0
        i = start
        while i < n:
            if wikitext.startswith("{{", i):
                depth += 1
                i += 2
                continue
            if wikitext.startswith("}}", i):
                depth -= 1
                i += 2
                if depth == 0:
                    break
                continue
            i += 1
        body = wikitext[start + 2 : i - 2]  # strip outer braces
        # remove leading template name
        body = body[len(template_name):]
        bodies.append(body)
        idx = i
    return bodies


def parse_params(body):
    """Parse |key = value pairs from a template body, brace/bracket aware."""
    params = {}
    # Split on top-level pipes only.
    parts = []
    depth_b = 0  # {{ }}
    depth_l = 0  # [[ ]]
    cur = []
    i = 0
    n = len(body)
    while i < n:
        if body.startswith("{{", i):
            depth_b += 1
            cur.append("{{")
            i += 2
            continue
        if body.startswith("}}", i):
            depth_b = max(0, depth_b - 1)
            cur.append("}}")
            i += 2
            continue
        if body.startswith("[[", i):
            depth_l += 1
            cur.append("[[")
            i += 2
            continue
        if body.startswith("]]", i):
            depth_l = max(0, depth_l - 1)
            cur.append("]]")
            i += 2
            continue
        ch = body[i]
        if ch == "|" and depth_b == 0 and depth_l == 0:
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    parts.append("".join(cur))

    for part in parts:
        if "=" not in part:
            continue
        key, _, val = part.partition("=")
        params[key.strip()] = val.strip()
    return params


def parse_skillboxes(wikitext):
    """Return list of skill dicts from a /Main page wikitext."""
    skills = []
    for body in split_templates(wikitext, "SkillBox"):
        p = parse_params(body)
        name = clean_wikitext(p.get("Name", "")).strip()
        if not name:
            continue
        # Base description plus brief upgrade notes
        desc = clean_wikitext(p.get("Description", ""))
        upgrades = []
        for lvl in ("L2", "L3", "L4", "L5", "L6"):
            if p.get(lvl):
                cleaned = clean_wikitext(p[lvl])
                if cleaned:
                    upgrades.append(f"{lvl}: {cleaned}")
        if upgrades:
            desc = (desc + " | Upgrades: " + "; ".join(upgrades)).strip(" |")
        skills.append(
            {
                "name": name,
                "type": clean_wikitext(p.get("Type", "")),
                "onibi": clean_wikitext(p.get("Onibi", "")),
                "cooldown": clean_wikitext(p.get("Cooldown", "")),
                "desc": desc,
            }
        )
    return skills


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------
def main():
    with open(PARSED, encoding="utf-8") as f:
        shikigami = json.load(f)
    print(f"Loaded {len(shikigami)} shikigami")

    # Load existing raw cache if present
    raw_cache = {}
    if os.path.exists(RAW_CACHE):
        try:
            with open(RAW_CACHE, encoding="utf-8") as f:
                raw_cache = json.load(f)
            print(f"Loaded raw cache with {len(raw_cache)} pages")
        except Exception:
            raw_cache = {}

    results = {}
    for idx, s in enumerate(shikigami, 1):
        name_en = s.get("name_en")
        name_gl = s.get("name_gl")
        if not name_en:
            continue

        wikitext = None
        used_page = None

        # 1) cache
        if name_en in raw_cache and raw_cache[name_en]:
            wikitext = raw_cache[name_en]
            used_page = name_en + "/Main (cache)"
        else:
            # 2) name_en/Main
            page = name_en + "/Main"
            wikitext = fetch_wikitext(page)
            used_page = page
            time.sleep(0.25)
            # 3) fallback name_gl/Main
            if not wikitext and name_gl and name_gl != name_en:
                page2 = name_gl + "/Main"
                wikitext = fetch_wikitext(page2)
                used_page = page2
                time.sleep(0.25)
            if wikitext:
                raw_cache[name_en] = wikitext

        # Follow a #REDIRECT to the real /Main page if needed.
        if wikitext:
            m = re.match(r"\s*#REDIRECT\s*\[\[([^\]]+)\]\]", wikitext, re.IGNORECASE)
            if m:
                target = m.group(1).split("|")[0].strip()
                redirected = fetch_wikitext(target)
                time.sleep(0.25)
                if redirected:
                    wikitext = redirected
                    raw_cache[name_en] = wikitext
                    used_page = target + " (redirect)"

        skills = []
        if wikitext:
            try:
                skills = parse_skillboxes(wikitext)
            except Exception as e:
                print(f"    parse error for {name_en!r}: {e}")
                skills = []

        results[name_en] = {
            "rarity": s.get("rarity"),
            "name_cn": s.get("name_cn"),
            "skills": skills,
        }

        if idx % 20 == 0:
            got = sum(1 for v in results.values() if v["skills"])
            print(f"  [{idx}/{len(shikigami)}] {name_en} -> {len(skills)} skills "
                  f"(running: {got} with skills)")
            # periodic checkpoint of raw cache
            with open(RAW_CACHE, "w", encoding="utf-8") as f:
                json.dump(raw_cache, f, ensure_ascii=False, indent=1)

    # Persist outputs
    with open(RAW_CACHE, "w", encoding="utf-8") as f:
        json.dump(raw_cache, f, ensure_ascii=False, indent=1)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Validation
    with_skills = sum(1 for v in results.values() if v["skills"])
    total_skills = sum(len(v["skills"]) for v in results.values())
    print("\n=== VALIDATION ===")
    print(f"Shikigami total      : {len(results)}")
    print(f"Shikigami >=1 skill  : {with_skills}")
    print(f"Total skills parsed  : {total_skills}")
    print(f"Raw pages cached     : {len(raw_cache)}")
    print(f"Output file          : {OUT} "
          f"({os.path.getsize(OUT)} bytes)")
    print(f"Raw cache file       : {RAW_CACHE} "
          f"({os.path.getsize(RAW_CACHE)} bytes)")

    samples = [k for k, v in results.items() if v["skills"]][:2]
    for k in samples:
        print(f"\n--- SAMPLE: {k} ({results[k]['rarity']}, {results[k]['name_cn']}) ---")
        print(json.dumps(results[k], ensure_ascii=False, indent=2)[:1200])


if __name__ == "__main__":
    main()
