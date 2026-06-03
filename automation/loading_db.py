#!/usr/bin/env python3
"""
loading_db.py - Nhan dien CHAC CHAN man hinh LOADING/chuyen canh bang artwork DB.

Y tuong (senior): game Onmyoji co bo ~260 ANH LOADING co dinh (illustration man cho)
da rip o data/game_assets/en_loading/. Khi game chuyen canh, no hien 1 trong cac anh
nay (toan man, watermark 'ONMYOJI' goc duoi). Thay vi DOAN 'da load xong chua' bang
so button (de sai voi loading artwork sang), ta MATCH screenshot voi DB nay bang
perceptual-hash (pHash). Khop -> dang loading 100% chac chan -> doi tiep.

Uu diem vs heuristic cu:
  - is_loading() cu chi bat loading TOI (den). Loading ARTWORK sang thi truot.
  - DB-match bat duoc CA loading artwork sang (vi no nam trong 260 anh da biet).
  - pHash ben voi resize/crop/nen nhe.

Build index 1 lan -> knowledge/loading_hashes.json (256-bit pHash moi anh).

Dung:
  python loading_db.py build        -> sinh index
  python loading_db.py test <anh>   -> co phai loading? khop anh nao?
  from loading_db import LoadingDB; db=LoadingDB(); db.is_loading(img)
"""
import os, sys, json, glob
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOAD_DIR = os.path.join(ROOT, "data", "game_assets", "en_loading")
OUT = os.path.join(ROOT, "knowledge", "loading_hashes.json")

_HASH_SIZE = 16   # pHash 16x16 = 256 bit (du phan biet, ben voi nhieu)

# Game hien loading bang cach CAT 64px moi ben artwork goc (1280 -> 1152), KHONG zoom.
# (do bang ORB affine: art456 -> game74 chi tx=-64, scale=1). Crop nay cho phep
# hash artwork DB GIONG het cach game hien -> match chinh xac.
_CROP_X = 64       # so px cat moi ben artwork goc (1280 wide)


def game_crop(art):
    """Mo phong cach game crop artwork goc 1280xH -> vung hien 1152xH."""
    if art is None:
        return art
    w = art.shape[1]
    if w >= 1280:
        return art[:, _CROP_X:w - _CROP_X]
    return art


def phash(img, hash_size=_HASH_SIZE):
    """Perceptual hash (DCT) -> chuoi bit. Ben voi resize/sang-toi nhe."""
    if img is None or img.size == 0:
        return None
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    # DCT tren anh 4x lon hon roi lay goc tan-so-thap
    big = cv2.resize(g, (hash_size * 4, hash_size * 4)).astype(np.float32)
    dct = cv2.dct(big)
    low = dct[:hash_size, :hash_size]
    med = np.median(low[1:, 1:])         # bo DC (goc 0,0) khoi median
    bits = (low > med).flatten()
    return "".join("1" if b else "0" for b in bits)


def _hamming(a, b):
    return sum(c1 != c2 for c1, c2 in zip(a, b))


def build():
    files = sorted(glob.glob(os.path.join(LOAD_DIR, "*.png")))
    idx = {}
    for f in files:
        img = cv2.imread(f)
        h = phash(game_crop(img))   # hash theo CACH GAME HIEN (cat 64px 2 ben)
        if h:
            idx[os.path.basename(f)] = h
    json.dump(idx, open(OUT, "w"))
    print(f"built {OUT}: {len(idx)} loading artwork hashed "
          f"(pHash {_HASH_SIZE*_HASH_SIZE} bit, game-crop)")
    return idx


class LoadingDB:
    """Tra lazy: load index 1 lan, match nhanh."""
    _idx = None

    def __init__(self, threshold=None):
        # 256-bit pHash. Artwork that khop ham 23-34; man UI thuong ham >100.
        # Bien rat rong -> nguong 38 an toan tuyet doi (0 false-pos do DB).
        self.threshold = threshold if threshold is not None else 38
        if LoadingDB._idx is None:
            LoadingDB._idx = json.load(open(OUT)) if os.path.exists(OUT) else {}
        self.idx = LoadingDB._idx

    def _prep(self, img):
        """Bo titlebar windows (~32px tren) khoi screenshot game truoc khi hash."""
        if img is None:
            return None
        if img.shape[0] > 660:           # screenshot game co titlebar
            return img[32:]
        return img

    def match(self, img):
        """Tra (ten_anh, hamming) cua loading artwork gan nhat, hoac (None, dist)."""
        h = phash(self._prep(img))
        if not h or not self.idx:
            return None, 999
        best, bd = None, 999
        for name, hh in self.idx.items():
            d = _hamming(h, hh)
            if d < bd:
                bd, best = d, name
        if bd <= self.threshold:
            return best, bd
        return None, bd

    def is_loading(self, img):
        """True neu screenshot khop 1 loading artwork trong DB."""
        name, _ = self.match(img)
        return name is not None


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "test":
        img = cv2.imread(sys.argv[2])
        db = LoadingDB()
        name, d = db.match(img)
        print(f"loading={name is not None}  khop={name}  hamming={d}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
