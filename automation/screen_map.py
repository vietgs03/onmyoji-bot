"""screen_map - KHAM PHA VET CAN 1 MAN HINH ("nhin 1 luot quanh 4 buc tuong").

Tu duy (theo de bai): khong hardcode toa do (game doi: doll di cho, mail to/nho/
doi mau). Thay vao do, khi BOT TOI 1 MAN, no QUET TAT CA affordance (nut chu, badge
do, tab) trong man -> THU tung cai -> GHI lai TAC DUNG (man moi ra la gi) vao bo nho
NGU NGHIA. Lan sau biet "trong Mailbox co: Claim All, Read All, tab System/Special".

Khac graph nav (chi nho canh giua cac man): day la BAN DO CHUC NANG BEN TRONG 1 man.

Bo nho: knowledge/screen_map.json
  { screen_key: {
      "label": ten man (vd 'mailbox'),
      "affordances": { aff_key: {
          "text": chu OCR (vd 'Claim All'),  # NGU NGHIA, khong phai toa do
          "tried": n, "effect": mo ta ket qua (man moi/popup/khong doi),
          "claim": True/False  # co phai nut nhan thuong khong
      }}
  }}

Nhan dien affordance theo NGU NGHIA (chu OCR) -> ben vung khi UI doi vi tri/size.
Toa do chi dung de TAP tai thoi diem do (doc lai moi lan, khong luu cung).
"""
from __future__ import annotations
import os, sys, json, time, hashlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "automation"), os.path.join(ROOT, "scripts"),
          os.path.join(ROOT, "ml")):
    if p not in sys.path:
        sys.path.insert(0, p)

from perception import dhash, detect_red_badges          # noqa: E402
from screen_reader import ocr_words                       # noqa: E402

MAPFILE = os.path.join(ROOT, "knowledge", "screen_map.json")

# Tu khoa NUT NHAN THUONG (claim) - phat hien semantic, khong theo vi tri.
CLAIM_HINT = ("claim", "receive", "collect", "redeem", "get all", "claim all",
              "sign", "check-in", "checkin", "reward")
# Nut DIEU HUONG / dong (khong phai claim, nhung dang thu de biet tac dung).
NAV_HINT = ("ok", "confirm", "read all", "back", "close", "cancel", "next",
            "go", "enter", "tab")


def screen_key(img, toks):
    """Khoa man theo bo cuc (dhash) + tap chu chinh -> gom man giong nhau."""
    dh = dhash(img) or ""
    keys = sorted({t.lower() for t in toks if len(t) >= 3 and any(c.isalpha() for c in t)})[:10]
    return hashlib.md5(f"{dh[:24]}|{'|'.join(keys)}".encode()).hexdigest()[:12]


class ScreenMap:
    """Kham pha + nho ban do chuc nang ben trong cac man."""

    def __init__(self, agent):
        self.a = agent
        self.m = {}
        if os.path.exists(MAPFILE):
            try:
                self.m = json.load(open(MAPFILE, encoding="utf-8"))
            except Exception:
                self.m = {}

    def save(self):
        os.makedirs(os.path.dirname(MAPFILE), exist_ok=True)
        json.dump(self.m, open(MAPFILE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    # ----- liet ke affordance: chu (button) + badge do -----
    def affordances(self, img):
        """Tra list dict {text, x, y, kind}. kind: 'text'|'badge'.
        'nhin quanh 4 buc tuong' = quet het nut chu + cham do."""
        out = []
        for t, (x, y, w, h), c in ocr_words(img, min_conf=45):
            s = str(t).strip()
            if 1 <= len(s) <= 20 and any(ch.isalpha() for ch in s):
                out.append({"text": s, "x": x + w // 2, "y": y + h // 2,
                            "kind": "text", "conf": float(c)})
        for cx, cy, ar in detect_red_badges(img, ui_only=True):
            out.append({"text": "", "x": cx, "y": cy + 18,
                        "kind": "badge", "area": ar})
        return out

    @staticmethod
    def is_claim(text):
        t = text.lower()
        return any(h in t for h in CLAIM_HINT)

    def observe(self):
        img = self.a.shot()
        toks = [str(t) for t, *_ in ocr_words(img, min_conf=40)]
        return img, toks, screen_key(img, toks)

    # ----- kham pha vet can 1 man: thu tung affordance, ghi tac dung -----
    def explore(self, label=None, max_try=12, claim_only=False,
                back_to=None, verbose=True):
        """O man HIEN TAI: liet ke affordance, thu tung cai (uu tien claim),
        ghi tac dung vao bo nho. back_to(callable) = cach ve man nay sau khi thu 1 nut.

        claim_only=True: chi bam nut co ve la nhan thuong (an toan, khong lung tung).
        Tra so muc da claim."""
        img, toks, skey = self.observe()
        rec = self.m.setdefault(skey, {"label": label, "affordances": {}})
        if label:
            rec["label"] = label
        affs = self.affordances(img)
        # uu tien: claim-button > badge > nav-button
        def pri(a):
            if a["kind"] == "text" and self.is_claim(a["text"]):
                return 3
            if a["kind"] == "badge":
                return 2
            return 1
        affs.sort(key=pri, reverse=True)

        if verbose:
            print(f"[map] man '{label or skey}': {len(affs)} affordance")
            for a in affs[:max_try]:
                tag = "CLAIM" if (a["kind"] == "text" and self.is_claim(a["text"])) else a["kind"]
                print(f"   - [{tag}] {a.get('text','') or '(badge)':18} @ ({a['x']},{a['y']})")

        claimed = 0
        for a in affs[:max_try]:
            akey = a["text"].lower() or f"badge@{a['x']//40},{a['y']//40}"
            ar = rec["affordances"].setdefault(akey, {"text": a["text"], "tried": 0,
                                                      "kind": a["kind"], "claim": None})
            is_claim = a["kind"] == "text" and self.is_claim(a["text"])
            if claim_only and not is_claim and a["kind"] != "badge":
                continue
            # THU: doc lai vi tri chu (UI co the doi) roi tap
            before_toks = self.observe()[1]
            self.a.click(a["x"], a["y"], wait=2.0)
            time.sleep(0.8)
            after_img, after_toks, after_key = self.observe()
            moved = after_key != skey
            # neu hien dialog co OK/Confirm -> day la nhan thuong -> xac nhan
            r = self.a.read(after_img)
            confirmed = False
            for w in ("OK", "Confirm", "Claim", "Receive"):
                if r.has(w):
                    hit = r.find(w)
                    if hit:
                        self.a.c.fgclick(hit[1], hit[2])   # modal cung -> fgclick
                        time.sleep(1.5)
                        confirmed = True
                        break
            ar["tried"] += 1
            ar["claim"] = bool(is_claim or confirmed)
            ar["effect"] = ("claimed" if confirmed else
                            ("opened" if moved else "no-change"))
            if confirmed:
                claimed += 1
                if verbose:
                    print(f"   + CLAIM '{a['text'] or akey}' -> nhan thuong")
            # ve lai man dang kham pha
            if back_to:
                back_to()
            elif moved or confirmed:
                self.a.back(wait=1.5)
            self.save()
        if verbose:
            print(f"[map] xong: claim {claimed} muc o '{label or skey}'")
        return claimed


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(ROOT, "automation"))
    from agent import Agent
    a = Agent()
    sm = ScreenMap(a)
    label = sys.argv[1] if len(sys.argv) > 1 else None
    sm.explore(label=label, claim_only=("--claim" in sys.argv),
               max_try=int(os.environ.get("TRY", 10)))
