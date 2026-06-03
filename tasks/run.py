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


def farm_realm(agent: Agent, times: int = 30, dry: bool = True):
    """Daily 'farm Realm Raid N lan' tu BAT KY man nao.

    Day la ME CUNG THUC TE: agent co the dang o soul_zones/town/dang danh -> phai TU
    DINH VI (nav.goto re-plan moi hop) -> toi realm_raid -> ACTION LOOP co VERIFY.

    An toan: dry=True chi DOC (where/OCR luot con lai), KHONG bam Challenge. Khi da
    hoc chac vi tri nut + xac nhan, doi dry=False.
    """
    import re
    print(f"[task] farm_realm x{times} (dry={dry})")

    # 1) DINH VI + DIEU HUONG: tu bat ky dau -> realm_raid (Dijkstra re-plan moi hop).
    if not agent.nav.goto("realm_raid"):
        print("  ! khong toi duoc realm_raid"); return False
    node, conf = agent.nav.where()
    print(f"  da toi '{node}' (conf {conf:.2f}).")

    # 2) VERIFY luot con lai (OCR 'X/30') -> khong farm mu, dung khi het.
    img = agent.shot()
    r = agent.read(img)
    remain = None
    for t in r.tappables():
        m = re.match(r"(\d+)\s*/\s*30", str(t[0]).replace(" ", ""))
        if m:
            remain = int(m.group(1)); break
    if remain is not None:
        print(f"  luot con lai: {remain}/30")
        runs = min(times, remain)
    else:
        print("  (khong doc duoc so luot - se dung verify moi vong)")
        runs = times

    # 3) ACTION LOOP co verify (state-machine: Challenge -> battle -> reward -> back).
    done = 0
    for i in range(runs):
        img = agent.shot()
        rr = agent.read(img)
        if not (rr.has("Challenge") or rr.has("Assault")):
            print(f"  vong {i+1}: khong thay nut Challenge -> dung (het luot/sai man).")
            break
        if dry:
            print(f"  vong {i+1}/{runs}: [DRY] se click Challenge -> battle -> reward")
            done += 1
            continue
        # --- thuc thi that (chi khi dry=False) ---
        ok, _ = agent.tap_text("Challenge")
        if not ok:
            print(f"  vong {i+1}: bam Challenge that bai -> dung."); break
        agent.wait_stable(max_wait=40)               # cho battle xong
        for w in ("Reward", "Confirm", "Tap"):       # nhan thuong
            if agent.tap_text(w)[0]:
                break
        agent.wait_stable()
        done += 1
    print(f"  hoan tat {done}/{runs} vong farm.")
    return True


TASKS = {
    "daily_signin": daily_signin,
    "farm_realm": farm_realm,
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
