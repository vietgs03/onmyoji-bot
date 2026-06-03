#!/usr/bin/env python3
"""
tasks - Cac tac vu automation. Moi task = chuoi (navigate + thao tac + verify).

Khung task mau. Khi game chay, agent.goto() dua bot toi dung man, roi task thuc thi.
Moi task NEN verify ket qua (vd doc lai man/OCR) thay vi click mu.

Cac task du kien (xay dan khi hoc them thao tac moi mode):
  - daily_signin : diem danh Return Benefits / Shrine Pass quests
  - claim_mail   : nhan thu (mailbox)
  - farm_explore : farm Exploration chuong X auto-battle N lan
  - free_summon  : rut the mien phi moi ngay

Hien tai: khung + daily_signin demo (an toan, chi navigate + chup, chua bam mua).
"""
import os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "automation"))
from agent import Agent


def daily_signin(agent: Agent):
    """Demo AN TOAN: ve HOME -> mo Event -> chup man (de nguoi/bot xem co nut Claim).
    Chua tu bam Claim (can hoc them vi tri nut qua explorer/OCR truoc).
    Dieu huong bang agent.nav (ScreenGraph clean: goto/where/escape)."""
    print("[task] daily_signin")
    if not agent.nav.goto("HOME"):
        print("  ! khong ve duoc HOME"); return False
    if not agent.nav.goto("event"):
        print("  ! khong mo duoc Event"); return False
    node, conf = agent.nav.where()
    print(f"  da o '{node}' (conf {conf:.2f}). Dung OCR tim nut Claim...")
    from ocr import find_text
    img = agent.shot()
    for word in ("Claim", "Sign", "Receive", "Get"):
        pt = find_text(img, word)
        if pt:
            print(f"  thay nut '{word}' @ {pt} (chua tu bam - can xac nhan)")
            return True
    print("  khong thay nut claim ro rang")
    return True


TASKS = {
    "daily_signin": daily_signin,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in TASKS:
        print("tasks co san:", ", ".join(TASKS))
        print("usage: python tasks/run.py <task>")
        return
    agent = Agent()
    TASKS[sys.argv[1]](agent)


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(ROOT, "ml"))
    main()
