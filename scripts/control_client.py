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
        self.proc = subprocess.Popen(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", WIN_SERVER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
        # doc dong "OK ready"
        line = self._readline(timeout=20)
        if not line or not line.startswith("OK"):
            raise RuntimeError(f"server khong san sang: {line!r}")

    def _readline(self, timeout=15):
        """Doc 1 dong tu server CO TIMEOUT thuc (select tren fd).
        Tranh treo vo han khi server PowerShell busy/chet (vd ket popup Summon,
        contention nhieu process). Tra None khi timeout -> caller xu ly nhe nhang."""
        if self.proc.stdout is None:
            return None
        fd = self.proc.stdout.fileno()
        end = time.time() + timeout
        while True:
            remain = end - time.time()
            if remain <= 0:
                return None
            r, _, _ = select.select([fd], [], [], remain)
            if not r:
                return None
            line = self.proc.stdout.readline()
            return line.strip() if line else None

    def _cmd(self, line):
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        return self._readline()

    def bgshot(self):
        r = self._cmd(f"bgshot {WIN_SHOT}")
        if not r or not r.startswith("OK"):
            return None
        return cv2.imread(WIN_SHOT_WSL)

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
    import numpy as np
    ctl = Controller()
    print("info:", ctl.info())
    t = time.time()
    n = 5
    for _ in range(n):
        img = ctl.bgshot()
    dt = (time.time() - t) / n
    print(f"bgshot avg {dt*1000:.0f} ms/shot, shape={None if img is None else img.shape}")
    ctl.close()
