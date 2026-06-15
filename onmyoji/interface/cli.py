#!/usr/bin/env python3
"""onmyoji.interface.cli - CLI moi theo Clean Architecture.

Day la 1 trong cac "interface adapter" (cung cap voi MCP/harness sau nay).
Tat ca deu di qua Container -> UseCase -> Port.

Dung:
    python -m onmyoji.interface.cli observe          # quan sat man hinh
    python -m onmyoji.interface.cli wait-stable      # doi man on dinh
    python -m onmyoji.interface.cli click 451 188    # click
    python -m onmyoji.interface.cli --eye fake observe   # test khong can game

Mac dinh ONMYOJI_EYE=python. Doi --eye fake de test offline.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from onmyoji.domain.entities import Action
from onmyoji.interface.container import Container


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="onmyoji", description="Onmyoji bot CLI (clean arch)")
    p.add_argument("--eye", choices=["python", "rust", "fake"], help="chon impl Eye")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("observe", help="chup + phan tich man hinh")
    sub.add_parser("wait-stable", help="doi man on dinh")
    c = sub.add_parser("click", help="click toa do"); c.add_argument("x", type=int); c.add_argument("y", type=int)
    pc = sub.add_parser("polite-click"); pc.add_argument("x", type=int); pc.add_argument("y", type=int)
    d = sub.add_parser("drag"); [d.add_argument(a, type=int) for a in ("x0", "y0", "x1", "y1")]
    k = sub.add_parser("key"); k.add_argument("key")
    g = sub.add_parser("goto", help="navigate toi man co label"); g.add_argument("label")
    a = sub.add_parser("ask", help="tra cuu KB"); a.add_argument("query", nargs="+")

    args = p.parse_args(argv)
    if args.eye:
        os.environ["ONMYOJI_EYE"] = args.eye

    container = Container()
    try:
        if args.cmd == "observe":
            ctx = container.perceive().execute()
            _print(ctx.observation.to_dict())
        elif args.cmd == "wait-stable":
            obs = container.wait_stable().execute()
            _print(obs.to_dict())
        elif args.cmd == "click":
            obs = container.act().execute(Action.click(args.x, args.y))
            _print(obs.to_dict())
        elif args.cmd == "polite-click":
            obs = container.act().execute(Action.polite_click(args.x, args.y))
            _print(obs.to_dict())
        elif args.cmd == "drag":
            obs = container.act().execute(Action.drag(args.x0, args.y0, args.x1, args.y1))
            _print(obs.to_dict())
        elif args.cmd == "key":
            obs = container.act().execute(Action.key_press(args.key))
            _print(obs.to_dict())
        elif args.cmd == "goto":
            ok = container.navigate().execute(args.label)
            _print({"goto": args.label, "ok": ok})
        elif args.cmd == "ask":
            results = container.ask_knowledge().execute(" ".join(args.query))
            _print(results)
        else:
            p.print_help(); return 2
    finally:
        container.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
