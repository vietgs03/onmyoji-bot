#!/usr/bin/env python3
"""
Client cho ps/server.ps1 - giu 1 PowerShell persistent qua stdin/stdout pipe.
Loai bo overhead spawn powershell.exe (~1s) moi lenh -> bgshot/bgclick nhanh hon nhieu.

Dung:
    from control_client import Controller
    ctl = Controller()
    img = ctl.bgshot()      # numpy BGR
    ctl.bgclick(x, y)
    ctl.close()
"""
import subprocess, os, time, shutil, select
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_SRC = os.path.join(ROOT, "ps", "server.ps1")
WIN_SERVER = r"C:\Users\Public\onmyoji_server.ps1"
WIN_SERVER_WSL = "/mnt/c/Users/Public/onmyoji_server.ps1"
WIN_SHOT = r"C:\Users\Public\onmyoji_srv.png"
WIN_SHOT_WSL = "/mnt/c/Users/Public/onmyoji_srv.png"


class Controller:
    def __init__(self):
        # sync server script sang Windows
        if (not os.path.exists(WIN_SERVER_WSL)
                or os.path.getmtime(SERVER_SRC) > os.path.getmtime(WIN_SERVER_WSL)):
            shutil.copy(SERVER_SRC, WIN_SERVER_WSL)
        # BINARY mode (bufsize=0): doc duoc CA dong ASCII (lenh thuong) LAN raw
        # binary (bgshot_raw gui thang pixel qua pipe). text=True khong doc duoc
        # raw bytes, nen ta tu decode dong ASCII bang _readline_bytes.
        self.proc = subprocess.Popen(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", WIN_SERVER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=0)
        # doc dong "OK ready"
        line = self._readline(timeout=20)
        if not line or not line.startswith("OK"):
            raise RuntimeError(f"server khong san sang: {line!r}")

    def _read_exact(self, n, timeout=15):
        """Doc DUNG n byte tu stdout (cho payload raw). Tra bytes hoac None khi
        timeout/EOF. Dung select de khong treo vo han."""
        if self.proc.stdout is None:
            return None
        fd = self.proc.stdout.fileno()
        end = time.time() + timeout
        buf = bytearray()
        while len(buf) < n:
            remain = end - time.time()
            if remain <= 0:
                return None
            r, _, _ = select.select([fd], [], [], remain)
            if not r:
                return None
            chunk = self.proc.stdout.read(n - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)

    def _readline_bytes(self, timeout=15):
        """Doc 1 dong (den \\n) tu stdout binary, tra bytes (khong gom \\n).
        Doc tung byte de KHONG nuot mat byte raw phia sau header."""
        if self.proc.stdout is None:
            return None
        fd = self.proc.stdout.fileno()
        end = time.time() + timeout
        buf = bytearray()
        while True:
            remain = end - time.time()
            if remain <= 0:
                return None
            r, _, _ = select.select([fd], [], [], remain)
            if not r:
                return None
            c = self.proc.stdout.read(1)
            if not c:
                return None if not buf else bytes(buf)
            if c == b"\n":
                return bytes(buf)
            if c != b"\r":  # bo CR (CRLF tu PowerShell)
                buf.extend(c)

    def _readline(self, timeout=15):
        """Doc 1 dong ASCII (lenh thuong). Wrap _readline_bytes + decode."""
        b = self._readline_bytes(timeout=timeout)
        return b.decode("utf-8", "replace").strip() if b is not None else None

    def _cmd(self, line):
        self.proc.stdin.write((line + "\n").encode("utf-8"))
        self.proc.stdin.flush()
        return self._readline()

    def bgshot(self):
        r = self._cmd(f"bgshot {WIN_SHOT}")
        if not r or not r.startswith("OK"):
            return None
        # BUG da gap: game KHONG chay -> server tra 'OK 0x0 pw=False' nhung file
        # anh CU van con tren disk -> cv2.imread doc anh STALE (bot "nhin" man
        # hinh ngay cu, click noop toan bo). Phai check kich thuoc that.
        parts = r.split()
        if len(parts) >= 2 and "x" in parts[1]:
            try:
                w, h = parts[1].split("x")
                if int(w) <= 0 or int(h) <= 0:
                    return None  # game khong chay / window khong ton tai
            except ValueError:
                pass
        return cv2.imread(WIN_SHOT_WSL)

    def bgshot_raw(self):
        """Chup NHANH: nhan raw BGR24 thang qua stdout pipe, BO QUA encode PNG +
        file 9P + decode. Nhanh ~5-25x bgshot() (do 30ms vs 137-750ms).
        Tra numpy BGR (h,w,3) hoac None neu game khong chay / loi.
        Giao thuc: server gui 'RAW <w> <h> <nbytes>\\n' roi <nbytes> byte BGR."""
        self.proc.stdin.write(b"bgshot_raw\n")
        self.proc.stdin.flush()
        hdr = self._readline()
        if not hdr or not hdr.startswith("RAW"):
            return None
        parts = hdr.split()
        if len(parts) != 4:
            return None
        try:
            w, h, n = int(parts[1]), int(parts[2]), int(parts[3])
        except ValueError:
            return None
        if w <= 0 or h <= 0 or n <= 0:
            return None  # game khong chay
        data = self._read_exact(n)
        if data is None or len(data) != n:
            return None
        return np.frombuffer(data, dtype=np.uint8).reshape(h, w, 3)


    def bgclick(self, x, y):
        # NeoX (game Onmyoji) BO QUA PostMessage (async) -> dung sendclick
        # (SendMessage dong bo) moi an. Giu ten bgclick cho tuong thich API.
        return self._cmd(f"sendclick {int(x)} {int(y)}")

    def pmclick(self, x, y):
        """PostMessage click (async, NeoX hay bo qua). Giu lai de test/so sanh."""
        return self._cmd(f"bgclick {int(x)} {int(y)}")

    def fgclick(self, x, y):
        """Foreground click THAT (focus + di chuot + bam). Tin cay tren modal ma
        ca PostMessage lan SendMessage bi bo qua (vd dialog Claim All Mailbox)."""
        return self._cmd(f"fgclick {int(x)} {int(y)}")

    def politeclick(self, x, y):
        """Click 'lich su': focus game + di chuot toi + bam + TRA chuot ve cho user
        ngay. Thuc nghiem cho thay TIN CAY HON fgclick tren cac modal nhan thuong
        (vd 'Claim' Exclusive Gifts) ma fgclick doi khi khong an. Nen dung mac dinh
        cho cac nut nhan thuong / dong popup."""
        return self._cmd(f"politeclick {int(x)} {int(y)}")

    def bgdrag(self, x0, y0, x1, y1, steps=12):
        """Keo/scroll KHONG chiem chuot (SendMessage down->moves->up)."""
        return self._cmd(f"senddrag {int(x0)} {int(y0)} {int(x1)} {int(y1)} {int(steps)}")

    def info(self):
        return self._cmd("info")

    def movewin(self, x=0, y=0):
        """Dua cua so game ve toa do (x,y) tren man chinh (mac dinh 0,0).
        FIX GOC: cua so off-screen (4047,-72) lam politeclick footer that bai.
        Goi truoc khi can click chinh xac bang chuot that (footer/header)."""
        return self._cmd(f"movewin {int(x)} {int(y)}")

    def ping(self):
        return self._cmd("ping")

    def close(self):
        try:
            self._cmd("quit")
        except Exception:
            pass
        try:
            self.proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    ctl = Controller()
    print("info:", ctl.info())
    # warmup (JIT module .NET lan dau)
    for _ in range(3):
        ctl.bgshot(); ctl.bgshot_raw()
    n = 10
    t = time.time()
    for _ in range(n):
        img = ctl.bgshot()
    dt_png = (time.time() - t) / n
    t = time.time()
    for _ in range(n):
        raw = ctl.bgshot_raw()
    dt_raw = (time.time() - t) / n
    print(f"bgshot()     avg {dt_png*1000:5.0f} ms  shape={None if img is None else img.shape}")
    print(f"bgshot_raw() avg {dt_raw*1000:5.0f} ms  shape={None if raw is None else raw.shape}")
    if dt_raw > 0:
        print(f"-> raw nhanh {dt_png/dt_raw:.1f}x")
    ctl.close()
