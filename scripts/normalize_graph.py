#!/usr/bin/env python3
"""normalize_graph.py - Don dep + chuan hoa world graph (exploration/world.json).

Vi sao (review thuat toan): kham pha tu nhieu nguon (automation cu + self-learning
moi) sinh ra:
  1. LABEL ALIAS: cung 1 man co 2 ten (vd 'Explore' cu vs 'Exploration' moi) ->
     bfs_path DUT MACH (HOME->Explore co edge, nhung chuoi moi tu Exploration).
  2. NODE RAC: node khong label + khong verified_elements + khong edge -> phinh graph.
  3. EDGE TU-THAN (from==to logic) hoac edge toi node da xoa.

Tool nay (idempotent, co --dry):
  - Gop label theo ALIASES (giu ten chuan).
  - Xoa node mo coi hoan toan.
  - Xoa edge tro toi node khong ton tai + edge tu-than logic.
  - Bao cao truoc/sau.

Chay:
  python3 scripts/normalize_graph.py --dry     # xem se lam gi
  python3 scripts/normalize_graph.py           # ap dung (tu backup .bak)
"""
import json
import os
import sys
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(ROOT, "exploration", "world.json")

# Cac label la ALIAS cua nhau -> gop ve ten CHUAN (value). Chi gop khi CHAC chan
# cung man (da verify bang vision trong session). KHONG doan bua.
ALIASES = {
    "Exploration": "Explore",  # man farm hub: ten moi (self-learn) == ten cu (OAS page_exploration)
}

# Element label -> Screen label (khi nut tren man hub TEN khac man dich, vd nut
# 'Totem' tren Explore mo man 'TotemZone'). Dung de SUY edge forward tu verified
# element (xem _derive_forward_edges). Chi map khi CHAC chan (da verify vision).
ELEMENT_TO_SCREEN = {
    "Totem": "TotemZone",
    "SecretZone": "SecretZone",
    "AreaBoss": "AreaBoss",
    "EvoMaterial": "EvolutionZone",
    "BondlingFairyland": "BondlingFairyland",
    "Explore": "Explore",
    "Town": "Town",
    "Shop": "Shop",
    "Summon": "Summon",
    "Shikigami": "Shikigami",
    "Onmyoji": "OnmyojiInfo",
    "Arena": "ArenaHub",
    "DemonParade": "DemonParade",
}


def _logical_dst(states, sid):
    lbl = states.get(sid, {}).get("label")
    return f"L:{lbl}" if lbl else sid


def _derive_forward_edges(S, E):
    """SUY edge forward tu verified_elements: neu man HUB co element ten X (vd
    'Soul') va ton tai man label X (hoac map qua ELEMENT_TO_SCREEN) -> tao edge
    hub -click(x,y)-> X. Vi sao: edge forward hay bi MISS khi click_at observe
    trung loading frame (man dich qua animation lau). Element da verify (toa do
    + label) la bang chung CHAC CHAN nut do dan toi man X -> suy edge an toan.
    Tra so edge them."""
    # label -> 1 sid dai dien (uu tien node co label)
    label_sid = {}
    for sid, st in S.items():
        lbl = st.get("label")
        if lbl and lbl not in label_sid:
            label_sid[lbl] = sid
    existing = {(e["from"], tuple(e["click"]), e["to"]) for e in E}
    added = 0
    for sid, st in S.items():
        if not st.get("label"):
            continue
        for el in st.get("verified_elements", []):
            ell = el.get("label", "")
            screen = ELEMENT_TO_SCREEN.get(ell, ell if ell in label_sid else None)
            if not screen or screen not in label_sid:
                continue
            dst = label_sid[screen]
            if _logical_dst(S, sid) == _logical_dst(S, dst):
                continue  # tu-than (vd back)
            click = (int(el["cx"]), int(el["cy"]))
            key = (sid, click, dst)
            if key in existing:
                continue
            E.append({"from": sid, "click": list(click), "to": dst})
            existing.add(key)
            added += 1
    return added


def main(dry: bool):
    w = json.load(open(WORLD, encoding="utf-8"))
    S, E = w["states"], w["edges"]
    n0_states, n0_edges = len(S), len(E)

    # 1) gop label alias
    alias_hits = 0
    for sid, st in S.items():
        lbl = st.get("label")
        if lbl in ALIASES:
            st["label"] = ALIASES[lbl]
            alias_hits += 1

    # 2) tap node duoc tham chieu boi edge
    edge_nodes = set()
    for e in E:
        edge_nodes.add(e["from"])
        edge_nodes.add(e["to"])

    # 3) xoa node mo coi (khong label + khong verified + khong edge + khong screenshot)
    drop = []
    for sid, st in S.items():
        if (not st.get("label") and not st.get("verified_elements")
                and sid not in edge_nodes and not st.get("screenshot")):
            drop.append(sid)
    for sid in drop:
        del S[sid]

    # 4) xoa edge tro toi node khong ton tai + edge tu-than LOGIC (cung label)
    kept = []
    drop_edge = 0
    for e in E:
        if e["from"] not in S or e["to"] not in S:
            drop_edge += 1
            continue
        if _logical_dst(S, e["from"]) == _logical_dst(S, e["to"]):
            drop_edge += 1
            continue
        kept.append(e)
    # dedup edge (cung from-click-to)
    seen = set()
    uniq = []
    for e in kept:
        k = (e["from"], tuple(e["click"]), e["to"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    w["edges"] = uniq

    # 5) SUY edge forward tu verified_elements (vá edge forward bi miss do loading)
    fwd = _derive_forward_edges(S, w["edges"])

    print(f"label alias gop: {alias_hits}")
    print(f"node: {n0_states} -> {len(S)} (xoa {len(drop)} mo coi)")
    print(f"edge: {n0_edges} -> {len(w['edges'])} (xoa {drop_edge} rac + {len(kept)-len(uniq)} trung, SUY them {fwd} forward)")

    if dry:
        print("[DRY] khong ghi. Bo --dry de ap dung.")
        return
    shutil.copy(WORLD, WORLD + ".bak")
    json.dump(w, open(WORLD, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"da ghi {WORLD} (backup .bak)")


if __name__ == "__main__":
    main("--dry" in sys.argv)
