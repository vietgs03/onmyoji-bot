"""onmyoji.adapters.eye_rs - RustEye: implement EyePort qua socket toi onmyoji-eye.

Day la doi tac Python cua binary Rust `onmyoji-eye` (eye-rs/). Thay vi chay cv2
trong Python (PythonEye), RustEye chi:
  - mo socket TCP toi onmyoji-eye (NDJSON, theo contracts/schema.json),
  - gui {op: observe|act|...} -> nhan Observation/ActionResult da phan tich san.

Perception (dhash/detect_buttons) chay BANG RUST -> nhanh hon, on dinh hon.
Swap = chi doi ONMYOJI_EYE=rust trong container, KHONG dau khac.

Ket noi:
  - ONMYOJI_EYE_ADDR=host:port  (mac dinh 127.0.0.1:8765)
  - Neu server chua chay va ONMYOJI_EYE_SPAWN=1: tu spawn onmyoji-eye --ps.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from typing import Optional

from onmyoji.domain.entities import (
    Observation, Action, ActionResult, Button, Mark, Resources, Size,
)
from onmyoji.domain.ports import EyePort

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# binary release sau khi `cargo build --release` trong eye-rs/
_DEFAULT_BIN = os.path.join(_ROOT, "eye-rs", "target", "release", "onmyoji-eye")
_DEFAULT_ADDR = "127.0.0.1:8765"


class RustEyeError(RuntimeError):
    """Loi giao tiep voi onmyoji-eye (socket/giao thuc)."""


class RustEye(EyePort):
    """EyePort noi chuyen voi onmyoji-eye qua socket NDJSON.

    Cung 1 contract (schema.json) nhu PythonEye -> tang application khong phan biet.
    """

    def __init__(self, addr: Optional[str] = None, *, spawn: Optional[bool] = None,
                 binary: Optional[str] = None, connect_timeout: float = 30.0):
        # connect_timeout 30s: khi spawn=1, `serve --ps` phai khoi dong PowerShell
        # (PsBridge) + cho ".NET/NeoX JIT warmup ~11s lan dau lanh" TRUOC khi bind
        # port -> 8s cu khong du, gay timeout gia. 30s du an toan; co the chinh qua
        # ONMYOJI_EYE_CONNECT_TIMEOUT.
        self._addr = addr or os.environ.get("ONMYOJI_EYE_ADDR", _DEFAULT_ADDR)
        self._host, _, port = self._addr.partition(":")
        self._port = int(port or "8765")
        self._binary = binary or os.environ.get("ONMYOJI_EYE_BIN", _DEFAULT_BIN)
        if spawn is None:
            spawn = os.environ.get("ONMYOJI_EYE_SPAWN", "0") == "1"
        self._spawn = spawn
        # cho phep chinh timeout qua env (vd may cham can lau hon)
        env_to = os.environ.get("ONMYOJI_EYE_CONNECT_TIMEOUT")
        if env_to:
            try:
                connect_timeout = float(env_to)
            except ValueError:
                pass
        self._proc: Optional[subprocess.Popen] = None
        self._sock: Optional[socket.socket] = None
        self._f = None  # file-like cho readline
        self._connect(connect_timeout)

    # ---------- ket noi ----------
    def _connect(self, timeout: float) -> None:
        deadline = time.time() + timeout
        last_err: Optional[Exception] = None
        # thu noi truoc (co the server da chay san)
        while time.time() < deadline:
            try:
                self._open_socket()
                return
            except OSError as e:
                last_err = e
                # chua co server: thu spawn 1 lan
                if self._spawn and self._proc is None:
                    self._spawn_server()
                time.sleep(0.3)
        raise RustEyeError(
            f"khong ket noi duoc onmyoji-eye tai {self._addr}: {last_err}"
        )

    def _open_socket(self) -> None:
        s = socket.create_connection((self._host, self._port), timeout=10.0)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = s
        self._f = s.makefile("rwb", buffering=0)

    def _spawn_server(self) -> None:
        if not os.path.exists(self._binary):
            raise RustEyeError(
                f"khong thay binary onmyoji-eye: {self._binary} "
                f"(chay: cd eye-rs && cargo build --release)"
            )
        # --ps: dung server PowerShell that (game that tren WSL)
        self._proc = subprocess.Popen(
            [self._binary, "serve", self._addr, "--ps"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    # ---------- giao thuc NDJSON ----------
    def _rpc(self, req: dict) -> dict:
        if self._f is None:
            raise RustEyeError("socket chua mo")
        try:
            self._f.write((json.dumps(req) + "\n").encode("utf-8"))
            line = self._f.readline()
        except OSError as e:
            raise RustEyeError(f"loi socket: {e}") from e
        if not line:
            raise RustEyeError("server dong ket noi (EOF)")
        try:
            return json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise RustEyeError(f"response khong phai JSON: {line!r}") from e

    @staticmethod
    def _obs_from_resp(d: dict) -> Observation:
        o = d.get("observation") or {}
        sz = o.get("size") or {"w": 0, "h": 0}
        return Observation(
            ts=o.get("ts", time.time()),
            state_id=o.get("state_id", "DEAD"),
            loading=bool(o.get("loading", False)),
            size=Size(int(sz["w"]), int(sz["h"])),
            buttons=tuple(
                Button(x=b["x"], y=b["y"], w=b["w"], h=b["h"],
                       score=float(b.get("score", 0.0)), text=b.get("text"))
                for b in o.get("buttons", [])
            ),
            alive=bool(o.get("alive", True)),
            resources=Resources(**(o.get("resources") or {})),
            frame_path=o.get("frame_path"),
            dhash=o.get("dhash"),
            page=o.get("page"),
            page_score=o.get("page_score"),
            marks=tuple(
                Mark(id=m["id"], cx=m["cx"], cy=m["cy"], x=m["x"], y=m["y"],
                     w=m["w"], h=m["h"], score=float(m.get("score", 0.0)))
                for m in o.get("marks", [])
            ),
            marked_path=o.get("marked_path"),
        )

    # ---------- EyePort ----------
    def observe(self) -> Observation:
        resp = self._rpc({"op": "observe"})
        if not resp.get("ok", False) and "observation" not in resp:
            raise RustEyeError(resp.get("error") or "observe that bai")
        return self._obs_from_resp(resp)

    def observe_nav(self) -> Observation:
        # Tier nav: bao Rust BO detect_buttons (~9x nhanh). Chi state_id/loading.
        resp = self._rpc({"op": "observe", "with_buttons": False})
        if not resp.get("ok", False) and "observation" not in resp:
            raise RustEyeError(resp.get("error") or "observe_nav that bai")
        return self._obs_from_resp(resp)

    def observe_page(self) -> Observation:
        """Observe co PAGE detection (landmark template match, ~300ms - CHI khi
        can xac dinh man/dieu huong). Tra Observation co .page/.page_score.
        Robust hon dhash voi man DONG/3D."""
        resp = self._rpc({"op": "observe", "with_buttons": False, "with_page": True})
        if not resp.get("ok", False) and "observation" not in resp:
            raise RustEyeError(resp.get("error") or "observe_page that bai")
        return self._obs_from_resp(resp)

    def observe_som(self, with_page: bool = False) -> Observation:
        """Observe cho LLM AGENT VISION: tao Set-of-Mark (danh so element + luu
        anh marked). Tra Observation co .marks (so->toa do) + .marked_path (anh
        da danh so de agent NHIN). Agent chon SO -> click_mark dung toa do.
        marks = UNG VIEN (CV co the sot/rac) -> agent VERIFY tren anh goc."""
        req = {"op": "observe", "with_som": True}
        if with_page:
            req["with_page"] = True
        resp = self._rpc(req)
        if not resp.get("ok", False) and "observation" not in resp:
            raise RustEyeError(resp.get("error") or "observe_som that bai")
        return self._obs_from_resp(resp)

    def snap(self, x: int, y: int, radius: int = 40) -> tuple[int, int, bool]:
        """SNAP toa do tho (x,y) ve tam element gan nhat (cho click chinh xac khi
        CV sot element). Tra (sx, sy, snapped). snapped=False -> giu nguyen (x,y)
        (khong co element gan -> agent van click cho do)."""
        resp = self._rpc({"op": "snap", "x": int(x), "y": int(y), "radius": int(radius)})
        s = resp.get("snap") or {}
        if not s:
            return (int(x), int(y), False)
        return (int(s.get("x", x)), int(s.get("y", y)), bool(s.get("snapped", False)))

    def probe(self, amp: int = 200) -> dict:
        """PROBE kha nang di chuyen man: drag thu ngang+doc tu giua man, do shift,
        roi tu keo VE (khong lam xe dich). Tra dict {movable, can_x, can_y, dx,
        dy, ...}. Cho agent biet man co scroll/keo duoc khong (ban do exploration,
        list menu Shop/Souls) de kham pha het content - cach SENIOR thay vi doan.
        amp = bien do keo thu (px). Dung truong 'radius' trong protocol."""
        resp = self._rpc({"op": "probe", "radius": int(amp)})
        return resp.get("probe") or {}

    def act(self, action: Action) -> ActionResult:
        resp = self._rpc({"op": "act", "action": action.to_dict()})
        result = resp.get("result") or {}
        obs = None
        if result.get("observation"):
            obs = self._obs_from_resp({"observation": result["observation"]})
        return ActionResult(
            ok=bool(result.get("ok", resp.get("ok", False))),
            error=result.get("error") or resp.get("error"),
            observation=obs,
        )

    def close(self) -> None:
        # neu ta spawn server, bao no shutdown
        try:
            if self._f is not None and self._proc is not None:
                self._rpc({"op": "shutdown"})
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._f is not None:
                self._f.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._sock is not None:
                self._sock.close()
        except Exception:  # noqa: BLE001
            pass
        if self._proc is not None:
            try:
                self._proc.wait(timeout=3)
            except Exception:  # noqa: BLE001
                self._proc.kill()
