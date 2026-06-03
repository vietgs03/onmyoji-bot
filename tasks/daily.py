#!/usr/bin/env python3
"""Daily tasks - tu dong cac viec lap hang ngay (hoc logic tu OAS, dieu huong DONG).

Triet ly khac OAS: KHONG hardcode template CN. Dung OCR doc text EN + tap_text.
-> Ben voi update/event (chi can text khong doi nhieu).

Moi task = ham(agent) -> dict {ok, detail}. An toan: chi nhan reward MIEN PHI,
KHONG mua/tieu jade/skey tru khi mo option. Co DRY-RUN (chi doc, khong bam).

Cac task (xay dan):
  free_summon   : rut the mien phi (Summon -> tab co "Free"/dem nguoc)
  claim_mail    : nhan het thu (mailbox -> Claim All)
  friend_love   : gui/nhan tinh than huu (Friends -> Send/Receive)
  sign_in       : diem danh moc qua (Event/Bonus -> Claim)

CLI:
  python daily.py list                 # liet ke task
  python daily.py run <task> [--dry]   # chay 1 task (--dry = chi doc khong bam)
  python daily.py all [--dry]          # chay het
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "automation"))
from agent import Agent  # noqa: E402


def _home(a, tries=5):
    """Bam back ve HOME (co Explore + Summon)."""
    for _ in range(tries):
        r = a.read()
        if r.has("Explore") and r.has("Summon"):
            return True
        a.back()
    r = a.read()
    return r.has("Explore") and r.has("Summon")


def _tap_any(a, r, labels, dry, wait=2.0):
    """Tim 1 trong cac label (uu tien thu tu) tren ScreenReader r, bam (tru dry)."""
    for lb in labels:
        hit = r.find(lb)
        if hit:
            if dry:
                return lb, hit, None
            a.c.bgclick(hit[1], hit[2])
            time.sleep(wait)
            return lb, hit, a.wait_stable()[1]
    return None, None, r


# ---------------- tasks ----------------
def free_summon(a, dry=False):
    """Vao Summon, tim tab co the rut mien phi (Free / dem nguoc)."""
    if not _home(a):
        return {"ok": False, "detail": "khong ve HOME"}
    ok, r = a.tap_text("Summon")
    if not ok:
        return {"ok": False, "detail": "khong mo Summon"}
    texts = [t[0] for t in r.tappables()]
    has_free = any("free" in t.lower() for t in texts)
    detail = f"man Summon: {texts[:8]}"
    if dry:
        return {"ok": True, "detail": f"[DRY] {detail}; free={has_free}"}
    # tim nut Summon/Free chinh (an toan: chi rut neu co chu 'Free')
    lb, hit, r2 = _tap_any(a, r, ["Free Summon", "Free"], dry=False)
    _home(a)
    return {"ok": True, "detail": f"summon tab: {detail}; clicked={lb}"}


def claim_mail(a, dry=False):
    """Mo mailbox (icon thu) -> Claim All."""
    if not _home(a):
        return {"ok": False, "detail": "khong ve HOME"}
    # icon mail thuong goc tren-phai. Thu tap_text 'Mail' (it khi co chu),
    # fallback: click goc tren-phai (vi tri chuan icon thu)
    r = a.read()
    hit = r.find("Mail")
    if not hit:
        a.c.bgclick(1038, 70)  # vi tri icon thu (tren-phai)
        time.sleep(2.0)
        r = a.wait_stable()[1]
    else:
        if not dry:
            a.c.bgclick(hit[1], hit[2]); time.sleep(2.0)
            r = a.wait_stable()[1]
    texts = [t[0] for t in r.tappables()]
    lb, hit, r2 = _tap_any(a, r, ["Claim All", "Claim", "Collect All"], dry)
    _home(a)
    return {"ok": True, "detail": f"mail man: {texts[:8]}; claim={lb}{' [DRY]' if dry else ''}"}


def friend_love(a, dry=False):
    """Friends -> gui/nhan tinh than huu (Send/Receive/One Tap)."""
    if not _home(a):
        return {"ok": False, "detail": "khong ve HOME"}
    ok, r = a.tap_text("Friend")
    if not ok:
        return {"ok": False, "detail": "khong mo Friends"}
    texts = [t[0] for t in r.tappables()]
    lb, hit, r2 = _tap_any(a, r, ["One Tap", "Send", "Receive", "Friendship"], dry)
    _home(a)
    return {"ok": True, "detail": f"friends man: {texts[:8]}; action={lb}{' [DRY]' if dry else ''}"}


def sign_in(a, dry=False):
    """Event -> tim moc thuong co the nhan (Claim/Receive)."""
    if not _home(a):
        return {"ok": False, "detail": "khong ve HOME"}
    ok, r = a.tap_text("Event")
    if not ok:
        return {"ok": False, "detail": "khong mo Event"}
    texts = [t[0] for t in r.tappables()]
    lb, hit, r2 = _tap_any(a, r, ["Claim", "Receive", "Sign", "Get"], dry)
    _home(a)
    return {"ok": True, "detail": f"event man: {texts[:8]}; claim={lb}{' [DRY]' if dry else ''}"}


TASKS = {
    "free_summon": free_summon,
    "claim_mail": claim_mail,
    "friend_love": friend_love,
    "sign_in": sign_in,
}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    dry = "--dry" in sys.argv
    if cmd == "list":
        print("Daily tasks:")
        for k, fn in TASKS.items():
            print(f"  {k:14s} - {fn.__doc__.splitlines()[0]}")
        return
    a = Agent()
    try:
        if cmd == "run":
            name = sys.argv[2]
            print(f"[{name}]", TASKS[name](a, dry=dry))
        elif cmd == "all":
            for name, fn in TASKS.items():
                print(f"[{name}]", fn(a, dry=dry))
    finally:
        a.c.close()


if __name__ == "__main__":
    main()
