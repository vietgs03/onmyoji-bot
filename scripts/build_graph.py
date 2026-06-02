#!/usr/bin/env python3
"""
Build LOGICAL graph tu world.json (physical states) bang cach gom theo LABEL.

Van de: 1 man hinh (vd HOME) co the sinh nhieu physical state (sid) do camera/
nhan vat dong. Sau khi label, ta gom cac sid CUNG LABEL ve 1 node logic.

Output:
  exploration/graph_logical.json   {nodes:{label:{sids,desc,count}}, edges:[{from,to,clicks}]}
  exploration/graph.md             ban do doc duoc + mermaid
"""
import json, os, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "exploration")
WORLD = os.path.join(EXP, "world.json")

def build():
    d = json.load(open(WORLD, encoding="utf-8"))
    states, edges = d["states"], d["edges"]

    # map sid -> label (fallback: sid neu chua label)
    lbl = {sid: (st.get("label") or sid) for sid, st in states.items()}

    nodes = collections.defaultdict(lambda: {"sids": [], "descs": set()})
    for sid, st in states.items():
        n = nodes[lbl[sid]]
        n["sids"].append(sid)
        if st.get("desc"):
            n["descs"].add(st["desc"])

    # gom edge theo (label_from, label_to), bo self-loop (HOME->HOME do camera)
    logical_edges = collections.defaultdict(list)
    for e in edges:
        a, b = lbl[e["from"]], lbl[e["to"]]
        if a == b:
            continue
        logical_edges[(a, b)].append(e["click"])

    out_nodes = {k: {"sids": v["sids"], "count": len(v["sids"]),
                     "desc": " | ".join(sorted(v["descs"]))}
                 for k, v in nodes.items()}
    out_edges = [{"from": a, "to": b, "clicks": clicks}
                 for (a, b), clicks in logical_edges.items()]

    json.dump({"nodes": out_nodes, "edges": out_edges},
              open(os.path.join(EXP, "graph_logical.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # markdown + mermaid
    md = ["# Onmyoji UI Graph (logical)\n",
          f"Nodes: {len(out_nodes)}  Edges: {len(out_edges)}\n",
          "## Nodes\n"]
    for k, v in sorted(out_nodes.items(), key=lambda x: -x[1]["count"]):
        md.append(f"- **{k}** (x{v['count']} physical): {v['desc']}")
    md.append("\n## Transitions\n")
    for e in out_edges:
        md.append(f"- {e['from']} --click {e['clicks'][0]}--> {e['to']}")
    md.append("\n## Mermaid\n```mermaid\ngraph TD")
    def nid(s): return "".join(c for c in s if c.isalnum()) or "X"
    for e in out_edges:
        md.append(f"    {nid(e['from'])}[{e['from']}] --> {nid(e['to'])}[{e['to']}]")
    md.append("```\n")
    open(os.path.join(EXP, "graph.md"), "w", encoding="utf-8").write("\n".join(md))

    print(f"Logical nodes: {len(out_nodes)}, edges: {len(out_edges)}")
    for k, v in sorted(out_nodes.items(), key=lambda x: -x[1]["count"]):
        print(f"  {k:20s} x{v['count']}")
    print(f"-> {os.path.join(EXP,'graph.md')}")

if __name__ == "__main__":
    build()
