#!/usr/bin/env python3
"""Loop test cac chuc nang chinh tu HOME - kiem tra dieu huong DONG (OCR).

Voi moi muc tieu: tu HOME -> tap_text(muc tieu) -> doc man moi -> back ve HOME.
In ket qua de phat hien cho dieu chinh (toa do back, nguong loading, fuzzy match).
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "automation"))
from agent import Agent  # noqa: E402

# cac muc tieu o HOME (text hien tren man) + expect thay gi khi vao
TARGETS = [
    ("Town",    ["Encounter", "Arena", "Demon"]),
    ("Explore", ["Chapter", "Soul", "Realm", "Floor", "Yokai"]),
    ("Summon",  ["Mystery", "Amulet", "Summon", "Draw"]),
    ("Event",   ["Event", "Reward", "Ongoing", "Limited"]),
]


def goto_home(a, tries=4):
    """Bam back nhieu lan ve HOME (co Explore + Summon)."""
    r = a.read()
    if r.has("Explore") and r.has("Summon"):
        return True
    r = a.back(home=True)
    return r.has("Explore") and r.has("Summon")


def main():
    a = Agent()
    print("=== dam bao dang o HOME ===")
    if not goto_home(a):
        print("  KHONG ve duoc HOME, dung lai.")
        return
    print("  OK o HOME")

    for target, expect in TARGETS:
        print(f"\n=== {target} ===")
        ok, r = a.tap_text(target)
        if not ok:
            print(f"  [FAIL] khong thay '{target}' tren HOME")
            goto_home(a)
            continue
        found = [e for e in expect if r.has(e)]
        taps = [t[0] for t in r.tappables()][:8]
        print(f"  vao OK. expect khop: {found or 'KHONG'}")
        print(f"  doc duoc: {taps}")
        # back ve HOME
        goto_home(a)
        ok_home = r.has("Explore")
        print(f"  back ve HOME: {'OK' if goto_home(a) else 'CHUA'}")

    a.c.close()
    print("\n=== xong loop test ===")


if __name__ == "__main__":
    main()
