"""Test kien truc Clean Architecture - KHONG can game/Windows.

Chay: .venv/bin/python -m pytest tests_arch/ -v
Hoac: .venv/bin/python tests_arch/test_architecture.py
"""
import os
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from onmyoji.domain.entities import (
    Observation, Action, ActionKind, ActionResult, Button, Resources, Size,
)
from onmyoji.application.use_cases import (
    PerceiveUseCase, WaitStableUseCase, NavigateUseCase, ActUseCase,
)
from onmyoji.adapters.eye_py.fake_eye import FakeEye


def test_observation_roundtrip():
    obs = Observation(
        ts=123.4, state_id="HOME", loading=False, size=Size(1152, 679),
        buttons=(Button(10, 20, 30, 40, 0.8, "Explore"),),
        alive=True, resources=Resources(gold=500, ap=80),
    )
    d = obs.to_dict()
    obs2 = Observation.from_dict(d)
    assert obs2 == obs
    # serialize JSON that
    s = json.dumps(d)
    assert Observation.from_dict(json.loads(s)) == obs
    print("  [ok] Observation roundtrip qua JSON")


def test_action_roundtrip():
    for a in [
        Action.click(5, 6),
        Action.polite_click(7, 8),
        Action.drag(0, 0, 100, 100, steps=10),
        Action.key_press("ESC"),
        Action.wait(500),
    ]:
        a2 = Action.from_dict(json.loads(json.dumps(a.to_dict())))
        assert a2 == a
    print("  [ok] Action roundtrip qua JSON (5 loai)")


def test_contract_matches_schema():
    """Entity to_dict() phai khop key voi contracts/schema.json."""
    schema = json.load(open(os.path.join(ROOT, "contracts", "schema.json")))
    obs_props = set(schema["definitions"]["Observation"]["properties"])
    obs = Observation(ts=1, state_id="x", loading=False, size=Size(1, 1))
    assert set(obs.to_dict()).issubset(obs_props), "Observation co key ngoai schema"
    act_props = set(schema["definitions"]["Action"]["properties"])
    assert set(Action.click(1, 2).to_dict()).issubset(act_props), "Action ngoai schema"
    print("  [ok] Entities khop contracts/schema.json")


def test_perceive_usecase_with_fake_eye():
    eye = FakeEye(state_id="HOME")
    ctx = PerceiveUseCase(eye).execute()
    assert ctx.observation.state_id == "HOME"
    assert ctx.observation.alive
    print("  [ok] PerceiveUseCase chay voi FakeEye")


def test_act_usecase_logs_action():
    eye = FakeEye()
    ActUseCase(eye).execute(Action.click(50, 60))
    assert len(eye.actions_log) == 1
    assert eye.actions_log[0].kind is ActionKind.CLICK
    print("  [ok] ActUseCase thuc thi + log action")


def test_navigate_usecase_with_stub_world():
    """NavigateUseCase chi biet Port -> dung world gia lap."""
    from onmyoji.domain.ports import WorldModelPort

    class StubWorld(WorldModelPort):
        def __init__(self):
            self.transitions = []
        def resolve_label(self, sid):
            return {"HOME": "HOME", "SHOP_SCREEN": "SHOP"}.get(sid)
        def path_to(self, frm, to_label):
            if to_label == "SHOP":
                return [Action.click(200, 50)]
            return None
        def record_transition(self, frm, action, to):
            self.transitions.append((frm, action.kind.value, to))

    eye = FakeEye(state_id="HOME")
    world = StubWorld()
    # khi click, eye chuyen sang SHOP_SCREEN
    orig_act = eye.act
    def act_then_move(a):
        r = orig_act(a)
        eye.set_state("SHOP_SCREEN")
        return r
    eye.act = act_then_move

    ok = NavigateUseCase(eye, world).execute("SHOP")
    assert ok, "phai navigate toi SHOP thanh cong"
    assert len(world.transitions) == 1
    print("  [ok] NavigateUseCase di HOME->SHOP qua Port (swap-able)")


def test_match_state_fuzzy_dhash():
    """Rust EYE cho dhash lech vai bit -> state_id md5 KHAC HAN. match_state phai
    khop MO theo dhash (hamming<=12) -> tra dung sid Python da luu.

    Day la cau noi song con cho viec swap EYE sang Rust: neu chi so khop state_id
    chinh xac, moi frame Rust se 'lac' state du man hinh y het."""
    import hashlib
    from onmyoji.adapters.world.world_model_adapter import WorldModelAdapter

    py_dh = "0101010010101010011001011001111010100110010110100100101011010011"
    py_sid = hashlib.md5(py_dh.encode()).hexdigest()[:10]

    class _WM:  # world toi thieu cho adapter (khong dung WorldModel that)
        def __init__(self):
            self.states = {py_sid: {"dhash": py_dh, "label": "HOME"}}

    adapter = WorldModelAdapter(world=_WM())

    # Rust: lech 1 bit -> sid khac han
    rust_dh = "0101010000101010011001011001111010100110010110100100101011010011"
    rust_sid = hashlib.md5(rust_dh.encode()).hexdigest()[:10]
    assert rust_sid != py_sid, "md5 phai khuech dai 1 bit thanh sid khac"

    # khop chinh xac theo sid Rust -> truot
    assert adapter.resolve_label(rust_sid) is None
    # khop mo theo dhash -> ra dung sid Python
    matched = adapter.match_state(rust_dh, rust_sid)
    assert matched == py_sid, "match_state phai khop mo ve sid Python"
    assert adapter.resolve_label(matched) == "HOME"
    # khong co dhash -> chi khop chinh xac (giu hanh vi cu, an toan)
    assert adapter.match_state(None, rust_sid) is None
    assert adapter.match_state(None, py_sid) == py_sid
    print("  [ok] match_state khop mo dhash (Rust lech bit van resolve dung state)")


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"\n=== Chay {len(tests)} test kien truc Clean Architecture ===")
    for t in tests:
        t()
    print(f"=== TAT CA {len(tests)} TEST PASS ===\n")


if __name__ == "__main__":
    run_all()
