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


# ---- Soul (Ngu Hon / 御魂) farming -----------------------------------------

SOUL_ZONES = ("Orochi", "Sougenbi", "Himiko", "Fallen Sun", "Sea of Eternity")
# Layout man Soul/<zone>: cot trai = danh sach stage (scroll duoc),
# nut Challenge goc phai duoi, vung battle/reward sau do.
_STAGE_COL = (95, 120, 185, 560)     # ROI cot trai chua ten stage (x,y,w,h)
_CHALLENGE_XY = (1063, 580)          # nut Challenge
_DRAG = (145, 500, 145, 180, 16)     # keo scroll list xuong (khong chiem chuot)
# Duong di da-verify-live HOME -> Soul (graph nav chua map sau tier-2 nen di truc tiep)
_HOME_EXPLORE_XY = (608, 192)        # nut Explore tren HOME
_EXPLORE_SOUL_XY = (175, 620)        # icon 'Soul' footer trong man Explore


def _ensure_soul_screen(agent, max_try=4):
    """Tu BAT KY dau -> man Soul (4 zone).

    DUNG StateSolver (giai man hinh huong-dich, hoc theo chu ky trang thai):
      1) solve(['Explore','Summon']) -> ve HOME du dang ket o idle/courtyard/popup
         (solver tu hoc back/wake/pan thay vi hardcode). Day la "tu nho".
      2) tu HOME: tap 'Explore' (OCR tim, khong hardcode toa do) -> man Soul.
    Verify bang OCR ('Soul' header + 'Challenge'). Fallback nav.goto neu can."""
    from ocr import ocr_words
    from state_solver import StateSolver

    def on_soul(img):
        # Dau hieu CHAC CHAN cua man Soul (tranh false-positive o HOME):
        #  - header 'Soul' goc trai tren (roi hep y<90, x<320)
        #  - nut 'Challenge' goc phai duoi
        head = " ".join(str(t).lower() for t, *_ in ocr_words(img, roi=(0, 40, 320, 90), min_conf=40))
        body = " ".join(str(t).lower() for t, *_ in ocr_words(img, roi=(0, 40, 1152, 640), min_conf=35))
        return ("soul" in head) and ("challenge" in body)

    solver = getattr(agent, "_solver", None) or StateSolver(agent)
    agent._solver = solver

    for _ in range(max_try):
        img = agent.shot()
        if on_soul(img):
            return True
        # (1) GIAI ve HOME (solver tu thoat idle/courtyard/popup, hoc theo trang thai).
        if not solver.solve(["Explore", "Summon"], need_all=True,
                            max_steps=12, verbose=False):
            # solver bo tay -> thu goto HOME (graph) lam moc cuoi.
            agent.nav.goto("HOME")
        time.sleep(0.8)
        # (2) tu HOME: tap dung chu 'Explore' (khong hardcode toa do) -> Soul.
        ok, _ = agent.tap_text("Explore", wait=3.5)
        if not ok:
            agent.click(*_HOME_EXPLORE_XY)        # fallback toa do cu
            time.sleep(3.5)
        if on_soul(agent.shot()):
            return True
        # neu Explore mo ra danh sach (chua vao Soul) -> tap icon Soul footer.
        agent.tap_text("Soul", wait=3.5)
        if on_soul(agent.shot()):
            return True
    return False


