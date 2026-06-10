"""graph_memory.py - BO NHO DO THI man hinh (PHAN C) tren nen state_matrix.

Node  = 1 man hinh, dac trung boi FeatureMatrix (state_matrix). Luu label,
        affordance da thu, so lan tham.
Edge  = (node_A) --[action ngu nghia]--> (node_B) voi dem thanh cong/that bai.
        Action KHONG luu toa do cung lam dinh danh (toa do chi la goi y cache).
Index = inverted-index token -> node + band-index dhash cell -> node.
        nearest() chi cham similarity day du voi UNG VIEN tu index,
        khong quet tuyen tinh O(n) toan graph.

API chinh:
    gm = GraphMemory.load()
    nid = gm.observe(img, words)        # match node cu / tao node moi
    gm.add_transition(a, action, b)     # ghi canh sau 1 hanh dong
    gm.path(a, b)                       # Dijkstra theo do tin cay canh
    gm.nearest(feat)                    # (node_id, sim) qua index
    gm.save()

CLI:
    .venv/bin/python automation/graph_memory.py stats
    .venv/bin/python automation/graph_memory.py import-shots   # nap 91 anh cu
    .venv/bin/python automation/graph_memory.py test           # self-test
"""
from __future__ import annotations

import heapq
import json
import os
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "automation"), os.path.join(ROOT, "ml"),
          os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from state_matrix import (FeatureMatrix, GRID_COLS, GRID_ROWS,  # noqa: E402
                          SAME_THRESH, extract, similarity)

STORE = os.path.join(ROOT, "knowledge", "graph_memory.json")

# Band-index dhash: chia 64 bit cua moi cell hash thanh BANDS dai 16 bit.
# 2 anh cung man -> nhieu cell hash gan giong -> trung it nhat 1 band o
# nhieu cell (nguyen ly LSH banding). Chi can 1 band trung la thanh ung vien.
_BANDS = 4
_BAND_BITS = 16
_BAND_MASK = (1 << _BAND_BITS) - 1


