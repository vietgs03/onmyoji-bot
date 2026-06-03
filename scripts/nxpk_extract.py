#!/usr/bin/env python3
"""
nxpk_extract.py - Giai nen kho asset NetEase NXPK (.npk) cua Onmyoji.

Format NXPK (NetEase):
  header: 'NXPK'(4) | file_count(u32) | unknown(12) | index_offset(u32) @20
  index : file_count * entry(28 byte):
          file_hash(u32) | offset(u32) | len_compressed(u32) | len_original(u32)
          | zip_flag(u32) | ... (bien the)  -> ta dung layout pho bien nhat.
  data  : zlib-compressed (zip_flag=1/2) hoac raw.

Cach dung:
  python nxpk_extract.py list <file.npk>                  # liet ke (magic ext doan tu header)
  python nxpk_extract.py extract <file.npk> <outdir> [--filter png] [--limit N]

Luu y: chi giai nen, KHONG giai ma. 1 so NPK NetEase co them lop ma hoa (rotor);
neu giai ra rac, tep do bi ma hoa -> bo qua (ta van lay duoc png/atlas khong ma hoa).
"""
import os, sys, struct, zlib

MAGIC = {
    b"\x89PNG": "png", b"\xff\xd8\xff": "jpg", b"DDS ": "dds",
    b"KTX ": "ktx", b"PKM ": "pkm", b"{\n": "json", b"{\r": "json",
    b"{ ": "json", b"<": "xml", b"OggS": "ogg", b"RIFF": "wav",
    b"\x1f\x8b": "gz", b"BKHD": "bnk", b"FSB5": "fsb",
}


def guess_ext(data):
    for sig, ext in MAGIC.items():
        if data[:len(sig)] == sig:
            return ext
    # text?
    try:
        s = data[:64].decode("ascii")
        if s.strip() and all(c.isprintable() or c in "\r\n\t" for c in s):
            return "txt"
    except Exception:
        pass
    return "bin"


def decrypt(data):
    """NetEase Onmyoji XOR decrypt (key bat dau 150, +1 mod 256, 128 byte dau).
    Tu zhouhang95/neox_tools/onmyoji_extractor.py."""
    data = bytearray(data)
    key = 150
    for i in range(min(len(data), 128)):
        data[i] ^= key
        key = (key + 1) % 256
    return bytes(data)


def read_index(f, count, index_off):
    """Entry 32 byte: sign,unknown,offset,len,orig_len,hash1,hash2,flag."""
    f.seek(index_off)
    raw = f.read(count * 32)
    entries = []
    for i in range(count):
        b = raw[i * 32:(i + 1) * 32]
        if len(b) < 32:
            break
        sign, unk, offset, clen, olen, h1, h2, flag = struct.unpack("<8I", b)
        entries.append((sign, offset, clen, olen, flag))
    return entries


def decompress(data, flag, olen):
    if flag & 0x10000:      # encrypted
        data = decrypt(data)
    if flag & 1:            # zlib
        try:
            data = zlib.decompress(data)
        except Exception:
            pass
    return data


def extract(npk, outdir, filt=None, limit=None):
    os.makedirs(outdir, exist_ok=True)
    with open(npk, "rb") as f:
        magic = f.read(4)
        if magic != b"NXPK":
            print("khong phai NXPK:", magic); return
        count, = struct.unpack("<I", f.read(4))
        f.seek(20)
        index_off, = struct.unpack("<I", f.read(4))
        entries = read_index(f, count, index_off)
        print(f"{count} files, index@0x{index_off:x}")
        n_ok = n_skip = 0
        stats = {}
        for i, (fhash, offset, clen, olen, zflag) in enumerate(entries):
            if limit and n_ok >= limit:
                break
            try:
                f.seek(offset)
                data = f.read(clen)
                data = decompress(data, zflag, olen)
            except Exception:
                n_skip += 1; continue
            ext = guess_ext(data)
            stats[ext] = stats.get(ext, 0) + 1
            if filt and ext != filt:
                continue
            name = f"{fhash:08x}.{ext}"
            sub = os.path.join(outdir, ext)
            os.makedirs(sub, exist_ok=True)
            with open(os.path.join(sub, name), "wb") as o:
                o.write(data)
            n_ok += 1
            if n_ok % 500 == 0:
                print(f"  ...{n_ok} extracted")
        print(f"\nextracted {n_ok}, skip {n_skip}")
        print("loai file (theo magic):", dict(sorted(stats.items(), key=lambda z: -z[1])))


def list_npk(npk):
    with open(npk, "rb") as f:
        magic = f.read(4)
        count, = struct.unpack("<I", f.read(4))
        f.seek(20); index_off, = struct.unpack("<I", f.read(4))
        entries = read_index(f, count, index_off)
        print(f"{magic} {count} files index@0x{index_off:x}")
        stats = {}
        for fhash, offset, clen, olen, zflag in entries[:2000]:
            try:
                f.seek(offset); data = f.read(min(clen, 64))
                data = decompress(data, zflag, olen)
                ext = guess_ext(data)
            except Exception:
                ext = "err"
            stats[ext] = stats.get(ext, 0) + 1
        print("mau 2000 file dau, loai:", dict(sorted(stats.items(), key=lambda z: -z[1])))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd, npk = sys.argv[1], sys.argv[2]
    if cmd == "list":
        list_npk(npk)
    elif cmd == "extract":
        outdir = sys.argv[3]
        filt = None
        limit = None
        if "--filter" in sys.argv:
            filt = sys.argv[sys.argv.index("--filter") + 1]
        if "--limit" in sys.argv:
            limit = int(sys.argv[sys.argv.index("--limit") + 1])
        extract(npk, outdir, filt, limit)

# GHI CHU: Onmyoji ban Steam hien tai MA HOA data trong NPK (khong phai zlib thuan).
# Giai ma can rotor/custom NetEase -> phuc tap + rui ro ToS. KHONG dao tiep.
# Asset EN sach da lay tu Documents/mulnation/en/ (loading art) + face_big/headicon.