def _find_stage(agent, name, max_scroll=8):
    """Scroll cot trai tim stage theo TEN (OCR), tra ve (x,y) tam de click.
    name khop khong phan biet hoa/thuong, chap nhan substring (vd 'Moan')."""
    import numpy as np
    from ocr import ocr_words
    key = name.lower().replace(" ", "")
    prev = None
    for _ in range(max_scroll):
        img = agent.shot()
        for t, (x, y, w, h), cf in ocr_words(img, roi=_STAGE_COL, min_conf=40):
            tok = str(t).lower().replace(" ", "")
            # OCR hay dinh rac phia truoc (vd 'TIfMoan') -> dung substring 'in'
            if key in tok:
                return (x + w // 2, y + h // 2)
        # chua thay -> scroll list xuong (khong chiem chuot)
        agent.drag(*_DRAG); time.sleep(1.1)
        cur = agent.shot()
        if prev is not None and np.abs(prev.astype(int) - cur.astype(int)).mean() < 1.5:
            break        # khong scroll them duoc -> da toi day list
        prev = cur
    return None


def farm_soul(agent: Agent, stage: str = "Moan", zone: str = "Orochi",
              times: int = 10, dry: bool = True):
    """Daily 'farm Ngu Hon (Soul) stage X, N lan' tu BAT KY man nao.

    Quy trinh (state-machine, generic theo TEN stage - khong hardcode toa do stage):
      1) nav.goto('soul_zones')  -> man Soul (4 zone)
      2) click zone (Orochi...)  -> man stage cua zone
      3) _find_stage(stage)      -> scroll list tim + click stage (vd Moan)
      4) ACTION LOOP: Challenge -> battle (wait_stable) -> reward -> lap, co VERIFY

    An toan: dry=True chi DINH VI + DOC (chon stage, in se-bam), KHONG bam Challenge.
    Khi xac nhan dung stage roi chay dry=False de danh that.
    """
    print(f"[task] farm_soul zone={zone} stage={stage} x{times} (dry={dry})")

    # 1) -> man Soul (di truc tiep HOME->Explore->Soul, verify bang OCR)
    if not _ensure_soul_screen(agent):
        print("  ! khong toi duoc man Soul"); return False
    print("  da o man Soul (thay Orochi/Eternity).")

    # 2) chon zone: man Soul co 4 panel doc xep ngang. Click vao panel zone.
    #    OCR ten zone bi xoay doc -> dung VI TRI panel (da verify live).
    _ZONE_X = {"orochi": 200, "sougenbi": 460, "fallen sun": 740,
               "fallensun": 740, "sea of eternity": 1040, "eternity": 1040,
               "himiko": 740}
    zx = _ZONE_X.get(zone.lower().replace("  ", " "), 200)
    agent.click(zx, 250); time.sleep(2.5)
    print(f"  da chon zone {zone} @ x={zx}")
    # neu chua vao (van o man chon zone) -> thu lai 1 lan
    from ocr import ocr_words
    toks = " ".join(str(t).lower() for t, *_ in ocr_words(agent.shot(), roi=(0, 40, 1152, 200), min_conf=40))
    if "daily souls" in toks:        # van con o man liet ke 4 zone
        agent.click(zx, 350); time.sleep(2.5)

    # 3) tim + chon stage (scroll list)
    spt = _find_stage(agent, stage)
    if not spt:
        print(f"  ! khong tim thay stage '{stage}'"); return False
    agent.click(*spt); time.sleep(1.5)
    print(f"  da chon stage {stage} @ {spt}")

    # 4) ACTION LOOP co verify + GHI SO LIEU
    import json as _json, re as _re, time as _time, os as _os
    from datetime import datetime as _dt

    def _read_counter(img):
        """Doc 'Rewards Preview X/500' -> X (so tran da danh trong cycle hien tai).
        OCR full anh roi loc theo regex (crop ROI nho lam OCR kem)."""
        for t, *_ in ocr_words(img, min_conf=30):
            m = _re.search(r"(\d+)\s*/\s*500\b", str(t))
            if m:
                return int(m.group(1))
        return None

    def _read_stamina(img):
        """Doc shushi (stamina) top-bar -> int (vd 13400). OCR full anh, loc theo
        bbox o goc tren phai (x>820, y<90) dang 'NN.NK' hoac so thuan."""
        for t, (x, y, w, h), cf in ocr_words(img, min_conf=30):
            if not (x > 820 and y < 90):
                continue
            s = str(t).replace(",", "").upper()
            m = _re.match(r"(\d+(?:\.\d+)?)K?$", s)
            if m:
                v = float(m.group(1))
                return int(v * 1000) if "K" in s else int(v)
        return None

    LOG = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                        "logs", "farm_soul_stats.jsonl")
    _os.makedirs(_os.path.dirname(LOG), exist_ok=True)
    run_id = _dt.utcnow().strftime("%Y%m%dT%H%M%SZ")
    img0 = agent.shot()
    c_start = _read_counter(img0)
    s_start = _read_stamina(img0)
    print(f"  [stats] run={run_id} counter_start={c_start} stamina_start={s_start}")

    done = 0
    wins = 0
    durations = []
    for i in range(times):
        # Cho man stage on dinh + tim Challenge (retry: vua ra khoi battle co the
        # con dang load lai man stage -> dung break ngay).
        on_stage = False
        for _ in range(6):
            img = agent.shot()
            rr = agent.read(img)
            if rr.has("Challenge"):
                on_stage = True
                break
            time.sleep(2.0)
        if not on_stage:
            print(f"  vong {i+1}: khong thay Challenge sau 6 thu -> dung (het luot/sai man)."); break
        if dry:
            print(f"  vong {i+1}/{times}: [DRY] se Challenge @ {_CHALLENGE_XY} -> battle -> reward")
            done += 1; continue
        round_t0 = _time.time()
        c_before = _read_counter(img)                 # counter TRUOC khi danh
        agent.click(*_CHALLENGE_XY)
        time.sleep(3.0)
        # Cho battle xong. THANG = counter TANG (dang tin hon 'thay Challenge', vi
        # cac dialog/popup co the de 'Challenge' hien ma battle CHUA chay).
        won = False
        t0 = time.time()
        saw_battle = False                            # da roi khoi man stage chua
        while time.time() - t0 < 150:                 # battle + reward/popup ngau nhien
            img = agent.shot()
            r2 = agent.read(img)
            c_now = _read_counter(img)
            has_ch = r2.has("Challenge")
            # HE THONG OVERLAY (tu nho): detect_overlay doc OVERLAYS (bonus_enable,
            # parade_privilege, ...) -> resolve_overlay tu xu ly (click@toa-do).
            # CHI lay dialog can chan (bonus/parade); KHONG dung 'loading'/'animation'
            # vi man reward cung co 'Tap to'/'Skip' -> de he duoi tu xu (tap continue).
            ov, ovc = agent.nav.detect_overlay(reader=r2)
            if ov not in ("bonus_enable", "parade_privilege"):
                ov = None
            is_dialog = ov is not None
            # ve man stage VA counter da tang -> thang that (dang tin nhat)
            if has_ch and c_before is not None and c_now is not None and c_now > c_before:
                won = True
                break
            # ve man stage, da tung vao battle that, counter OCR loi -> coi nhu xong
            if has_ch and saw_battle and not is_dialog:
                won = True
                break
            # 'roi stage' chi tinh khi KHONG phai dialog (dialog cung an Challenge)
            if not has_ch and not is_dialog:
                saw_battle = True
            # --- Overlay da biet (bonus/parade/...) -> resolve qua he thong ---
            if ov is not None:
                agent.nav.resolve_overlay(ov)
                time.sleep(0.8)
                # neu bonus dialog -> battle chua chay (van o stage) -> bam lai Challenge
                if ov == "bonus_enable" and agent.read().has("Challenge"):
                    agent.c.bgclick(*_CHALLENGE_XY)
                    time.sleep(3.0)
                continue
            # --- Nut ket qua / man reward dac biet ---
            tapped = False
            for w in ("Reward", "Confirm", "Continue", "OK"):
                if r2.has(w) and agent.tap_text(w, wait=1.2)[0]:
                    tapped = True
                    break
            if not tapped:
                agent.c.bgclick(576, 620)             # 'Tap to continue'
                time.sleep(0.8)
                agent.c.bgclick(576, 340)             # giua man
            time.sleep(1.8)
        dur = round(_time.time() - round_t0, 1)
        done += 1
        wins += 1 if won else 0
        durations.append(dur)
        # ghi so lieu tung vong
        with open(LOG, "a") as f:
            f.write(_json.dumps({
                "run": run_id, "round": i + 1, "won": won, "dur_s": dur,
                "counter": _read_counter(agent.shot()),
                "ts": _dt.utcnow().isoformat() + "Z",
            }) + "\n")
        print(f"  vong {i+1}/{times}: {'xong' if won else 'het gio (?)'} ({dur}s)")

    # tong ket run
    img_end = agent.shot()
    c_end = _read_counter(img_end)
    s_end = _read_stamina(img_end)
    avg = round(sum(durations) / len(durations), 1) if durations else 0
    summary = {
        "run": run_id, "stage": stage, "zone": zone, "times": times,
        "done": done, "wins": wins, "win_rate": round(wins / done, 3) if done else 0,
        "avg_dur_s": avg, "total_dur_s": round(sum(durations), 1),
        "counter_start": c_start, "counter_end": c_end,
        "stamina_start": s_start, "stamina_end": s_end,
        "stamina_used": (s_start - s_end) if (s_start is not None and s_end is not None) else None,
        "summary": True, "ts": _dt.utcnow().isoformat() + "Z",
    }
    with open(LOG, "a") as f:
        f.write(_json.dumps(summary) + "\n")
    print(f"  [SUMMARY] done={done}/{times} wins={wins} win_rate={summary['win_rate']} "
          f"avg={avg}s counter {c_start}->{c_end} stamina {s_start}->{s_end} "
          f"(used={summary['stamina_used']})")
    print(f"  hoan tat {done}/{times} vong farm Soul. Log: {LOG}")
    return True