class GraphMemory:
    def __init__(self):
        self.nodes: dict[str, dict] = {}      # id -> {feat, label, visits, ...}
        self._feats: dict[str, FeatureMatrix] = {}
        self.edges: dict[str, dict[str, dict]] = defaultdict(dict)
        #   edges[a][action] = {"to": b, "ok": n, "fail": n, "hint_xy": [x,y]}
        self._tok_index: dict[str, set] = defaultdict(set)    # token -> {node}
        self._band_index: dict[tuple, set] = defaultdict(set)  # (cell,band,val) -> {node}
        self._next_id = 0

    # ------------------------------------------------------------------ store
    @classmethod
    def load(cls, path: str = STORE) -> "GraphMemory":
        gm = cls()
        if not os.path.exists(path):
            return gm
        with open(path) as fh:
            d = json.load(fh)
        gm._next_id = d.get("next_id", 0)
        for nid, nd in d.get("nodes", {}).items():
            gm.nodes[nid] = nd
            gm._feats[nid] = FeatureMatrix.from_json(nd["feat"])
            gm._index_node(nid)
        for a, acts in d.get("edges", {}).items():
            gm.edges[a] = acts
        return gm

    def save(self, path: str = STORE) -> None:
        d = {"next_id": self._next_id, "nodes": {}, "edges": dict(self.edges)}
        for nid, nd in self.nodes.items():
            nd = dict(nd)
            nd["feat"] = self._feats[nid].to_json()
            d["nodes"][nid] = nd
        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(d, fh)
        os.replace(tmp, path)

    # ------------------------------------------------------------------ index
    def _index_node(self, nid: str) -> None:
        f = self._feats[nid]
        for t in f.sem:
            self._tok_index[t].add(nid)
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                h = f.grid_dhash[r][c]
                for b in range(_BANDS):
                    val = (h >> (b * _BAND_BITS)) & _BAND_MASK
                    self._band_index[(r * GRID_COLS + c, b, val)].add(nid)

    def _candidates(self, feat: FeatureMatrix, min_votes: int = 2) -> list:
        """Ung vien tu index: node trung token HOAC trung >= min_votes band."""
        votes: dict[str, int] = defaultdict(int)
        for t in feat.sem:
            for nid in self._tok_index.get(t, ()):
                votes[nid] += 3            # token trung = bang chung manh
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                h = feat.grid_dhash[r][c]
                for b in range(_BANDS):
                    val = (h >> (b * _BAND_BITS)) & _BAND_MASK
                    for nid in self._band_index.get((r * GRID_COLS + c, b, val), ()):
                        votes[nid] += 1
        ranked = sorted(votes.items(), key=lambda kv: -kv[1])
        return [nid for nid, v in ranked if v >= min_votes][:20]

    # ------------------------------------------------------------------- core
    def nearest(self, feat: FeatureMatrix) -> tuple[str | None, float]:
        """Node giong nhat (qua index). Tra (node_id|None, similarity)."""
        best_id, best_sim = None, 0.0
        for nid in self._candidates(feat):
            sim = similarity(self._feats[nid], feat)["combined"]
            if sim > best_sim:
                best_id, best_sim = nid, sim
        return best_id, best_sim

    def observe(self, img=None, words=None, feat: FeatureMatrix | None = None,
                label: str = "", thresh: float = SAME_THRESH) -> str:
        """Match frame vao node cu hoac tao node moi. Tra node_id."""
        if feat is None:
            feat = extract(img, words)
        nid, sim = self.nearest(feat)
        if nid is not None and sim >= thresh:
            self.nodes[nid]["visits"] += 1
            self.nodes[nid]["last_seen"] = time.time()
            return nid
        nid = f"N{self._next_id:04d}"
        self._next_id += 1
        self.nodes[nid] = {
            "label": label or "/".join(sorted(feat.sem)[:3]) or "(no-text)",
            "visits": 1, "created": time.time(), "last_seen": time.time(),
        }
        self._feats[nid] = feat
        self._index_node(nid)
        return nid

    def add_transition(self, a: str, action: str, b: str,
                       ok: bool = True, hint_xy=None) -> None:
        """Ghi canh a --action--> b. action = mo ta ngu nghia ('tap:Explore',
        'back', 'swipe:left'...), khong phai toa do."""
        e = self.edges[a].get(action)
        if e is None or e.get("to") != b:
            e = {"to": b, "ok": 0, "fail": 0}
            self.edges[a][action] = e
        e["ok" if ok else "fail"] += 1
        if hint_xy is not None:
            e["hint_xy"] = list(hint_xy)

    def path(self, src: str, dst: str) -> list[tuple[str, str]] | None:
        """Dijkstra: chi phi canh = 1/do-tin-cay (canh hay fail thi dat).
        Tra [(node, action), ...] khong gom dst, None neu khong co duong."""
        if src == dst:
            return []
        pq = [(0.0, src, [])]
        seen = set()
        while pq:
            cost, cur, trail = heapq.heappop(pq)
            if cur in seen:
                continue
            seen.add(cur)
            for action, e in self.edges.get(cur, {}).items():
                to = e["to"]
                rel = (e["ok"] + 1) / (e["ok"] + e["fail"] + 2)  # Laplace
                nc = cost + 1.0 / rel
                nt = trail + [(cur, action)]
                if to == dst:
                    return nt
                if to not in seen:
                    heapq.heappush(pq, (nc, to, nt))
        return None

    def graph_features(self, nid: str, hub: str | None = None) -> dict:
        """Dac trung vi tri trong graph: bac ra/vao, khoang cach toi hub."""
        out_deg = len(self.edges.get(nid, {}))
        in_deg = sum(1 for acts in self.edges.values()
                     for e in acts.values() if e["to"] == nid)
        feats = {"out_deg": out_deg, "in_deg": in_deg}
        if hub and hub in self.nodes:
            p = self.path(nid, hub)
            feats["dist_to_hub"] = len(p) if p is not None else -1
        return feats

    def stats(self) -> dict:
        n_edges = sum(len(a) for a in self.edges.values())
        return {"nodes": len(self.nodes), "edges": n_edges,
                "tokens_indexed": len(self._tok_index),
                "bands_indexed": len(self._band_index)}


