#!/usr/bin/env python3
"""Phan tich shikigami/team/soul tu wiki_db (Supabase structured).

Dung data co cau truc (build/stats/skills/souls/tags) de tra cuu & goi y.
Khong phai vector search (nguoi dung hoi tu nhien -> dung vectordb.py).
Cai nay tra cuu CHINH XAC theo field (role, soul, tag, stat).

CLI:
  python analyzer.py shiki <ten>          # full info 1 shikigami (skill/stat/build)
  python analyzer.py role <role>          # liet ke shikigami theo role (healer/dps/control...)
  python analyzer.py soul <ten>           # ai dung soul nay (theo build)
  python analyzer.py tag <tag>            # shikigami co skill tag (revive/shield/debuff...)
  python analyzer.py fastest [n]          # top N shikigami SPD cao nhat (speedrun)
  python analyzer.py team <role,role,...> # goi y team theo cac role yeu cau
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WDB = os.path.join(ROOT, "data", "wiki_db")


def _load(name):
    return json.load(open(os.path.join(WDB, name), encoding="utf-8"))


def _en(field):
    """name/desc field co the la dict {en,cn,...} hoac str."""
    if isinstance(field, dict):
        v = field.get("en")
        return v if isinstance(v, str) else (v[0] if isinstance(v, list) and v else "")
    return field or ""


class Analyzer:
    def __init__(self):
        self.shiki = _load("Shikigami.json")
        self.souls = _load("Soul.json")
        self.tags = _load("Tag.json")
        # index
        self.soul_by_id = {s["id"]: _en(s.get("name")) for s in self.souls}
        self.tag_by_id = {t["id"]: _en(t.get("name")) for t in self.tags}
        self.name_index = {_en(s.get("name")).lower(): s for s in self.shiki}

    # ---------- tra cuu 1 shikigami ----------
    def find(self, q):
        ql = q.lower()
        if ql in self.name_index:
            return self.name_index[ql]
        for s in self.shiki:
            nm = s.get("name") or {}
            allnames = [_en(nm)] + ([nm.get("vn")] if isinstance(nm, dict) else [])
            cn = nm.get("cn") if isinstance(nm, dict) else None
            if cn:
                allnames += cn if isinstance(cn, list) else [cn]
            if any(ql in str(x).lower() for x in allnames if x):
                return s
        return None

    def describe(self, s):
        nm = _en(s.get("name"))
        out = [f"# {nm} ({s.get('rarity')})"]
        st = s.get("stats") or {}
        if st:
            out.append("Stats (min-max): " + ", ".join(
                f"{k} {v[0]}-{v[1]}" if isinstance(v, list) else f"{k} {v}"
                for k, v in st.items()))
        for b in (s.get("build") or []):
            souls = " / ".join(self.soul_by_id.get(i, f"#{i}") for i in (b.get("souls") or []))
            out.append(f"Build [{b.get('role')}]: souls={souls}; "
                       f"stats={b.get('indicate')}; sub={b.get('substats')}; "
                       f"breakpoint={b.get('breakpoint')}")
        for sk in (s.get("skills") or []):
            tags = ", ".join(self.tag_by_id.get(t, str(t)) for t in (sk.get("tags") or []))
            out.append(f"Skill {_en(sk.get('name'))} ({sk.get('type')}, "
                       f"onibi {sk.get('onibi')}, CD {sk.get('cooldown')}) "
                       f"[{tags}]: {_en(sk.get('description'))}")
        return "\n".join(out)

    # ---------- loc theo role ----------
    ROLE_ALIAS = {
        "control": ["cc", "control"], "cc": ["cc", "control"],
        "dps": ["dps", "damage"], "damage": ["dps", "damage"],
        "tank": ["tank", "shield"], "support": ["support", "buff", "debuff"],
    }

    def by_role(self, role):
        rl = role.lower()
        keys = self.ROLE_ALIAS.get(rl, [rl])
        hits = []
        for s in self.shiki:
            for b in (s.get("build") or []):
                rstr = (b.get("role") or "").lower()
                if any(k in rstr for k in keys):
                    hits.append((_en(s.get("name")), s.get("rarity"),
                                 b.get("role") or "(role trong)"))
                    break
        return hits

    def by_soul(self, soul_name):
        sid = next((i for i, n in self.soul_by_id.items()
                    if soul_name.lower() in n.lower()), None)
        if sid is None:
            return []
        hits = []
        for s in self.shiki:
            for b in (s.get("build") or []):
                if sid in (b.get("souls") or []):
                    hits.append((_en(s.get("name")), b.get("role")))
                    break
        return hits

    def by_tag(self, tag_name):
        tid = next((i for i, n in self.tag_by_id.items()
                    if tag_name.lower() in n.lower()), None)
        if tid is None:
            return []
        hits = []
        for s in self.shiki:
            for sk in (s.get("skills") or []):
                if tid in (sk.get("tags") or []):
                    hits.append((_en(s.get("name")), _en(sk.get("name"))))
                    break
        return hits

    def fastest(self, n=15):
        rows = []
        for s in self.shiki:
            spd = (s.get("stats") or {}).get("SPD")
            if isinstance(spd, list) and spd:
                rows.append((_en(s.get("name")), spd[1], s.get("rarity")))
        rows.sort(key=lambda x: -x[1])
        return rows[:n]

    def team(self, roles):
        """Goi y: voi moi role, lay 3 shikigami SSR/SP truoc."""
        order = {"SP": 0, "SSR": 1, "SR": 2, "R": 3, "N": 4}
        out = {}
        for r in roles:
            cands = self.by_role(r)
            cands.sort(key=lambda x: order.get(x[1], 9))
            out[r] = cands[:4]
        return out


def main():
    a = Analyzer()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    arg = " ".join(sys.argv[2:])
    if cmd == "shiki":
        s = a.find(arg)
        print(a.describe(s) if s else f"khong tim thay '{arg}'")
    elif cmd == "role":
        hits = a.by_role(arg)
        print(f"{len(hits)} shikigami role '{arg}':")
        for nm, rar, role in hits[:40]:
            print(f"  {nm:22s} {rar:4s} {role}")
    elif cmd == "soul":
        hits = a.by_soul(arg)
        print(f"{len(hits)} shikigami dung soul '{arg}':")
        for nm, role in hits[:40]:
            print(f"  {nm:22s} {role}")
    elif cmd == "tag":
        hits = a.by_tag(arg)
        print(f"{len(hits)} shikigami co skill tag '{arg}':")
        for nm, sk in hits[:40]:
            print(f"  {nm:22s} ({sk})")
    elif cmd == "fastest":
        n = int(arg) if arg.strip().isdigit() else 15
        print(f"Top {n} SPD cao nhat (speedrun):")
        for nm, spd, rar in a.fastest(n):
            print(f"  {nm:22s} SPD {spd:3d} {rar}")
    elif cmd == "team":
        roles = [r.strip() for r in arg.split(",") if r.strip()]
        for r, cands in a.team(roles).items():
            print(f"[{r}]")
            for nm, rar, role in cands:
                print(f"  {nm:22s} {rar:4s} {role}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
