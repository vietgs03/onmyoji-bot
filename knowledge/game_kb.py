#!/usr/bin/env python3
"""
game_kb.py - Knowledge Base THONG NHAT cho Onmyoji bot.

Gop moi nguon tri thuc thanh interface chung + sinh "documents" de index vector:
  - Shikigami (269): ten EN/CN/JP, rarity, CV, SP.
  - Souls/Mitama (69): type, combo2, combo4.
  - Game modes (26): mo ta day du tu wiki.
  - UI screens (tu exploration graph): label, desc, cac transition.
  - Learnings (knowledge/LEARNINGS.md): tri thuc van hanh bot.

Dung:
  from game_kb import KB
  kb = KB()
  kb.shikigami("Ibaraki")        # tra cuu
  kb.soul("Harvest")
  kb.mode("Realm Raid")
  kb.documents()                 # list[dict] cho vector index: {id,type,title,text,meta}
  kb.stats()

CLI: python game_kb.py [stats|docs|shikigami <q>|soul <q>|mode <q>|screen <q>]
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FANDOM = os.path.join(ROOT, "data", "fandom")
EXP = os.path.join(ROOT, "exploration")
KNOW = os.path.join(ROOT, "knowledge")


def _load(path, default):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def _clean(text, limit=1200):
    """Lam sach wikitext tho -> doan van de embed."""
    if not text:
        return ""
    t = re.sub(r"\{\{[^}]*\}\}", " ", text)        # bo template {{...}}
    t = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", t)  # [[a|b]] -> b
    t = re.sub(r"'''?|==+|<[^>]+>", " ", t)        # bo bold/heading/html
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit]


class KB:
    def __init__(self):
        self.shikigami_list = _load(os.path.join(FANDOM, "shikigami_parsed.json"), [])
        self.shikigami_full = _load(os.path.join(FANDOM, "shikigami_full_parsed.json"), [])
        self.souls = _load(os.path.join(FANDOM, "souls_parsed.json"), [])
        self.modes = _load(os.path.join(FANDOM, "game_modes.json"), {})
        self.core = _load(os.path.join(FANDOM, "core_pages.json"), {})
        self.world = _load(os.path.join(EXP, "world.json"), {"states": {}, "edges": []})
        # index nhanh shikigami_full theo ten
        self._sfull = {s.get("name", "").lower(): s for s in self.shikigami_full}

    # ---------- tra cuu ----------
    def shikigami(self, q):
        ql = q.lower()
        hits = [s for s in self.shikigami_list
                if ql in (s.get("name_en") or "").lower()
                or ql in (s.get("name_cn") or "").lower()
                or ql in (s.get("name_gl") or "").lower()]
        # bo sung CV/SP tu full
        for s in hits:
            f = self._sfull.get((s.get("name_en") or "").lower())
            if f:
                s = {**s, "cv": f.get("cv"), "has_sp": f.get("has_sp")}
        return hits

    def soul(self, q):
        ql = q.lower()
        return [s for s in self.souls
                if ql in (s.get("name_en") or "").lower()
                or ql in (s.get("name_cn") or "").lower()]

    def soul_by_type(self, t):
        tl = t.lower()
        return [s for s in self.souls if tl in (s.get("type") or "").lower()]

    def mode(self, q):
        ql = q.lower()
        return {k: v for k, v in self.modes.items() if ql in k.lower()}

    def screen(self, q):
        ql = q.lower()
        out = []
        for sid, st in self.world["states"].items():
            lbl = (st.get("label") or "")
            desc = (st.get("desc") or "")
            if ql in lbl.lower() or ql in desc.lower():
                out.append({"sid": sid, "label": lbl, "desc": desc})
        return out

    # ---------- documents cho vector index ----------
    def documents(self):
        """Sinh list document chuan hoa de embed: {id,type,title,text,meta}."""
        docs = []
        # 1) shikigami
        for s in self.shikigami_list:
            f = self._sfull.get((s.get("name_en") or "").lower(), {})
            title = s.get("name_en") or s.get("name_gl") or f"shiki-{s.get('id')}"
            text = (f"Shikigami {title} (CN {s.get('name_cn')}, JP {s.get('name_jp')}), "
                    f"rarity {s.get('rarity')}. CV {f.get('cv','?')}. "
                    f"{'Co phien ban SP.' if f.get('has_sp') else ''}")
            docs.append({"id": f"shiki:{s.get('id')}", "type": "shikigami",
                         "title": title, "text": text.strip(),
                         "meta": {"rarity": s.get("rarity"), "name_cn": s.get("name_cn")}})
        # 2) souls
        for s in self.souls:
            title = s.get("name_en") or s.get("name")
            text = (f"Soul/Mitama {title} (CN {s.get('name_cn')}), type {s.get('type')}. "
                    f"2-set: {s.get('combo2')}. 4-set: {s.get('combo4')}.")
            docs.append({"id": f"soul:{s.get('no')}", "type": "soul",
                         "title": title, "text": text,
                         "meta": {"type": s.get("type")}})
        # 3) modes (mo ta day du)
        for name, body in self.modes.items():
            docs.append({"id": f"mode:{name}", "type": "mode",
                         "title": name, "text": f"Game mode {name}. {_clean(body)}",
                         "meta": {}})
        # 4) core pages
        if isinstance(self.core, dict):
            for name, body in self.core.items():
                docs.append({"id": f"core:{name}", "type": "core",
                             "title": name, "text": f"{name}. {_clean(body)}",
                             "meta": {}})
        # 5) UI screens (chuc nang game da map)
        seen = set()
        for sid, st in self.world["states"].items():
            lbl = st.get("label")
            if not lbl or lbl in seen:
                continue
            seen.add(lbl)
            descs = [s.get("desc") for s in self.world["states"].values()
                     if s.get("label") == lbl and s.get("desc")]
            text = f"Man hinh game '{lbl}'. " + " ".join(dict.fromkeys(descs))[:600]
            docs.append({"id": f"screen:{lbl}", "type": "screen",
                         "title": lbl, "text": text, "meta": {}})
        # 6) learnings (chia theo heading)
        lp = os.path.join(KNOW, "LEARNINGS.md")
        if os.path.exists(lp):
            md = open(lp, encoding="utf-8").read()
            for sec in re.split(r"\n## ", md):
                sec = sec.strip()
                if not sec:
                    continue
                title = sec.splitlines()[0].strip("# ")
                docs.append({"id": f"learn:{title[:40]}", "type": "learning",
                             "title": title, "text": _clean(sec, 1500), "meta": {}})
        return docs

    def stats(self):
        return {
            "shikigami": len(self.shikigami_list),
            "shikigami_full": len(self.shikigami_full),
            "souls": len(self.souls),
            "modes": len(self.modes),
            "screens_labeled": len({st.get("label") for st in self.world["states"].values()
                                    if st.get("label")}),
            "documents": len(self.documents()),
        }


def main():
    kb = KB()
    if len(sys.argv) < 2 or sys.argv[1] == "stats":
        print(json.dumps(kb.stats(), ensure_ascii=False, indent=2))
        return
    cmd = sys.argv[1]
    q = " ".join(sys.argv[2:])
    if cmd == "docs":
        docs = kb.documents()
        print(f"{len(docs)} documents. Loai:",
              {t: sum(1 for d in docs if d["type"] == t)
               for t in {d["type"] for d in docs}})
        for d in docs[:5]:
            print(f"  [{d['type']}] {d['title']}: {d['text'][:80]}...")
    elif cmd == "shikigami":
        for s in kb.shikigami(q)[:15]:
            print(f"#{s['id']:>3} [{s['rarity']}] {s['name_en']} / {s['name_cn']}")
    elif cmd == "soul":
        for s in kb.soul(q)[:10]:
            print(f"#{s['no']} {s['name_en']} [{s['type']}]")
            print(f"   2: {s['combo2']}\n   4: {s['combo4']}")
    elif cmd == "mode":
        for k, v in kb.mode(q).items():
            print(f"=== {k} ===\n{_clean(v, 400)}\n")
    elif cmd == "screen":
        for s in kb.screen(q):
            print(f"  {s['label']}: {s['desc']}")
    else:
        print("unknown cmd")


if __name__ == "__main__":
    main()