# --------------------------------------------------------------------- CLI

def _import_shots():
    """Nap 91 anh logs/explore_shots vao graph (dung feat cache cua state_matrix)."""
    from state_matrix import _load_feats
    shot_dir = os.path.join(ROOT, "logs", "explore_shots")
    paths = [os.path.join(shot_dir, f) for f in sorted(os.listdir(shot_dir))
             if f.endswith(".png")]
    feats = _load_feats(paths)
    gm = GraphMemory.load()
    mapping = {}
    for p, f in feats.items():
        mapping[os.path.basename(p)] = gm.observe(feat=f)
    gm.save()
    n_uniq = len(set(mapping.values()))
    print(f"import {len(mapping)} anh -> {n_uniq} node (gop {len(mapping) - n_uniq} trung)")
    print("stats:", gm.stats())


def _self_test():
    """Test logic graph thuan (khong can anh): observe/edge/path/index."""
    import numpy as np
    gm = GraphMemory()

    def fake_feat(tokens, seed):
        rng = np.random.default_rng(seed)
        gh = [[int(rng.integers(0, 2 ** 63)) for _ in range(GRID_COLS)]
              for _ in range(GRID_ROWS)]
        gt = [[set() for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
        for i, t in enumerate(tokens):
            gt[i % GRID_ROWS][i % GRID_COLS].add(t)
        return FeatureMatrix(sem=set(tokens), grid_tokens=gt, grid_dhash=gh)

    home = fake_feat(["explore", "summon", "town", "shop", "guild"], 1)
    menu = fake_feat(["realmraid", "orochi", "soulzones", "areaboss"], 2)
    battle = fake_feat(["challenge", "lineup", "presets", "auto"], 3)

    h = gm.observe(feat=home, label="HOME")
    m = gm.observe(feat=menu, label="explore_menu")
    b = gm.observe(feat=battle, label="battle_prep")
    assert len({h, m, b}) == 3, "3 man khac nhau phai ra 3 node"

    # cung man (cung feat) -> cung node
    h2 = gm.observe(feat=home)
    assert h2 == h, f"cung feat phai cung node: {h2} != {h}"

    # bien the nho cua HOME (mat 1 token, hash giong) -> van match
    home_v = FeatureMatrix(sem=set(list(home.sem)[:-1]),
                           grid_tokens=home.grid_tokens,
                           grid_dhash=home.grid_dhash)
    h3 = gm.observe(feat=home_v)
    assert h3 == h, f"bien the nho phai match node cu: {h3} != {h}"

    gm.add_transition(h, "tap:Explore", m, hint_xy=(59, 89))
    gm.add_transition(m, "tap:RealmRaid", b)
    gm.add_transition(b, "back", m)
    gm.add_transition(m, "back", h)

    p = gm.path(h, b)
    assert p == [(h, "tap:Explore"), (m, "tap:RealmRaid")], f"path sai: {p}"
    p2 = gm.path(b, h)
    assert p2 == [(b, "back"), (m, "back")], f"path nguoc sai: {p2}"

    # canh fail nhieu phai bi ne khi co duong khac
    alt = gm.observe(feat=fake_feat(["via", "alt"], 9), label="alt")
    for _ in range(10):
        gm.add_transition(h, "tap:BadBtn", alt, ok=False)
    gm.add_transition(alt, "tap:To", b)
    p3 = gm.path(h, b)
    assert p3[0][1] == "tap:Explore", f"phai ne canh fail: {p3}"

    # round-trip save/load
    tmp = "/tmp/_gm_test.json"
    gm.save(tmp)
    gm2 = GraphMemory.load(tmp)
    assert gm2.stats() == gm.stats(), "save/load lech"
    assert gm2.observe(feat=home_v) == h, "match sau khi load lech"
    os.remove(tmp)
    print("self-test OK:", gm.stats())


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "stats":
        print(GraphMemory.load().stats())
    elif cmd == "import-shots":
        _import_shots()
    elif cmd == "test":
        _self_test()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
