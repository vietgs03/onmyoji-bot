"""onmyoji.application.use_cases - Use case (tang ung dung) cho Clean Architecture.

Logic dieu phoi NGHIEP VU. CHI phu thuoc Ports (interface), KHONG biet cv2/socket.
Day la API ma harness agent (jcode) va CLI/MCP se goi.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from onmyoji.domain.entities import Observation, Action
from onmyoji.domain.ports import EyePort, WorldModelPort, KnowledgePort


@dataclass
class GameContext:
    """Trang thai hien tai bot 'hieu' ve game."""
    observation: Observation
    label: Optional[str] = None


class PerceiveUseCase:
    """Chup + hieu man hinh hien tai."""

    def __init__(self, eye: EyePort, world: Optional[WorldModelPort] = None):
        self._eye = eye
        self._world = world

    def execute(self) -> GameContext:
        obs = self._eye.observe()
        label = None
        if self._world:
            # khop MO theo dhash -> sid chuan (chiu duoc lech bit Rust/Python)
            sid = self._world.match_state(obs.dhash, obs.state_id)
            label = self._world.resolve_label(sid) if sid else None
        return GameContext(observation=obs, label=label)


class WaitStableUseCase:
    """Doi man hinh on dinh (het loading + du button) truoc khi doc/click."""

    def __init__(self, eye: EyePort, min_buttons: int = 2,
                 max_wait_s: float = 12.0, poll_s: float = 0.6):
        self._eye = eye
        self._min_buttons = min_buttons
        self._max_wait = max_wait_s
        self._poll = poll_s

    def execute(self) -> Observation:
        deadline = time.time() + self._max_wait
        last = self._eye.observe()
        while time.time() < deadline:
            obs = self._eye.observe()
            last = obs
            if obs.alive and not obs.loading and len(obs.buttons) >= self._min_buttons:
                return obs
            time.sleep(self._poll)
        return last


class NavigateUseCase:
    """Di toi man hinh co label dich, theo path da hoc trong WorldModel.

    Xac dinh vi tri hien tai theo 2 tang (robust):
      1. dhash match (nhanh, nhung fail tren man DONG/3D - shikigami dong v.v.)
      2. neu dhash khong ra label -> page detector (landmark template match,
         robust hon) -> map page->label. Day la fix diem yeu dhash.
    """

    def __init__(self, eye: EyePort, world: WorldModelPort, max_steps: int = 8):
        self._eye = eye
        self._world = world
        self._max_steps = max_steps

    def _locate(self) -> tuple[str | None, str | None]:
        """Xac dinh (sid_xuat_phat, label) hien tai. Thu dhash truoc, page sau.
        sid dung cho path_to; label de kiem da toi dich chua."""
        # tang 1: dhash (nhanh)
        obs = self._eye.observe_nav()
        sid = self._world.match_state(obs.dhash, obs.state_id) or obs.state_id
        label = self._world.resolve_label(sid)
        if label is not None:
            return sid, label
        # tang 2: page detector (landmark, robust voi man DONG) - chi khi dhash bi
        obs_pg = self._eye.observe_page()
        page_label = self._world.resolve_page(obs_pg.page)
        if page_label is not None:
            # diem xuat phat cho path_to = 1 state da luu co label nay
            start = self._world.state_for_label(page_label) or sid
            return start, page_label
        return sid, None

    def execute(self, target_label: str) -> bool:
        for _ in range(self._max_steps):
            sid, label = self._locate()
            if label == target_label:
                return True
            path = self._world.path_to(sid, target_label)
            if not path:
                return False
            action = path[0]
            result = self._eye.act(action)
            if not result.ok:
                return False
            if result.observation:
                to_obs = result.observation
                to_sid = self._world.match_state(to_obs.dhash, to_obs.state_id) or to_obs.state_id
                self._world.record_transition(sid, action, to_sid)
        return False


class AskKnowledgeUseCase:
    """Tra cuu tri thuc game (KB/vector)."""

    def __init__(self, knowledge: KnowledgePort):
        self._kb = knowledge

    def execute(self, query: str, k: int = 5) -> list[dict]:
        return self._kb.ask(query, k=k)


class ActUseCase:
    """Thuc thi 1 action tho (click/drag/key) + tra observation moi."""

    def __init__(self, eye: EyePort):
        self._eye = eye

    def execute(self, action: Action) -> Observation:
        result = self._eye.act(action)
        if not result.ok:
            raise RuntimeError(result.error or "action failed")
        return result.observation or self._eye.observe()
