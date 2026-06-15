#!/usr/bin/env python3
"""tests_arch/test_mcp.py - Test MCP server bang FakeEye (KHONG can game).

Goi truc tiep cac ham tool (khong qua stdio) de verify chung tra dung cau truc.
Bat buoc chay voi ONMYOJI_EYE=fake.

Dung:
    ONMYOJI_EYE=fake .venv/bin/python tests_arch/test_mcp.py
    (script tu set ONMYOJI_EYE=fake neu chua co)
"""
from __future__ import annotations

import os
import sys

# Buoc test offline: bat buoc fake eye truoc khi import server.
os.environ.setdefault("ONMYOJI_EYE", "fake")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from onmyoji.interface import mcp_server as srv  # noqa: E402

_failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {msg}")
    if not cond:
        _failures.append(msg)


def assert_observation(d: object, where: str) -> None:
    """Verify dict co dung shape cua Observation.to_dict()."""
    check(isinstance(d, dict), f"{where}: tra ve dict")
    if not isinstance(d, dict):
        return
    for field in ("ts", "state_id", "loading", "size", "buttons", "alive", "resources"):
        check(field in d, f"{where}: co field '{field}'")
    check(isinstance(d.get("size"), dict) and {"w", "h"} <= set(d["size"]),
          f"{where}: size co w,h")
    check(isinstance(d.get("buttons"), list), f"{where}: buttons la list")
    if d.get("buttons"):
        b = d["buttons"][0]
        check(isinstance(b, dict) and {"x", "y", "w", "h", "score"} <= set(b),
              f"{where}: button co x,y,w,h,score")
    check(isinstance(d.get("resources"), dict), f"{where}: resources la dict")


def main() -> int:
    print("=== test_mcp (ONMYOJI_EYE=%s) ===" % os.environ.get("ONMYOJI_EYE"))

    # Container la singleton (lazy)
    c1 = srv.get_container()
    c2 = srv.get_container()
    check(c1 is c2, "get_container() tra ve cung 1 instance (singleton)")
    check(type(c1.eye).__name__ == "FakeEye", "Eye la FakeEye khi ONMYOJI_EYE=fake")

    # Inject FakeKnowledge de test THUAN (khong load sklearn/vectordb, khong side-effect).
    from onmyoji.adapters.knowledge.fake_knowledge import FakeKnowledge
    c1._knowledge = FakeKnowledge()
    c1._knowledge_built = True

    # Cac tool deu duoc dang ky vao server (qua MCP API async)
    import asyncio
    registered = {t.name for t in asyncio.run(srv.mcp.list_tools())}
    expected = {"observe", "wait_stable", "click", "polite_click",
                "drag", "key", "goto", "ask_kb"}
    check(expected <= registered,
          f"day du tool dang ky: thieu {sorted(expected - registered)}")

    # --- observe ---
    obs = srv.observe()
    assert_observation(obs, "observe()")
    check(obs.get("state_id") == "HOME", "observe(): FakeEye state_id == HOME")

    # --- wait_stable ---
    ws = srv.wait_stable()
    assert_observation(ws, "wait_stable()")

    # --- click ---
    ck = srv.click(100, 100)
    assert_observation(ck, "click(100,100)")

    # --- polite_click ---
    pc = srv.polite_click(120, 130)
    assert_observation(pc, "polite_click(120,130)")

    # --- drag ---
    dg = srv.drag(10, 20, 30, 40)
    assert_observation(dg, "drag(10,20,30,40)")

    # --- key ---
    ky = srv.key("esc")
    assert_observation(ky, "key('esc')")

    # Verify cac action thuc su duoc ghi vao FakeEye theo dung kind
    log = c1.eye.actions_log
    kinds = [a.kind.value for a in log]
    check(kinds == ["click", "polite_click", "drag", "key"],
          f"actions_log dung thu tu/kind: {kinds}")
    # Verify tham so truyen dung
    click_act = log[0]
    check(click_act.x == 100 and click_act.y == 100, "click action giu dung x,y")
    drag_act = log[2]
    check(drag_act.x == 10 and drag_act.y == 20 and drag_act.x1 == 30 and drag_act.y1 == 40,
          "drag action giu dung x0,y0,x1,y1")
    check(log[3].key == "esc", "key action giu dung key")

    # --- goto: fake eye khong co WorldModel -> phai raise RuntimeError ---
    try:
        srv.goto("HOME")
        check(False, "goto() voi fake eye phai raise RuntimeError")
    except RuntimeError:
        check(True, "goto() raise RuntimeError khi WorldModel khong kha dung (fake)")

    # --- ask_kb: Knowledge doc lap voi eye kind (khong phu thuoc fake eye).
    # Neu KB load duoc -> tra list[dict]; neu khong -> raise RuntimeError.
    if c1.knowledge is not None:
        res = srv.ask_kb("farm soul", k=3)
        check(isinstance(res, list), "ask_kb() tra ve list khi KB kha dung")
        check(all(isinstance(x, dict) for x in res),
              "ask_kb() moi phan tu la dict")
        check(len(res) <= 3, "ask_kb() ton trong tham so k")
    else:
        try:
            srv.ask_kb("farm soul", k=3)
            check(False, "ask_kb() khi KB None phai raise RuntimeError")
        except RuntimeError:
            check(True, "ask_kb() raise RuntimeError khi KB khong kha dung")

    print()
    if _failures:
        print(f"RESULT: FAIL ({len(_failures)} loi)")
        for m in _failures:
            print("  - " + m)
        return 1
    print("RESULT: PASS (tat ca check deu pass)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
