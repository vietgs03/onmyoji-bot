#!/usr/bin/env python3
"""Memory tree - cay nho phan cap cua du an. Query + render.

Usage:
  python knowledge/memory.py              # render cay markdown
  python knowledge/memory.py find <q>     # tim node chua <q> (key/value)
  python knowledge/memory.py path a.b.c   # lay node theo duong dan
  python knowledge/memory.py json         # in raw json
"""
import json, sys, os

ROOT = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.join(ROOT, "MEMORY_TREE.json")


def load():
    return json.load(open(TREE, encoding="utf-8"))


def render(node, indent=0, key=None):
    pad = "  " * indent
    out = []
    if isinstance(node, dict):
        if key:
            out.append(f"{pad}- **{key}**")
        for k, v in node.items():
            out += render(v, indent + (1 if key else 0), k)
    elif isinstance(node, list):
        out.append(f"{pad}- **{key}**: {', '.join(map(str, node))}")
    else:
        out.append(f"{pad}- **{key}**: {node}")
    return out


def find(node, q, trail=""):
    q = q.lower()
    hits = []
    if isinstance(node, dict):
        for k, v in node.items():
            t = f"{trail}.{k}" if trail else k
            if q in str(k).lower():
                hits.append((t, _short(v)))
            hits += find(v, q, t)
    elif isinstance(node, list):
        for v in node:
            if q in str(v).lower():
                hits.append((trail, str(v)))
    else:
        if q in str(node).lower():
            hits.append((trail, str(node)))
    return hits


def _short(v):
    s = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
    return s[:120] + ("..." if len(s) > 120 else "")


def get_path(node, path):
    for p in path.split("."):
        node = node[p]
    return node


def main():
    d = load()
    if len(sys.argv) < 2:
        print(f"# {d['project']} - Memory Tree\n> {d['target']}\n")
        print("\n".join(render(d["tree"])))
        return
    cmd = sys.argv[1]
    if cmd == "json":
        print(json.dumps(d, ensure_ascii=False, indent=2))
    elif cmd == "find":
        for t, v in find(d, sys.argv[2]):
            print(f"  {t}: {v}")
    elif cmd == "path":
        print(json.dumps(get_path(d, sys.argv[2]), ensure_ascii=False, indent=2))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
