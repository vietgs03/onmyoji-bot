"""agent_bus.py - kenh noi chuyen giua 2 agent (OPERATOR choi game / ANALYST phan tich).

Blackboard don gian: logs/agent_bus.jsonl, moi dong 1 message JSON:
    {"ts", "frm", "to", "type", "text", "data"}
type: report | question | directive | hypothesis | result

CLI:
    python automation/agent_bus.py send <frm> <to> <type> "<text>" ['<json-data>']
    python automation/agent_bus.py read [--for AGENT] [--since TS] [--new AGENT]
        --new AGENT: chi in message CHUA doc cua AGENT (con tro logs/.bus_cursor_AGENT)
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUS = os.path.join(ROOT, "logs", "agent_bus.jsonl")


def send(frm: str, to: str, mtype: str, text: str, data=None) -> dict:
    msg = {"ts": round(time.time(), 1), "frm": frm, "to": to,
           "type": mtype, "text": text}
    if data is not None:
        msg["data"] = data
    os.makedirs(os.path.dirname(BUS), exist_ok=True)
    with open(BUS, "a") as fh:
        fh.write(json.dumps(msg, ensure_ascii=False) + "\n")
    return msg


def read(for_agent: str | None = None, since: float = 0.0) -> list:
    if not os.path.exists(BUS):
        return []
    out = []
    with open(BUS) as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            if m.get("ts", 0) <= since:
                continue
            if for_agent and m.get("to") not in (for_agent, "*"):
                continue
            out.append(m)
    return out


def read_new(agent: str) -> list:
    """Message chua doc cua agent (luu con tro byte-offset)."""
    cur_path = os.path.join(ROOT, "logs", f".bus_cursor_{agent}")
    pos = 0
    if os.path.exists(cur_path):
        try:
            pos = int(open(cur_path).read().strip())
        except ValueError:
            pos = 0
    out = []
    if os.path.exists(BUS):
        with open(BUS) as fh:
            fh.seek(pos)
            for line in fh:
                try:
                    m = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if m.get("to") in (agent, "*"):
                    out.append(m)
            pos = fh.tell()
    with open(cur_path, "w") as fh:
        fh.write(str(pos))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "send":
        frm, to, mtype, text = sys.argv[2:6]
        data = json.loads(sys.argv[6]) if len(sys.argv) > 6 else None
        m = send(frm, to, mtype, text, data)
        print("sent:", json.dumps(m, ensure_ascii=False)[:200])
    elif cmd == "read":
        args = sys.argv[2:]
        if "--new" in args:
            msgs = read_new(args[args.index("--new") + 1])
        else:
            for_agent = args[args.index("--for") + 1] if "--for" in args else None
            since = float(args[args.index("--since") + 1]) if "--since" in args else 0.0
            msgs = read(for_agent, since)
        for m in msgs:
            print(json.dumps(m, ensure_ascii=False))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
