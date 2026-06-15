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


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"\n=== Chay {len(tests)} test kien truc Clean Architecture ===")
    for t in tests:
        t()
    print(f"=== TAT CA {len(tests)} TEST PASS ===\n")


if __name__ == "__main__":
    run_all()