# ---- claim_home: nhan het thuong tren HOME (mail, daily check-in, task xong) ----
# Tu duy: man HOME = ma tran trang thai; DICH = "het badge do co the claim".
# Khong hardcode toa do tung muc -> detect badge do (perception.detect_red_badges)
# roi GIAI tung cai: tap badge -> popup claim? -> tap nut Claim/Receive/OK -> back.
# HOC: nho (theo chu ky trang thai) badge nao cho claim that, badge nao vo ich.
_CLAIM_WORDS = ("Claim", "Receive", "Confirm", "Collect", "Get", "OK", "Sign", "Tap to")


def claim_home(agent: Agent, rounds: int = 3, dry: bool = True):
    """Quet HOME tim badge do va claim het (mail / diem danh / task xong).

    rounds: so vong quet lai (badge moi co the hien sau khi claim cai khac).
    dry=True: chi BAO CAO badge + thu mo, KHONG bam nut Claim (an toan xem truoc).
    dry=False (--live): bam Claim that.
    """
    import time as _t
    from datetime import datetime as _dt
    import json as _json
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from state_solver import StateSolver
    from perception import detect_red_badges
    from screen_reader import ocr_words

    LOG = os.path.join(ROOT, "logs", "claim_home.jsonl")
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    run_id = _dt.utcnow().strftime("%Y%m%dT%H%M%S")

    solver = getattr(agent, "_solver", None) or StateSolver(agent)
    agent._solver = solver

    def at_home():
        ws = [str(t).lower() for t, *_ in ocr_words(agent.shot(), min_conf=40)]
        return any("explore" in w for w in ws) and any("summon" in w for w in ws)

    def back_home():
        if not at_home():
            solver.solve(["Explore", "Summon"], need_all=True, max_steps=10, verbose=False)

    print(f"=== claim_home (dry={dry}) - run {run_id} ===")
    back_home()
    claimed = 0
    seen = set()
    for rnd in range(rounds):
        img = agent.shot()
        badges = detect_red_badges(img)
        # bo badge trung lap gan nhau (gom theo o luoi 30px)
        uniq = []
        for cx, cy, ar in badges:
            key = (cx // 30, cy // 30)
            if key not in seen:
                seen.add(key)
                uniq.append((cx, cy, ar))
        print(f"  vong {rnd+1}: {len(badges)} badge ({len(uniq)} moi)")
        for cx, cy, ar in uniq:
            # badge thuong o GOC TREN icon -> diem tap = hoi xuong duoi tam icon
            tx, ty = cx, min(cy + 18, 660)
            if dry:
                print(f"    [DRY] badge @ ({cx},{cy}) area={ar} -> se tap ({tx},{ty})")
                continue
            agent.click(tx, ty, wait=2.0)
            time.sleep(1.0)
            # sau khi tap: tim nut claim trong popup
            r = agent.read()
            got = False
            for w in _CLAIM_WORDS:
                if r.has(w):
                    ok, _ = agent.tap_text(w, wait=1.5)
                    if ok:
                        got = True
                        claimed += 1
                        print(f"    + claim '{w}' @ badge ({cx},{cy})")
                        break
            # tap-continue cho man qua (nhan vat dac/reward)
            if got:
                agent.c.bgclick(576, 620); time.sleep(0.6)
            # ve HOME truoc khi xu badge tiep (popup co the day man khac)
            back_home()
            # ghi log
            with open(LOG, "a") as f:
                f.write(_json.dumps({
                    "run": run_id, "round": rnd + 1, "badge": [cx, cy],
                    "area": ar, "claimed": got,
                    "ts": _dt.utcnow().isoformat() + "Z"}) + "\n")
        back_home()
    print(f"  hoan tat: claim {claimed} muc. Log: {LOG}")
    return True


# ---- claim_dolls: nhan qua tu cac DOLL CAM QUA trong san HOME (courtyard) ----
# Tu duy (theo user): tren HOME co cac con DOLL than trang dung trong san, moi con
# CAM 1 vat pham (hop go 'Lot' = diem danh, the do = task/clear daily). Doll DOI CHO
# moi ngay -> KHONG hardcode toa do. Detect doll bang dac trung anh
# (perception.detect_courtyard_dolls) roi CLICK tung con -> doc man hien ra:
#  - "Claim Reward"/"Claim Gifts"/"Daily Lot"... -> nhan thuong, dong popup, back.
#  - khong doi gi (nhan vat nguoi choi) -> bo qua. Bot TU HOC doll nao co qua.
_DOLL_CLAIM = ("Claim", "Receive", "Collect", "Get", "Daily", "Lot", "Sign", "Tap to")


def claim_dolls(agent: Agent, dry: bool = True):
    """Quet san HOME tim doll cam qua, click tung con, nhan thuong neu co.

    dry=True: chi BAO CAO doll phat hien + man hien ra, KHONG bam nut nhan.
    dry=False (--live): bam nut Claim/Daily that su.
    """
    import time as _t
    from datetime import datetime as _dt
    import json as _json
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from state_solver import StateSolver
    from perception import detect_courtyard_dolls
    from screen_reader import ocr_words

    LOG = os.path.join(ROOT, "logs", "claim_dolls.jsonl")
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    run_id = _dt.utcnow().strftime("%Y%m%dT%H%M%S")

    solver = getattr(agent, "_solver", None) or StateSolver(agent)
    agent._solver = solver

    def words(img=None):
        return [str(t) for t, *_ in ocr_words(img if img is not None else agent.shot(),
                                              min_conf=40)]

    def at_home():
        ws = [w.lower() for w in words()]
        return any("explore" in w for w in ws) and any("summon" in w for w in ws)

    def claim_popup():
        """Neu dang co popup nhan thuong (Claim/Claim Gifts/Receive) -> bam nhan.
        Tra True neu da bam. Dung politeclick (tin cay hon fgclick tren modal nhan
        thuong nhu Exclusive Gifts)."""
        r = agent.read()
        for w in ("Claim Gifts", "Claim All", "Claim", "Receive", "Collect"):
            if r.has(w):
                hit = r.find(w.split()[0])
                if hit:
                    agent.c.politeclick(hit[1], hit[2])
                    _t.sleep(2.0)
                    agent.c._cmd("sendclick 576 620")  # tap-to-continue neu co
                    _t.sleep(1.0)
                    return True
        return False

    def back_home():
        for _ in range(5):
            if at_home():
                return True
            if claim_popup():        # popup nhan thuong -> nhan thay vi back
                continue
            agent.back(wait=1.2)
        return solver.solve(["Explore", "Summon"], need_all=True,
                            max_steps=10, verbose=False)

    print(f"=== claim_dolls (dry={dry}) - run {run_id} ===")
    back_home()
    img = agent.shot()
    dolls = detect_courtyard_dolls(img)
    print(f"  phat hien {len(dolls)} doll cam qua")
    claimed = 0
    for cx, cy, ar, ic in dolls:
        before = set(words())
        if dry:
            print(f"    [DRY] doll @ ({cx},{cy}) item_px={ic}")
            continue
        agent.c._cmd(f"sendclick {cx} {cy}")
        _t.sleep(2.2)
        after = words()
        new = set(after) - before
        opened = any(any(k.lower() in w.lower() for k in _DOLL_CLAIM) for w in after)
        got = False
        if opened:
            # man qua mo ra -> nhan thuong (Claim/Claim Gifts/Receive...) bang fgclick.
            # co the can nhan 2 lop (vd letter 'Claim Gifts' -> bang 'Claim').
            for _try in range(3):
                if claim_popup():
                    got = True
                else:
                    break
            # man "Daily Lot": tap giua de rut omikuji roi tap-to-continue
            if any("lot" in w.lower() or "tap to" in w.lower() or "daily" in w.lower()
                   for w in words()):
                agent.c._cmd("sendclick 576 300"); _t.sleep(1.5)
                agent.c._cmd("sendclick 576 620"); _t.sleep(1.2)
                got = True
            if got:
                claimed += 1
                print(f"    + doll@({cx},{cy}) -> NHAN: {[w for w in new][:4]}")
            else:
                print(f"    . doll@({cx},{cy}) mo man nhung chua ro nut: {list(new)[:4]}")
        else:
            print(f"    - doll@({cx},{cy}) khong doi (bo qua)")
        with open(LOG, "a") as f:
            f.write(_json.dumps({
                "run": run_id, "doll": [cx, cy], "item_px": ic,
                "opened": opened, "claimed": got,
                "new_words": list(new)[:8],
                "ts": _dt.utcnow().isoformat() + "Z"}) + "\n")
        back_home()
    print(f"  hoan tat: nhan {claimed} doll. Log: {LOG}")
    return True


def daily(agent: Agent, dry: bool = True):
    """DAILY ROUTINE - chay TAT CA viec hang ngay theo bo nho knowledge/daily_tasks.json.

    Doc routine tu file (de KHONG QUEN) roi chay tung task theo thu tu. Moi muc routine
    map toi 1 ham trong TASKS. File la NGUON SU THAT - them task moi vao file la xong.
    """
    import json as _json
    kb = os.path.join(ROOT, "knowledge", "daily_tasks.json")
    routine = []
    if os.path.exists(kb):
        try:
            routine = _json.load(open(kb, encoding="utf-8")).get("routine", [])
        except Exception as e:
            print(f"  [warn] khong doc duoc {kb}: {e}")
    if not routine:
        # fallback: thu tu mac dinh neu file thieu
        routine = [{"id": "claim_dolls"}, {"id": "claim_home"}]
    print(f"=== DAILY (dry={dry}) - {len(routine)} task tu bo nho ===")
    done = []
    ran_fns = set()
    for item in routine:
        tid = item.get("id")
        # map id routine -> ham task (claim_mail/claim_home_badges deu dung claim_home)
        fn = TASKS.get(tid) or TASKS.get({"claim_mail": "claim_home",
                                          "claim_home_badges": "claim_home"}.get(tid, ""))
        if not fn:
            print(f"  - bo qua '{tid}' (chua co ham task)")
            continue
        if fn in ran_fns:               # tranh chay trung ham (mail+badges chung fn)
            print(f"  - '{tid}' dung chung ham da chay -> bo qua")
            continue
        ran_fns.add(fn)
        print(f"  >>> chay '{tid}': {item.get('name', tid)}")
        try:
            fn(agent, dry=dry)
            done.append(tid)
        except Exception as e:
            print(f"  [err] '{tid}' loi: {e}")
    print(f"=== DAILY xong: {done} ===")
    return True


TASKS = {
    "daily": daily,
    "daily_signin": daily_signin,
    "farm_realm": farm_realm,
    "farm_soul": farm_soul,
    "claim_home": claim_home,
    "claim_dolls": claim_dolls,
}


def _parse_kwargs(args):
    """Doc 'key=value' va co --live (=> dry=False) tu argv con lai.
    Tu dong ep kieu int/float/bool de khop signature task."""
    kw = {}
    for a in args:
        if a == "--live":
            kw["dry"] = False
            continue
        if a in ("--dry", "--dry-run"):
            kw["dry"] = True
            continue
        if "=" not in a:
            continue
        k, v = a.split("=", 1)
        vl = v.lower()
        if vl in ("true", "false"):
            kw[k] = (vl == "true")
        else:
            try:
                kw[k] = int(v)
            except ValueError:
                try:
                    kw[k] = float(v)
                except ValueError:
                    kw[k] = v
    return kw


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in TASKS:
        print("tasks co san:", ", ".join(TASKS))
        print("usage: python tasks/run.py <task> [key=value ...] [--live]")
        print("  vd: python tasks/run.py farm_soul zone=Orochi stage=Moan times=10")
        print("      python tasks/run.py farm_soul zone=Orochi stage=Moan --live")
        return
    kw = _parse_kwargs(sys.argv[2:])
    agent = Agent()
    TASKS[sys.argv[1]](agent, **kw)


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(ROOT, "ml"))
    main()
