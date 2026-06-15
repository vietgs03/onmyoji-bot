"""onmyoji.adapters.eye_py.fake_eye - FakeEye cho test/dev KHONG can game.

Cho phep test toan bo use case + harness ma khong can Windows/game chay.
Tra ve observation/action gia lap theo kich ban dat truoc.
"""
from __future__ import annotations

import time
from typing import Optional

from onmyoji.domain.entities import (
    Observation, Action, ActionResult, Button, Size,
)
from onmyoji.domain.ports import EyePort


class FakeEye(EyePort):
    """Eye gia lap: tra observation theo 'scripted' state, ghi lai action."""

    def __init__(self, state_id: str = "HOME", buttons: Optional[list[Button]] = None):
        self._state = state_id
        self._buttons = tuple(buttons or [Button(100, 100, 40, 40, 0.9, "Explore")])
        self.actions_log: list[Action] = []

    def set_state(self, state_id: str, buttons: Optional[list[Button]] = None) -> None:
        self._state = state_id
        if buttons is not None:
            self._buttons = tuple(buttons)

    def observe(self) -> Observation:
        return Observation(
            ts=time.time(), state_id=self._state, loading=False,
            size=Size(1152, 679), buttons=self._buttons, alive=True,
        )

    def act(self, action: Action) -> ActionResult:
        self.actions_log.append(action)
        return ActionResult(ok=True, observation=self.observe())

    def close(self) -> None:
        pass
