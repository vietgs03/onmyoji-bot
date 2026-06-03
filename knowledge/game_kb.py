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
        self.skills = _load(os.path.join(FANDOM, "shikigami_skills.json"), {})
        self.battle = _load(os.path.join(FANDOM, "battle_mechanics.json"), {})
        self.progression = _load(os.path.join(FANDOM, "progression_guide.json"), {})
        self.features = _load(os.path.join(os.path.dirname(__file__), "oas_features.json"), [])
        self.world = _load(os.path.join(EXP, "world.json"), {"states": {}, "edges": []})
        # wiki_db (Supabase trmzaiu) - shikigami/soul/effect co cau truc, da ngon ngu
        WDB = os.path.join(ROOT, "data", "wiki_db")
        self.wdb_shiki = _load(os.path.join(WDB, "Shikigami.json"), [])
        self.wdb_soul = _load(os.path.join(WDB, "Soul.json"), [])
        self.wdb_effect = _load(os.path.join(WDB, "Effect.json"), [])
        # strategy guides EN (FiresChain/onmyoji-wiki) - chien thuat thuc chien
        self.guides = self._load_guides(os.path.join(ROOT, "data", "external", "firechain", "guides_en"))
        # index nhanh shikigami_full theo ten
        self._sfull = {s.get("name", "").lower(): s for s in self.shikigami_full}

    @staticmethod
    def _load_guides(path):
        """Load markdown guides EN -> list {title, tags, summary, body}."""
        guides = []
        if not os.path.isdir(path):
            return guides
        for fn in sorted(os.listdir(path)):
            if not fn.endswith(".md") or fn == "index.md":
                continue
            raw = open(os.path.join(path, fn), encoding="utf-8").read().lstrip("\ufeff")
            meta, body = {}, raw
            m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.DOTALL)
            if m:
                for line in m.group(1).splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip()
                body = m.group(2)
            body = re.sub(r"[#*`>\-]+", " ", body)
            body = re.sub(r"\s+", " ", body).strip()
            guides.append({"file": fn, "title": meta.get("title", fn),
                           "tags": meta.get("tags", ""), "summary": meta.get("summary", ""),
                           "body": body})
        return guides

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

    def skill(self, shiki_name):
        """Tra skill cua 1 shikigami (khop ten EN gan dung)."""
        ql = shiki_name.lower()
        for name, info in self.skills.items():
            if ql in name.lower():
                return {"name": name, **info}
        return None

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
            sk = self.skills.get(title, {})
            skill_txt = ""
            if sk.get("skills"):
                skill_txt = " Skills: " + "; ".join(
                    f"{k['name']} - {k.get('desc','')[:120]}" for k in sk["skills"][:4])
            text = (f"Shikigami {title} (CN {s.get('name_cn')}, JP {s.get('name_jp')}), "
                    f"rarity {s.get('rarity')}. CV {f.get('cv','?')}. "
                    f"{'Co phien ban SP.' if f.get('has_sp') else ''}{skill_txt}")
            docs.append({"id": f"shiki:{s.get('id')}", "type": "shikigami",
                         "title": title, "text": text.strip()[:1500],
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
        # 4b) battle mechanics (Formulae/Move Bar/Damage/Skill Effects/...)
        if isinstance(self.battle, dict):
            for name, body in self.battle.items():
                txt = body if isinstance(body, str) else str(body)
                docs.append({"id": f"battle:{name}", "type": "battle",
                             "title": f"Battle: {name.lstrip('_')}",
                             "text": _clean(txt, 1800), "meta": {}})
        # 4c) progression / beginner guide / daily routine
        if isinstance(self.progression, dict):
            for name, body in self.progression.items():
                txt = body if isinstance(body, str) else str(body)
                docs.append({"id": f"prog:{name}", "type": "progression",
                             "title": f"Guide: {name.lstrip('_')}",
                             "text": _clean(txt, 1800), "meta": {}})
        # 4d) game features / activities (trich tu OAS - game co che do/hoat dong gi)
        for f in self.features:
            opts = "; ".join(
                f"{o.get('title') or o.get('field')}: {o.get('desc') or ''}"
                for o in f.get("options", [])[:15])
            methods = ", ".join(f.get("script_methods", [])[:12])
            text = (f"Game activity/mode: {f['name']} (OAS task '{f['task']}'). "
                    f"Do phuc tap: {f.get('templates',0)} template, {f.get('ocr_regions',0)} vung OCR. "
                    f"Tuy chon tu dong hoa: {opts}. "
                    f"Cac buoc/ham xu ly: {methods}.")
            docs.append({"id": f"feature:{f['task']}", "type": "feature",
                         "title": f"Activity: {f['name']}",
                         "text": _clean(text, 1600), "meta": {"task": f["task"]}})
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
        # 7) wiki_db: shikigami giau (skill structured + stats + build/team) - nguon tot nhat
        def _en(n):
            if isinstance(n, dict):
                return n.get("en") or (n.get("cn", [""])[0] if isinstance(n.get("cn"), list) else n.get("cn"))
            return n

        for s in self.wdb_shiki:
            title = _en(s.get("name")) or f"shiki-{s.get('id')}"
            sk = s.get("skills") or []
            skill_txt = "; ".join(
                f"{_en(k.get('name'))} ({k.get('type','')}, onibi {k.get('onibi',0)}, cd {k.get('cooldown',0)}): "
                f"{_en(k.get('description')) or ''}"[:160] for k in sk[:4])
            st = s.get("stats") or {}
            stat_txt = ", ".join(f"{k} {v}" for k, v in st.items()) if isinstance(st, dict) else ""
            builds = s.get("build") or []
            build_txt = "; ".join(
                f"role {b.get('role')}: souls {b.get('souls')}, sub {b.get('substats')}"
                for b in builds[:3]) if isinstance(builds, list) else ""
            prof = _en(s.get("profile")) or ""
            text = (f"Shikigami {title}, rarity {s.get('rarity')}. "
                    f"Stats(min,max): {stat_txt}. Skills: {skill_txt}. "
                    f"Team build: {build_txt}. {prof[:300]}")
            docs.append({"id": f"wshiki:{s.get('id')}", "type": "shikigami_db",
                         "title": title, "text": text.strip()[:1900],
                         "meta": {"rarity": s.get("rarity")}})
        # 7b) wiki_db souls (structured effects)
        for s in self.wdb_soul:
            title = _en(s.get("name"))
            eff = s.get("effects") or {}
            p2 = _en(eff.get("piece2", {})) if isinstance(eff, dict) else ""
            p4 = _en(eff.get("piece4", {})) if isinstance(eff, dict) else ""
            text = (f"Soul/Mitama {title}, type {s.get('type')}. "
                    f"2-set: {_clean(str(p2), 300)}. 4-set: {_clean(str(p4), 400)}.")
            docs.append({"id": f"wsoul:{s.get('id')}", "type": "soul_db",
                         "title": title, "text": text, "meta": {"type": s.get("type")}})
        # strategy guides EN (chien thuat thuc chien: team setup/speed tuning)
        for g in self.guides:
            text = (f"Strategy guide: {g['title']}. {g['summary']} "
                    f"Tags: {g['tags']}. {_clean(g['body'], 1500)}")
            docs.append({"id": f"guide:{g['file']}", "type": "strategy",
                         "title": g["title"], "text": text, "meta": {"tags": g["tags"]}})
        return docs

    def stats(self):
        return {
            "shikigami": len(self.shikigami_list),
            "shikigami_full": len(self.shikigami_full),
            "shikigami_with_skills": len(self.skills),
            "total_skills": sum(len(v.get("skills", [])) for v in self.skills.values()),
            "souls": len(self.souls),
            "modes": len(self.modes),
            "battle_pages": len(self.battle),
            "progression_pages": len(self.progression),
            "game_features": len(self.features),
            "wikidb_shikigami": len(self.wdb_shiki),
            "wikidb_soul": len(self.wdb_soul),
            "wikidb_effect": len(self.wdb_effect),
            "strategy_guides": len(self.guides),
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
    elif cmd == "skill":
        sk = kb.skill(q)
        if sk:
            print(f"=== {sk['name']} [{sk.get('rarity')}] ===")
            for k in sk.get("skills", []):
                print(f"  - {k['name']} ({k.get('type','?')}): {k.get('desc','')[:200]}")
        else:
            print("khong tim thay")
    elif cmd == "mode":
        for k, v in kb.mode(q).items():
            print(f"=== {k} ===\n{_clean(v, 400)}\n")
    elif cmd == "screen":
        for s in kb.screen(q):
            print(f"  {s['label']}: {s['desc']}")
    elif cmd == "features":
        for f in sorted(kb.features, key=lambda z: -z.get("templates", 0)):
            if q and q.lower() not in f["name"].lower():
                continue
            print(f"• {f['name']}  [{f.get('templates',0)} tmpl]")
            if q:  # chi tiet khi loc 1 task
                for o in f.get("options", [])[:12]:
                    print(f"    - {o.get('title') or o.get('field')}: {o.get('desc') or ''}")
    else:
        print("unknown cmd")


if __name__ == "__main__":
    main()
