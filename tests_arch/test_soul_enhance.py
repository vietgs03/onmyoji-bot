"""Test OFFLINE cho task cuong hoa soul - khong can game, khong can OCR.

Chay: .venv/bin/python tests_arch/test_soul_enhance.py
  hoac: .venv/bin/python -m pytest tests_arch/test_soul_enhance.py -v

Kiem 2 thu:
  1) ml/soul_lines.py doc dung cap <ten dong> <gia tri> tu OCR words (ghep hang).
  2) tasks/enhance_soul.py._decide ra quyet dinh dung (trung dich -> tiep, truot -> dung).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "ml"))
sys.path.insert(0, os.path.join(ROOT, "tasks"))

from soul_lines import parse_lines, stat_of, SoulLine, parse_value  # noqa: E402
import enhance_soul as ES  # noqa: E402
from enhance_soul import _decide, _stats_diff, read_level  # noqa: E402


def W(text, x, y, w=90, h=20, conf=80):
    """Helper: 1 ket qua OCR."""
    return (text, (x, y, w, h), conf)


# --- 1. Doc dong phu ---------------------------------------------------------
def test_parse_value():
    assert parse_value("12%") == (12.0, True)
    assert parse_value("+3") == (3.0, False)
    assert parse_value("2.8") == (2.8, False)
    assert parse_value("abc") == (None, False)
    print("  [ok] parse_value")


def test_stat_alias():
    assert stat_of(SoulLine("Attack Bonus")) == "atk_pct"
    assert stat_of(SoulLine("Crit DMG")) == "crit_dmg"
    assert stat_of(SoulLine("Effect Hit")) == "eff_hit"
    assert stat_of(SoulLine("SPEED")) == "spd"
    assert stat_of(SoulLine("khong phai dong nao")) is None
    print("  [ok] alias ten dong phu")


def test_parse_soul_panel():
    """Man chi tiet soul: ten dong ben trai, gia tri ben phai, cung 1 hang."""
    words = [
        W("Moan", 200, 60), W("+15", 900, 60),            # header: ten soul + muc
        W("Attack Bonus", 300, 300), W("4%", 700, 302),
        W("Speed", 300, 340), W("2", 700, 341),
        W("Crit Rate", 300, 380), W("3%", 700, 379),
        W("Effect RES", 300, 420), W("4%", 700, 421),
        W("Enhance", 1040, 630),                          # nut (khong phai dong phu)
    ]
    st = parse_lines(words)
    assert st.stats == {"atk_pct": 4.0, "spd": 2.0, "crit": 3.0, "eff_res": 4.0}, st.stats
    assert read_level(None, words) == 15
    print("  [ok] parse panel soul:", st.stats)


def test_number_not_stolen_across_rows():
    """So cua hang duoi khong duoc gan cho ten hang tren."""
    words = [
        W("Speed", 300, 340), W("2", 700, 400),           # so lech hang (60px)
        W("Crit Rate", 300, 400), W("3%", 700, 402),
    ]
    st = parse_lines(words)
    assert st.stats.get("crit") == 3.0, st.stats
    assert "spd" not in st.stats, st.stats   # so lech hang -> khong nhan
    print("  [ok] khong gan lan so giua cac hang")


# --- 2. Quyet dinh chien thuat ----------------------------------------------
def test_decide_hit_then_stop_at_max():
    cont, why = _decide({"spd": 2.8}, {"spd"}, 3, 15)
    assert cont is True, why
    cont, why = _decide({"spd": 2.8}, {"spd"}, 15, 15)
    assert cont is False and "dat dich" in why, why
    print("  [ok] trung dich -> di tiep; cham max_level -> dung giu")


def test_decide_miss_stops():
    cont, why = _decide({"atk_pct": 4.0}, {"spd"}, 3, 15)
    assert cont is False and "truot" in why, why
    print("  [ok] truot -> dung (giu lam thuc an)")


def test_decide_unreadable():
    cont, why = _decide({}, {"spd"}, 3, 15)
    assert cont is None and "khong doc duoc" in why, why
    print("  [ok] OCR khong doc duoc -> khong quyet dinh bua")


def test_stats_diff_detects_new_and_raised():
    from soul_lines import SoulState
    before = SoulState({"spd": 2.0, "atk_pct": 4.0})
    after = SoulState({"spd": 4.8, "atk_pct": 4.0, "crit": 3.0})
    d = _stats_diff(before, after)
    assert d == {"spd": 2.8, "crit": None}, d
    print("  [ok] diff phat hien dong tang + dong moi:", d)


def test_simulation_allin_rate():
    """Mo phong chien thuat: do ti le hit khi roll deu 1/4 tren 4 dong.

    Khong phai test tinh luan ly - chi kiem chien thuat loc som THUC SU cat som:
    voi 4 dong va target 1 dong, so lan roll trung binh truoc khi truot phai nho
    (dong nghia bot tiet kiem soul).
    """
    import random
    random.seed(7)
    keys = ["spd", "atk_pct", "crit", "eff_res"]
    target = {"spd"}
    rolls, cuts, total_kept = 0, 0, 0
    for _ in range(2000):
        # moi soul con 4 dong; roll tung moc den khi truot hoac het 5 moc
        kept = 0
        for _lvl in range(5):
            k = random.choice(keys)
            rolls += 1
            if k in target:
                kept += 1
            else:
                cuts += 1
                break
        total_kept += kept
    assert rolls > 0 and cuts > 0
    # 3/4 so lan roll dau tien la truot -> ti le "cat" phai cao (>=60%)
    assert cuts / rolls >= 0.6, cuts / rolls
    print(f"  [ok] mo phong: {rolls} lan roll, cat som {cuts} "
          f"({100 * cuts / rolls:.0f}%), tong so lan trung dich {total_kept}")


def test_task_end_to_end_with_fake_agent():
    """Chay NGUYEN task voi FakeAgent + OCR gia -> kiem vong doi + ghi log + dry.

    Day la test quan trong nhat: bao dam task thuc su doc duoc dong phu, quyet dinh
    va KHONG bam gi khi dry=True.
    """
    import tempfile

    class FR:
        def has(self, t):
            return False

    class FC:
        def __init__(self):
            self.clicks = []

        def bgclick(self, x, y):
            self.clicks.append((x, y))

    class FA:
        def __init__(self):
            self.c = FC()
            self.backs = 0

        def shot(self):
            import numpy as np
            return np.zeros((679, 1152, 3), np.uint8)

        def read(self, *a, **k):
            return FR()

        def tap_text(self, *a, **k):
            return (False, None)

        def back(self):
            self.backs += 1

    # OCR gia: lan dau doc 4 dong, sau khi cuong hoa Speed tang (trung dich)
    panel = [W("Speed", 300, 340), W("2.4", 700, 341),
             W("Crit Rate", 300, 380), W("3%", 700, 379),
             W("+0", 900, 60)]
    raised = [W("Speed", 300, 340), W("5.2", 700, 341),
              W("Crit Rate", 300, 380), W("3%", 700, 379),
              W("+3", 900, 60)]
    calls = {"n": 0}

    def fake_ocr(img, min_conf=30):
        calls["n"] += 1
        # moi soul: lan dau tra panel, lan sau (sau khi bam) tra raised
        return panel if calls["n"] % 2 == 1 else raised

    old_ocr, old_log = ES._ocr_words, ES.LOG
    ES._ocr_words = fake_ocr
    fd, tmp = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    ES.LOG = tmp
    try:
        a = FA()
        assert ES.enhance_soul(a, target="spd", times=1, dry=True) is True
        assert a.c.clicks == [], f"dry=True ma van bam: {a.c.clicks}"

        # --live: phai co bam nut cuong hoa va ghi log
        a2 = FA()
        calls["n"] = 0
        assert ES.enhance_soul(a2, target="spd", times=1, dry=False) is True
        assert a2.c.clicks, "dry=False ma khong bam gi"
        import json
        rows = [json.loads(l) for l in open(tmp) if l.strip()]
        assert any(r.get("summary") for r in rows), "thieu dong summary"
        rec = [r for r in rows if not r.get("summary")][0]
        assert rec["rolled"] == {"spd": 2.8}, rec["rolled"]
        assert rec["hit"] is True and rec["decision"] == "keep", rec
        print(f"  [ok] task E2E: dry khong bam, live ghi log {rec['rolled']} -> keep")
    finally:
        ES._ocr_words, ES.LOG = old_ocr, old_log
        os.path.exists(tmp) and os.remove(tmp)


def test_task_no_click_when_not_soul_screen():
    """Neu OCR khong thay dong phu nao (khong phai man soul) -> dung, KHONG bam."""
    class FA:
        def __init__(self):
            self.clicked = False

        def shot(self):
            import numpy as np
            return np.zeros((679, 1152, 3), np.uint8)

        def back(self):
            pass

    old_ocr = ES._ocr_words
    ES._ocr_words = lambda img, min_conf=30: [W("Home", 100, 100)]
    try:
        ES.enhance_soul(FA(), target="spd", times=3, dry=False)
        print("  [ok] man khong phai soul -> dung an toan, khong bam mu")
    finally:
        ES._ocr_words = old_ocr


def main():
    for fn in [test_parse_value, test_stat_alias, test_parse_soul_panel,
               test_number_not_stolen_across_rows, test_decide_hit_then_stop_at_max,
               test_decide_miss_stops, test_decide_unreadable,
               test_stats_diff_detects_new_and_raised, test_simulation_allin_rate,
               test_task_end_to_end_with_fake_agent,
               test_task_no_click_when_not_soul_screen]:
        fn()
    print("OK - tat ca test soul enhance pass (offline)")


if __name__ == "__main__":
    main()
