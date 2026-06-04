"""state_solver - GIAI MAN HINH NHU MA TRAN TRANG THAI (khong hoc vet duong cung).

Y tuong (theo de bai dung): moi man hinh = 1 trang thai cua bai toan search. Ta co
DICH (goal predicate, vd 'man co nut Explore'). Tu trang thai bat ky, bot SINH cac
hanh dong kha di (back/X, tap-text, tap-button CV, pan/keo, wake-tap), THU, quan sat
trang thai moi, va HOC: hanh dong nao o trang thai-co-chu-ky-X dua toi gan dich.

Khac 'hoc vet': ta khong nho 'click 571,191'. Ta nho 'O trang thai co chu ky S
(vd event popup / courtyard idle), hanh dong A (vd back arrow / wake-tap) co gia tri V'.
Chu ky trang thai = dhash tho + tap OCR token chinh -> tong quat cho man tuong tu.

Bo nho: Q[state_sig][action] = gia tri (EWMA reward). Luu knowledge/solver_q.json.
Reward: +1 toi dich; -step_cost moi buoc; +shaping neu so token-dich xuat hien tang.

Hanh dong:
  back      : find_dismiss (icon back/X hoac chu Cancel/Exit/Skip).
  tap:<word>: OCR tim <word> roi tap (vd 'Explore','Confirm').
  wake      : tap giua man (danh thuc idle screensaver).
  pan:<dir> : keo man (left/right/up/down) - courtyard lo menu.
  btn:i     : tap nut thu i do CV detect (perception.detect_buttons).
"""
from __future__ import annotations
import os, sys, json, time, hashlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "automation"), os.path.join(ROOT, "scripts"),
          os.path.join(ROOT, "ml")):
    if p not in sys.path:
        sys.path.insert(0, p)

from perception import dhash, hamming, detect_buttons     # noqa: E402
from screen_reader import ocr_words                        # noqa: E402

QFILE = os.path.join(ROOT, "knowledge", "solver_q.json")
ALPHA = 0.4          # toc do hoc EWMA
STEP_COST = 0.05     # phat moi buoc (uu tien giai nhanh)
EPS = 0.25           # ti le tham hiem (thu hanh dong moi)


# ----------------------------------------------------------------------
# CHU KY TRANG THAI: CHI cac nhan UI co dinh (bo dhash + token nhieu) -> on dinh.
# ----------------------------------------------------------------------
import re

# Tu khoa DONG (nhieu) - PHAI LOAI khoi state_sig vi doi tung frame/giay:
#  - dong chat the gioi (got/lucky/drew/opened/challenging/requested/wishes...)
#  - dong ho (mon/tue/wed.../est/utc), tien/so (chua chu so), ten nguoi choi.
# Neu de chung vao chu ky thi MOI FRAME ra 1 state-key khac -> Q-learning vo dung.
_NOISE_WORDS = {
    "got", "lucky", "drew", "opened", "returnee", "received", "challenging",
    "requested", "others", "join", "wishes", "become", "apprentice", "triggered",
    "zone", "add", "them", "friend", "frienas", "master", "thomas", "thomag",
    "homas", "homd", "homg", "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    "thur", "est", "utc", "gmt", "new", "tap", "spirit", "coin", "shard", "box",
    "and", "has", "the", "you", "are", "back", "not", "long", "ago", "this",
    "with", "news", "your", "loyal",
}
_TIME_RE = re.compile(r"\d|:")          # token co chu so / dau ':' = dong ho/so lieu


def ui_tokens(ocr_words_list) -> set[str]:
    """Tap nhan UI ON DINH cua 1 man: token NGAN (3-15 ky tu), 1 tu, conf cao (>=70),
    khong chu so/':', khong trong _NOISE_WORDS. Conf cao -> bot OCR jitter."""
    out = set()
    for t, _box, c in ocr_words_list:
        s = str(t).strip().lower()
        if (3 <= len(s) <= 15 and any(ch.isalpha() for ch in s)
                and " " not in s and not _TIME_RE.search(s)
                and s not in _NOISE_WORDS and float(c) >= 70):
            out.add(s)
    return out


def state_sig(img, ocr_tokens: list[str]) -> str:
    """Chu ky on dinh (giu API cu) - hash tap nhan UI. NHUNG so khop chinh nen dung
    match_state (Jaccard) vi OCR jitter lam tap doi nhe -> hash exact van le."""
    ui = sorted({t.lower() for t in ocr_tokens
                 if 3 <= len(t) <= 15 and any(c.isalpha() for c in t)
                 and " " not in t.strip() and not _TIME_RE.search(t)
                 and t.lower() not in _NOISE_WORDS})[:10]
    return hashlib.md5("|".join(ui).encode()).hexdigest()[:12]


