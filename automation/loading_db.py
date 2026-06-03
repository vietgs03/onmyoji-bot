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
        h = phash(img)
        if h:
            idx[os.path.basename(f)] = h
    json.dump(idx, open(OUT, "w"))
    print(f"built {OUT}: {len(idx)} loading artwork hashed (pHash {_HASH_SIZE*_HASH_SIZE} bit)")
    return idx


class LoadingDB:
    """Tra lazy: load index 1 lan, match nhanh."""
    _idx = None

    def __init__(self, threshold=None):
        # nguong hamming: 256-bit, <~25 (10%) coi nhu khop. Loading artwork rat dac trung.
        self.threshold = threshold if threshold is not None else 28
        if LoadingDB._idx is None:
            LoadingDB._idx = json.load(open(OUT)) if os.path.exists(OUT) else {}
        self.idx = LoadingDB._idx

    def match(self, img):
        """Tra (ten_anh, hamming) cua loading artwork gan nhat, hoac (None, dist)."""
        h = phash(img)
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
