"""Test tich hop RustEye <-> onmyoji-eye (binary Rust) qua socket that.

Khong can game: dung backend --file cua onmyoji-eye (doc 1 PNG that). Chung minh
ca chuoi swap hoat dong: EyePort (Python) -> socket NDJSON -> perception Rust.

Bo qua (skip) neu chua build binary (cd eye-rs && cargo build --release).

Chay: .venv/bin/python tests_arch/test_rust_eye_e2e.py
"""
import json
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from onmyoji.adapters.eye_rs.rust_eye import RustEye
from onmyoji.application.use_cases import PerceiveUseCase
from onmyoji.domain.entities import Action

BIN = os.path.join(ROOT, "eye-rs", "target", "release", "onmyoji-eye")
ADDR = "127.0.0.1:8811"


def _pick_frame() -> str:
    """Chon 1 PNG full-screen that tu goldens (frame de test)."""
    gp = os.path.join(ROOT, "eye-rs", "tests", "goldens", "perception_goldens_full.json")
    g = json.load(open(gp))
    # lay anh nhieu button nhat (kiem tra ca detect)
    name, v = max(g.items(), key=lambda kv: len(kv[1]["buttons"]))
    return os.path.join(ROOT, v["path"])


def _wait_port(host: str, port: int, timeout: float = 6.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            socket.create_connection((host, port), timeout=0.5).close()
            return True
        except OSError:
            time.sleep(0.15)
    return False


def main() -> int:
    if not os.path.exists(BIN):
        print(f"SKIP: chua build binary {BIN} (cd eye-rs && cargo build --release)")
        return 0

    frame = _pick_frame()
    print(f"frame test: {os.path.relpath(frame, ROOT)}")

    srv = subprocess.Popen(
        [BIN, "serve", ADDR, "--file", frame],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    host, port = ADDR.split(":")
    fails: list[str] = []
    try:
        if not _wait_port(host, int(port)):
            print("FAIL: server khong mo port")
            return 1

        os.environ["ONMYOJI_EYE_ADDR"] = ADDR
        os.environ["ONMYOJI_EYE_SPAWN"] = "0"
        eye = RustEye()

        # 1) observe tra Observation hop le
        obs = eye.observe()
        checks = [
            (obs.alive, "obs.alive == True"),
            (not obs.loading, "obs.loading == False (frame that)"),
            (obs.size.w == 1152 and obs.size.h == 679, "size 1152x679"),
            (len(obs.dhash or "") == 64, "dhash dai 64"),
            (len(obs.state_id) == 10, "state_id dai 10"),
            (len(obs.buttons) > 10, f"detect nhieu button ({len(obs.buttons)})"),
        ]
        b0 = obs.buttons[0]
        checks.append((b0.w > 0 and b0.h > 0 and b0.score > 0, "button[0] hop le"))

        # 2) act qua socket -> ActionResult ok
        res = eye.act(Action.click(b0.x, b0.y))
        checks.append((res.ok, "act(click) ok"))
        checks.append((res.observation is not None, "act tra observation moi"))

        # 3) chay qua use case (tang application khong biet Rust)
        ctx = PerceiveUseCase(eye, None).execute()
        checks.append((ctx.observation.state_id == obs.state_id,
                       "PerceiveUseCase dung RustEye nhat quan"))

        for ok, msg in checks:
            print(f"  [{'ok ' if ok else 'FAIL'}] {msg}")
            if not ok:
                fails.append(msg)

        eye.close()
    finally:
        try:
            socket.create_connection((host, int(port)), timeout=1).sendall(
                b'{"op":"shutdown"}\n'
            )
        except OSError:
            pass
        try:
            srv.wait(timeout=3)
        except subprocess.TimeoutExpired:
            srv.kill()

    if fails:
        print(f"\nRESULT: FAIL ({len(fails)} check)")
        return 1
    print("\nRESULT: PASS (RustEye <-> onmyoji-eye E2E qua socket)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