class StateSolver:
    """Giai man hinh huong-dich bang search + Q-learning nhe."""

    def __init__(self, agent):
        self.a = agent
        self.q: dict[str, dict[str, float]] = {}
        # toks[state_id] = tap nhan UI dai dien -> so khop Jaccard (chong OCR jitter)
        self.toks: dict[str, list[str]] = {}
        if os.path.exists(QFILE):
            try:
                blob = json.load(open(QFILE, encoding="utf-8"))
                # ho tro ca format cu (chi q) lan moi ({q, toks})
                if isinstance(blob, dict) and "q" in blob:
                    self.q = blob.get("q", {})
                    self.toks = {k: list(v) for k, v in blob.get("toks", {}).items()}
                else:
                    self.q = blob
            except Exception:
                self.q = {}

    def save(self):
        os.makedirs(os.path.dirname(QFILE), exist_ok=True)
        json.dump({"q": self.q, "toks": {k: sorted(v) for k, v in self.toks.items()}},
                  open(QFILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    @staticmethod
    def _jaccard(a: set, b: set) -> float:
        if not a and not b:
            return 1.0
        u = a | b
        return len(a & b) / len(u) if u else 0.0

    def match_state(self, ui: set[str], thresh: float = 0.5) -> str:
        """So khop tap nhan UI hien tai voi state DA BIET bang Jaccard. Neu trung
        >= thresh -> tai su dung state-id cu (chia se Q). Nguoc lai tao state-id moi.
        Day la chia khoa: OCR jitter (onmyoji/onmyojt) chi lam Jaccard giam nhe, van
        khop -> bot HOC duoc thay vi moi frame 1 state."""
        best_id, best = None, 0.0
        for sid, toks in self.toks.items():
            j = self._jaccard(ui, set(toks))
            if j > best:
                best, best_id = j, sid
        if best_id is not None and best >= thresh:
            return best_id
        # state moi: id = hash tap ui (on dinh tuong doi)
        sid = hashlib.md5("|".join(sorted(ui)).encode()).hexdigest()[:12]
        self.toks[sid] = sorted(ui)
        return sid

    # ----- quan sat -----
    def observe(self):
        img = self.a.shot()
        words = ocr_words(img, min_conf=40)
        toks = [str(t) for t, *_ in words]
        ui = ui_tokens(words)                 # tap nhan UI on dinh
        sig = self.match_state(ui)            # Jaccard match -> state-id chia se Q
        return img, words, toks, sig

    # ----- sinh hanh dong kha di tai 1 trang thai -----
    def actions(self, img, words, toks, goal_words):
        """Tra list (action_str, callable). Action chung + theo ngu canh."""
        acts = []
        low = " ".join(toks).lower()
        # 1) back/X/Cancel/Skip - thoat popup/man con (manh nhat de ve goc)
        acts.append(("back", lambda: self.a.back(wait=2.0)))
        # 2) tap dung tu DICH neu thay (vd thay 'Explore' -> tap luon)
        for gw in goal_words:
            if any(gw.lower() in t.lower() for t in toks):
                acts.append((f"tap:{gw}", lambda gw=gw: self.a.tap_text(gw, wait=2.5)))
        # 3) wake-tap giua (idle screensaver)
        acts.append(("wake", lambda: (self.a.c.bgclick(576, 340), time.sleep(2.5))))
        # 4) pan 4 huong (courtyard lo menu)
        for d, (x0, y0, x1, y1) in {
                "pan:left":  (820, 400, 240, 400),
                "pan:right": (240, 400, 900, 400),
                "pan:up":    (576, 480, 576, 180),
                "pan:down":  (576, 200, 576, 480)}.items():
            acts.append((d, lambda a=(x0, y0, x1, y1): (
                self.a.c.bgdrag(*a, 18), time.sleep(2.0))))
        # 5) cac nut CV detect (toa do) - tham hiem co dieu huong
        try:
            btns = detect_buttons(img)[:6]
        except Exception:
            btns = []
        for i, b in enumerate(btns):
            cx, cy = (b[0] + b[2] // 2, b[1] + b[3] // 2) if len(b) >= 4 else b[:2]
            acts.append((f"btn:{cx},{cy}",
                         lambda cx=cx, cy=cy: self.a.click(cx, cy, wait=2.5)))
        return acts

    # ----- danh gia tien do toi dich (shaping) -----
    @staticmethod
    def goal_score(toks, goal_words):
        """So tu-dich xuat hien (de shaping: cang nhieu cang gan dich)."""
        low = [t.lower() for t in toks]
        return sum(1 for gw in goal_words if any(gw.lower() in t for t in low))

    def reached(self, toks, goal_words, need_all=True):
        s = self.goal_score(toks, goal_words)
        return s == len(goal_words) if need_all else s > 0

    # ----- uu tien (prior) cua hanh dong khi CHUA co Q (tri thuc tien nghiem) -----
    @staticmethod
    def _prior(name: str) -> float:
        """Diem uu tien tien nghiem: tap dung tu-dich > back > wake > pan > btn.
        Dan huong tham hiem hop ly thay vi random deu (back/tap-goal hay thoat nhat)."""
        if name.startswith("tap:"):
            return 5.0          # thay nut dich -> tap luon
        if name == "back":
            return 4.0          # thoat popup/man con ve goc - manh nhat
        if name == "wake":
            return 2.0          # danh thuc idle
        if name.startswith("pan:"):
            return 1.0          # courtyard lo menu
        return 0.5              # btn CV - tham hiem cuoi

    # ----- chinh: giai toi dich -----
    def solve(self, goal_words, need_all=True, max_steps=12, verbose=True):
        """Tu trang thai hien tai, tim chuoi hanh dong toi man co tat ca goal_words.
        Tra True neu toi dich. HOC vao self.q theo chu ky trang thai."""
        import random
        recent_sigs = []        # phat hien lap (ket vong trong) -> ep back
        for step in range(max_steps):
            img, words, toks, sig = self.observe()
            if self.reached(toks, goal_words, need_all):
                if verbose:
                    print(f"[solver] buoc {step}: DICH dat ({goal_words})")
                self.save()
                return True
            acts = self.actions(img, words, toks, goal_words)
            qrow = self.q.setdefault(sig, {})
            before = self.goal_score(toks, goal_words)

            # GIA TRI quyet dinh = Q da hoc (neu co) + prior (neu chua thu).
            def val(name):
                return qrow[name] if name in qrow else self._prior(name)

            stuck = recent_sigs.count(sig) >= 2          # quanh quan o sig nay
            if stuck:
                # ket vong -> ep 'back' de thoat (du da thu) tranh loop vo han
                name, fn = next((a for a in acts if a[0] == "back"), acts[0])
                why = "STUCK->back"
            elif random.random() < EPS:
                name, fn = random.choice(acts)           # tham hiem ngau nhien
                why = "tham-hiem(eps)"
            else:
                name, fn = max(acts, key=lambda a: val(a[0]))  # greedy theo val
                why = f"val={val(name):.2f}"
            if verbose:
                print(f"[solver] buoc {step} sig={sig} -> '{name}' ({why})")

            try:
                fn()
            except Exception as e:
                if verbose:
                    print(f"[solver]   action loi: {e}")

            # quan sat ket qua + tinh reward
            _, _, toks2, sig2 = self.observe()
            after = self.goal_score(toks2, goal_words)
            done = self.reached(toks2, goal_words, need_all)
            moved = (sig2 != sig)                        # trang thai co doi khong
            reward = (1.0 if done else 0.0) + 0.1 * (after - before) - STEP_COST
            if not moved and not done:
                reward -= 0.1                            # phat action vo dung (khong doi man)
            old = qrow.get(name, self._prior(name))
            qrow[name] = old + ALPHA * (reward - old)    # EWMA update
            if verbose and (after != before or not moved):
                print(f"[solver]   tien do {before}->{after}, moved={moved}, "
                      f"reward {reward:+.2f}, Q['{name}']={qrow[name]:.2f}")
            recent_sigs = (recent_sigs + [sig])[-4:]
            if done:
                self.save()
                return True
        self.save()
        if verbose:
            print(f"[solver] het {max_steps} buoc, chua toi dich {goal_words}")
        return False


if __name__ == "__main__":
    # demo: giai ve HOME (man co Explore + Summon) tu trang thai bat ky.
    sys.path.insert(0, os.path.join(ROOT, "automation"))
    from agent import Agent
    a = Agent()
    s = StateSolver(a)
    goal = sys.argv[1:] or ["Explore", "Summon"]
    ok = s.solve(goal, need_all=True, max_steps=int(os.environ.get("STEPS", 14)))
    print("KET QUA:", ok)
