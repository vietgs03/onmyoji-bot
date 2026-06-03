#!/usr/bin/env python3
"""Map id anh flow_assets (id-based, vd 598.png) -> ten EN.

flow_shikigami.json: id -> {avatar path, rarity, names.zh}  (names.en van la zh, data tho)
wiki_db/Shikigami.json: id rieng + name.en + name.cn[] (EN chuan)

Khop qua ten zh: flow.names.zh chua/trung wiki_db.name.cn[0].
Cho SP variant (vd 灼华桃花妖) -> tim base shikigami (桃花妖) bang substring.

CLI:
  python flow_id_map.py build        # build + luu data/external/flow_assets/id_to_en.json
  python flow_id_map.py lookup 598   # tra ten EN cho flow id
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(p):
    return json.load(open(p, encoding="utf-8"))


def build_map():
    flow = _load(os.path.join(ROOT, "data/external/firechain/flow_shikigami.json"))
    wdb = _load(os.path.join(ROOT, "data/wiki_db/Shikigami.json"))

    # index wiki_db theo ten cn (han tu)
    cn_to_en = {}
    for s in wdb:
        en = (s.get("name") or {}).get("en")
        cn = (s.get("name") or {}).get("cn") or []
        if not en:
            continue
        for c in (cn if isinstance(cn, list) else [cn]):
            if c and any("\u4e00" <= ch <= "\u9fff" for ch in c):
                cn_to_en[c] = en

    cn_keys = sorted(cn_to_en, key=len, reverse=True)  # khop dai truoc
    out = {}
    matched = unmatched = 0
    for item in flow:
        fid = item.get("id")
        zh = (item.get("names") or {}).get("zh", "")
        rarity = item.get("rarity", "")
        avatar = item.get("avatar", "")
        en = cn_to_en.get(zh)
        if not en:  # SP/skin variant: tim base name la substring
            for c in cn_keys:
                if c in zh:
                    en = cn_to_en[c]
                    break
        if en:
            matched += 1
        else:
            unmatched += 1
            en = zh  # fallback giu zh
        out[fid] = {"en": en, "zh": zh, "rarity": rarity, "avatar": avatar}

    print(f"khop {matched}/{matched + unmatched} (fallback zh: {unmatched})")
    dst = os.path.join(ROOT, "data/external/flow_assets/id_to_en.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"luu -> {dst}")
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build_map()
    elif cmd == "lookup":
        m = _load(os.path.join(ROOT, "data/external/flow_assets/id_to_en.json"))
        fid = sys.argv[2]
        print(json.dumps(m.get(fid, {"error": "not found"}), ensure_ascii=False, indent=1))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
