#!/usr/bin/env python3
"""
Semantic labeling layer (Tang B).

Cong cu de gan NHAN + MO TA + cac NUT cho moi state trong world.json.
Vi agent (toi) la vision model, toi xem screenshot roi goi:

    label_states.py set <sid> "Label" "mo ta chuc nang"
    label_states.py addbtn <sid> X Y "ten nut" "tac dung"
    label_states.py show            # liet ke state chua label
    label_states.py dump            # in toan bo nhan

Nhan duoc luu vao world.json (states[sid].label/desc/buttons[]).
Day la "tu hoi nut nay lam gi" -> tra loi -> luu lai = self-documenting graph.
"""
import sys, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(ROOT, "exploration", "world.json")

def load():
    return json.load(open(WORLD, encoding="utf-8"))

def save(d):
    json.dump(d, open(WORLD, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    d = load()
    states = d["states"]
    if cmd == "set":
        sid, label, desc = sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else ""
        states[sid]["label"] = label
        states[sid]["desc"] = desc
        save(d); print(f"set {sid} = {label}")
    elif cmd == "addbtn":
        sid, x, y, name = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
        eff = sys.argv[6] if len(sys.argv) > 6 else ""
        states[sid].setdefault("buttons", []).append(
            {"x": x, "y": y, "name": name, "effect": eff})
        save(d); print(f"addbtn {sid}: {name}")
    elif cmd == "show":
        for sid, st in states.items():
            if not st.get("label"):
                print(f"UNLABELED {sid}  {st['screenshot']}")
    elif cmd == "dump":
        for sid, st in states.items():
            print(f"\n=== {sid}  [{st.get('label') or '?'}] ===")
            print(f"    {st.get('desc') or ''}")
            for b in st.get("buttons", []):
                print(f"    btn ({b['x']},{b['y']}) {b['name']}: {b['effect']}")
            # edges di ra
            outs = [e for e in d["edges"] if e["from"] == sid]
            for e in outs:
                to_lbl = states.get(e["to"], {}).get("label") or e["to"]
                print(f"    --click{e['click']}--> {to_lbl}")
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
