#!/usr/bin/env python3
"""enhance_soul.py - Task CUONG HOA NGU HON (soul) theo chien thuat loc som.

Y tuong (xem research/SOUL_ENHANCE.md):
  Khong the ep roll vao 1 dong. Cach hieu qua nhat la: cuong hoa den moc +3/+6/+9,
  OCR lai dong phu; neu lan roll KHONG vao dong muc tieu -> DUNG, giu lam thuc an.
  Nho vay phan lon soul bi loai som (re) thay vi do tien len +15 het.

Task nay lam phan THAT THI duoc tu dong va do luong duoc:
  1) (tuy chon) cuong hoa soul dang chon len moc tiep theo.
  2) OCR dong phu truoc/sau -> biet lan roll vao dong nao.
  3) Quyet dinh theo chien thuat: tiep / dung / danh dau bo (弃置).
  4) GHI SO LIEU tung lan roll -> logs/enhance_soul_stats.jsonl, de do TI LE THAT
     tren tai khoan (so voi 1/4 o wiki).

An toan: dry=True (mac dinh) chi DOC (doc muc, dong phu, de xuat) KHONG bam gi.
         dry=False moi bam. Nen chay dry truoc de kiem toa do nut.

CLI qua tasks/run.py:
  python tasks/run.py enhance_soul --dry
  python tasks/run.py enhance_soul target=spd times=5 --live
  python tasks/run.py enhance_soul target=crit,spd max_level=9 --live
"""
import json
import os
import re
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "automation"))
sys.path.insert(0, os.path.join(ROOT, "ml"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

LOG = os.path.join(ROOT, "logs", "enhance_soul_stats.jsonl")

# --- Toa do man chi tiet soul / nut cuong hoa (SUY TU res.npk, can verify LIVE) ---
# Nguon UI: res.npk entry 35994.json (panel chi tiet: strengthenBtn '强化' + lockBtn)
#           + 26763.json (panel cuong hoa: upgradeBtn '强化', attrScroll, processLabel).
# => 2 gia tri duoi la GIA THUYET, phai kiem bang --dry khi game chay:
ANCHORS = {
    "strengthen_btn": (1040, 640),   # nut 'Strengthen/强化' o panel chi tiet
    "strengthen_btn2": (1000, 600),  # nut '强化' o panel cuong hoa (fallback)
    "discard_btn": (980, 640),       # nut danh dau bo (弃置)
    "confirm_btn": (660, 410),       # Confirm cua dialog (da verify tu farm_soul)
    "tap_center": (576, 620),
}

# Ten dong phu co the OCR thanh nhieu kieu -> dung tap alias cua ml/soul_lines.py
from soul_lines import parse_lines, read_soul, stat_of  # noqa: E402


# ---------------------------------------------------------------- doc muc soul


def _ocr_words(img, min_conf=30):
    """Lop mong quanh ml/ocr.py ocr_words. Tach ra de TEST OFFLINE de dang
    (test monkeypatch ham nay de tra words gia, khong can game/OCR)."""
    from ocr import ocr_words as _real
    return _real(img, min_conf=min_conf)


_LEVEL_PAT = re.compile(r"\+\s*(\d{1,2})\b")


def read_level(img, words=None):
    """Doc muc cuong hoa hien tai (so '+N') tren man chi tiet soul.

    Du phong: neu khong doc duoc '+N', tra None (task se dua vao OCR lai sau khi bam).
    """
    ws = words if words is not None else _ocr_words(img)
    best = None
    for w in ws:
        m = _LEVEL_PAT.search(str(w[0]))
        if m:
            v = int(m.group(1))
            if 0 <= v <= 15:
                # uu tien so nam nua tren man (header soul) - lay so dau tien hop le
                best = v if best is None else best
    return best


def _stats_diff(before, after):
    """So sanh 2 SoulState -> {key: delta} cho dong DA TANG (>=0.1) va dong MOI."""
    out = {}
    for k, v in after.stats.items():
        b = before.stats.get(k)
        if b is None:
            out[k] = None            # dong MOI xuat hien o moc nay
        elif v - b >= 0.05:
            out[k] = round(v - b, 3)
    return out


def _decide(rolled, target, level, max_level):
    """Chien thuat: (tiep?, ly do).

    rolled : {key: delta} cac dong da tang o moc vua roi.
    target : set key muc tieu (vd {'spd'}).
    """
    if not rolled:
        return None, "khong doc duoc lan roll nao (OCR loi?)"
    if any(k in target for k in rolled):
        if level >= max_level:
            return False, f"trung dich o +{level} = dat dich -> DUNG (giu)"
        return True, f"trung dich {sorted(rolled)} o +{level} -> di tiep +{level + 3}"
    return False, f"truot ({sorted(rolled)}) o +{level} -> DUNG, giu lam thuc an"


# ---------------------------------------------------------------- task chinh
def enhance_soul(agent, target: str = "spd", times: int = 5, max_level: int = 15,
                 dry: bool = True, zone: str = None, stage: str = None):
    """Cuong hoa soul dang chon (hoac tu di toi man Soul), theo chien thuat loc som.

    target   : dong muc tieu, phan cach bang dau phay. vd 'spd' hoac 'crit,spd'.
             Dung ten key chuan: atk, atk_pct, hp, hp_pct, def, def_pct, spd,
             crit, crit_dmg, eff_hit, eff_res.
    times    : so soul se thu trong lan chay nay (moi soul = 1 lan vao chi tiet).
    max_level: moc dung khi da trung dich (mac dinh 15 = full).
    dry      : True = chi doc + de xuat (khong bam).
    """
    tset = {t.strip().lower() for t in str(target).split(",") if t.strip()}
    print(f"[task] enhance_soul target={sorted(tset)} times={times} "
          f"max_level=+{max_level} (dry={dry})")

    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    tries, kept, stopped, rolls_total, hits = 0, 0, 0, 0, 0

    for n in range(times):
        img = agent.shot()
        if img is None:
            print("  ! khong chup duoc anh (game dang tat?) -> dung"); break
        words = _ocr_words(img)
        before = parse_lines(words)
        lv = read_level(img, words)
        print(f"\n  soul #{n+1}: level={lv} dong={before.stats}")
        if not before.stats:
            print("    ! khong doc duoc dong phu nao -> khong phai man chi tiet soul?")
            print("    (mo man chi tiet 1 soul roi chay lai, hoac dung --zone/--stage)")
            break

        if dry:
            print(f"    [DRY] se bam Strengthen @ {ANCHORS['strengthen_btn']} "
                  f"-> doc lai dong phu -> quyet dinh theo target {sorted(tset)}")
            tries += 1
            continue

        # --- 1) cuong hoa len moc ke tiep ---
        lvl_now = lv if lv is not None else 0
        if lvl_now >= max_level:
            print(f"    da +{lvl_now} >= max_level -> bo qua soul nay"); continue
        agent.c.bgclick(*ANCHORS["strengthen_btn"])
        time.sleep(2.5)
        # dialog xac nhan (neu co)
        r2 = agent.read()
        for w in ("Confirm", "OK", "Strengthen"):
            if r2.has(w):
                agent.tap_text(w, wait=1.5)
                break
        time.sleep(2.0)

        # --- 2) doc lai dong phu -> biet roll vao dau ---
        after = parse_lines(_ocr_words(agent.shot()))
        rolled = _stats_diff(before, after)
        lv2 = lvl_now + 3
        rolls_total += 1
        if any(k in tset for k in rolled):
            hits += 1
        cont, why = _decide(rolled, tset, lv2, max_level)
        print(f"    roll @ +{lv2}: {rolled} -> {why}")

        # --- 3) hanh dong theo quyet dinh ---
        if cont is False:
            stopped += 1
            if not any(k in tset for k in rolled):
                # truot: giu lam thuc an / danh dau bo
                print(f"    -> (tuy chon) danh dau bo @ {ANCHORS['discard_btn']} "
                      f"[chua tu bam, bat tay trong ban sau]")
        else:
            kept += 1

        tries += 1
        with open(LOG, "a") as f:
            f.write(json.dumps({
                "run": run_id, "idx": n + 1, "level_before": lvl_now,
                "level_after": lv2, "before": before.stats, "after": after.stats,
                "rolled": rolled, "target": sorted(tset),
                "decision": "keep" if cont else ("stop" if cont is False else "unknown"),
                "hit": any(k in tset for k in rolled),
                "dry": False, "ts": datetime.utcnow().isoformat() + "Z",
            }, ensure_ascii=False) + "\n")

        if cont is False:
            print("    -> quay ra list (back) de chon soul khac")
            agent.back()

    summary = {
        "run": run_id, "task": "enhance_soul", "target": sorted(tset),
        "times": times, "tried": tries, "kept_going": kept, "stopped": stopped,
        "rolls_total": rolls_total, "hits": hits,
        "hit_rate": round(hits / rolls_total, 3) if rolls_total else None,
        "note": "hit_rate so voi 1/4 = 0.25 cua wiki (xem research/SOUL_ENHANCE.md)",
        "dry": dry, "summary": True, "ts": datetime.utcnow().isoformat() + "Z",
    }
    if not dry:
        with open(LOG, "a") as f:
            f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(f"\n  [SUMMARY] tried={tries} hit={hits}/{rolls_total} "
          f"(ti le {summary['hit_rate']}) stop={stopped} keep={kept} log={LOG}")
    return True
