"""onmyoji.adapters.eye_py - PythonEye: implement EyePort bang code hien co.

Bao boc Controller (PowerShell server) + perception.py (cv2) thanh EyePort.
KHONG viet lai logic - chi adapt API cu sang contract moi.

Day la impl MAC DINH. Sau nay RustEye (socket toi onmyoji-eye.exe) se thay the
ma tang application khong doi.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

# nap path toi code cu (scripts/) - se go bo khi refactor xong hoan toan
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
for _p in ("scripts", "automation"):
    _full = os.path.join(_ROOT, _p)
    if _full not in sys.path:
        sys.path.insert(0, _full)

from onmyoji.domain.entities import (
    Observation, Action, ActionKind, ActionResult, Button, Resources, Size,
)
from onmyoji.domain.ports import EyePort


class PythonEye(EyePort):
    """EyePort dung cv2 + PowerShell control (impl hien tai)."""

    def __init__(self, controller=None):
        # lazy import de domain/test khong can cv2
        from control_client import Controller
        self._c = controller or Controller()
        self._last_size = Size(0, 0)

    # kich thuoc CHUAN cua knowledge base (goldens + dhash state_id).
    # Game ep client 16:9 (1136x640) nhung KB duoc dung tren 1152x679.
    # dhash phai chay tren anh resize ve day de state_id khop KB; resize
    # client->canon cho hamming=0 (kiem chung tren state_fighting.png).
    CANON_W, CANON_H = 1152, 679

    # ---------- EyePort ----------
    def observe(self) -> Observation:
        import cv2
        from perception import dhash, is_loading, state_id, detect_buttons
        img = self._c.bgshot()
        ts = time.time()
        if img is None:
            # game khong chay / anh stale -> observation "chet"
            return Observation(
                ts=ts, state_id="DEAD", loading=False,
                size=self._last_size, buttons=(), alive=False,
            )
        h, w = img.shape[:2]
        self._last_size = Size(w, h)
        # dhash/state_id la VAN TAY DIEU HUONG -> tinh tren anh CHUAN (resize
        # ve canon) de khop knowledge base bat ke resolution thuc. Resize ve
        # 9x8 ben trong dhash nen khong anh huong toa do.
        if (w, h) != (self.CANON_W, self.CANON_H):
            canon = cv2.resize(img, (self.CANON_W, self.CANON_H))
        else:
            canon = img
        dh = dhash(canon)
        sid = state_id(dh)
        # buttons + loading tinh tren anh GOC (native client) -> toa do click
        # khop 1:1 voi client area, khong bi scale lech.
        loading = bool(is_loading(img))
        buttons: tuple[Button, ...] = ()
        if not loading:
            raw = detect_buttons(img)  # list (cx, cy, w, h, score)
            buttons = tuple(
                Button(x=int(cx), y=int(cy), w=int(bw), h=int(bh), score=float(sc))
                for (cx, cy, bw, bh, sc) in raw
            )
        return Observation(
            ts=ts, state_id=sid, loading=loading,
            size=Size(w, h), buttons=buttons, alive=True,
            resources=self._read_resources(img), dhash=dh,
        )

    def act(self, action: Action) -> ActionResult:
        try:
            self._dispatch(action)
        except Exception as e:  # noqa: BLE001
            return ActionResult(ok=False, error=f"{type(e).__name__}: {e}")
        # quan sat lai sau action
        obs = self.observe()
        return ActionResult(ok=True, observation=obs)

    def close(self) -> None:
        try:
            self._c.close()
        except Exception:  # noqa: BLE001
            pass

    # ---------- noi bo ----------
    def _dispatch(self, a: Action) -> None:
        k = a.kind
        if k is ActionKind.CLICK:
            self._c.bgclick(a.x, a.y)
        elif k is ActionKind.POLITE_CLICK:
            self._c.politeclick(a.x, a.y)
        elif k is ActionKind.FG_CLICK:
            self._c.fgclick(a.x, a.y)
        elif k is ActionKind.DRAG:
            self._c.bgdrag(a.x, a.y, a.x1, a.y1, a.steps or 14)
        elif k is ActionKind.KEY:
            # control server key command
            self._c._cmd(f"key {a.key}")
        elif k is ActionKind.WAIT:
            time.sleep((a.duration_ms or 0) / 1000.0)
        elif k is ActionKind.NOOP:
            pass
        else:
            raise ValueError(f"unknown action kind: {k}")

    def _read_resources(self, img) -> Resources:
        # OCR tai nguyen la tuy chon, khong fail observe neu loi
        try:
            from ocr import ocr_words  # noqa: F401
            # de don gian buoc dau: chua parse so, tra rong (se noi sau)
            return Resources()
        except Exception:  # noqa: BLE001
            return Resources()
