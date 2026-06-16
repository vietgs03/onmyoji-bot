"""onmyoji.adapters.eye_py.fake_game - FakeGame: state machine mo phong game that.

KHAC FakeEye (tinh): FakeGame mo phong LUONG game - click element -> chuyen man,
co battle (pre->in->victory), co loading frame, tru AP. Dung de test do_task/
run_daily END-TO-END khong can game that -> verify MO HINH chay dung truoc khi
game mo (xem RUNTIME_MODEL.md).

Thiet ke: dinh nghia man (screen) + transition (click element -> man dich) nhu 1
world thu nho. observe() tra Observation theo current screen (co page de
canonical_state/verify neo). act(click) di chuyen theo transition.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from onmyoji.domain.entities import (
    Observation, Action, ActionResult, ActionKind, Size, Resources,
)
from onmyoji.domain.ports import EyePort


@dataclass
class FakeScreen:
    """1 man trong FakeGame. page = landmark gia (de verify/canonical_state neo).
    elements: {(cx,cy): dst_screen} - click gan toa do nay -> chuyen toi dst.
    loading_frames: so lan observe dau tra loading=True (mo phong chuyen canh)."""
    name: str
    page: Optional[str] = None
    elements: dict = field(default_factory=dict)  # (cx,cy) -> dst screen name
    loading_frames: int = 0


class FakeGame(EyePort):
    """Game gia lap (state machine). Cam vao Container thay FakeEye de test autonomy.

    Vi du dinh nghia (mo phong nhanh Soul):
      HOME --click Explore--> Explore --click Soul--> Soul --Challenge--> SoulBattle
      SoulBattle --Challenge--> SoulPreBattle --Ready--> SoulInBattle --(tu)--> Victory --> SoulBattle
    """

    CLICK_TOL = 40  # click trong ban kinh nay coi la trung element

    def __init__(self, screens: dict[str, FakeScreen], start: str = "HOME",
                 ap: int = 100, ap_cost_battle: int = 6,
                 battle_loading: int = 2, auto_win: bool = True):
        self._screens = screens
        self._cur = start
        self._ap = ap
        self._ap_cost = ap_cost_battle
        self._battle_loading = battle_loading
        self._auto_win = auto_win
        self.actions_log: list[Action] = []
        self._loading_left = 0          # so frame loading con lai cho man hien tai
        self._battle_phase = None       # None | 'in_battle' (dem frame toi victory)
        self._battle_frames = 0
        self._dhash_tick = 0            # de mo phong dhash doi moi frame (man dong)

    # ---- helpers ----
    def _screen(self) -> FakeScreen:
        return self._screens[self._cur]

    def _goto(self, name: str):
        self._cur = name
        self._loading_left = self._screens[name].loading_frames

    def _fake_dhash(self) -> str:
        """dhash gia: on dinh theo man (de canonical_state khop) NHUNG doi nhe khi
        loading/battle (man dong). 64 ky tu '0'/'1'."""
        base = abs(hash(self._cur)) % (2 ** 32)
        # man dong (loading/battle) -> them nhieu theo tick
        if self._loading_left > 0 or self._battle_phase:
            base ^= (self._dhash_tick * 0x9E3779B1) & 0xFFFFFFFF
        bits = format(base, "032b")
        return (bits + bits)[:64]

    # ---- EyePort ----
    def observe(self) -> Observation:
        self._dhash_tick += 1
        sc = self._screen()
        loading = self._loading_left > 0
        if loading:
            self._loading_left -= 1
        # battle: sau battle_loading frame -> victory
        page = sc.page
        if self._battle_phase == "in_battle":
            self._battle_frames += 1
            if self._battle_frames >= self._battle_loading:
                # battle xong -> man ket qua
                page = "page_victory" if self._auto_win else "page_defeat"
                self._cur = "_RESULT"
                self._battle_phase = None
            else:
                loading = False  # battle khong phai loading, nhung man DONG
                page = None      # dang danh -> chua co page ket qua
        return Observation(
            ts=time.time(), state_id=self._cur, loading=loading,
            size=Size(1136, 640), buttons=(), alive=True,
            resources=Resources(ap=self._ap),
            dhash=self._fake_dhash(), page=page,
            page_score=0.95 if page else None,
        )

    def observe_nav(self) -> Observation:
        return self.observe()

    def observe_page(self) -> Observation:
        return self.observe()

    def observe_som(self, with_page: bool = False) -> Observation:
        return self.observe()

    def act(self, action: Action) -> ActionResult:
        self.actions_log.append(action)
        if action.kind in (ActionKind.CLICK, ActionKind.POLITE_CLICK, ActionKind.FG_CLICK):
            self._handle_click(action.x or 0, action.y or 0)
        return ActionResult(ok=True, observation=self.observe())

    def _handle_click(self, x: int, y: int):
        # man ket qua: click bat ky -> ve man goc battle (mo phong dismiss)
        if self._cur == "_RESULT":
            self._goto(getattr(self, "_battle_home", "SoulBattle"))
            return
        sc = self._screen()
        # tim element gan (x,y)
        for (ex, ey), dst in sc.elements.items():
            if abs(ex - x) <= self.CLICK_TOL and abs(ey - y) <= self.CLICK_TOL:
                if dst == "_BATTLE":
                    # bat dau battle: tru AP, vao in_battle (sau Ready)
                    self._battle_home = self._cur
                    self._ap = max(0, self._ap - self._ap_cost)
                    self._battle_phase = "in_battle"
                    self._battle_frames = 0
                else:
                    self._goto(dst)
                return
        # click khong trung gi -> khong doi man (mo phong tap vao cho trong)

    def close(self) -> None:
        pass


def demo_soul_world() -> tuple[dict, dict]:
    """Tra (screens cho FakeGame, world_def cho WorldModel gia) mo phong nhanh Soul.
    Dung trong test: HOME -> Explore -> Soul -> SoulBattle -> (battle) -> Victory."""
    screens = {
        "HOME": FakeScreen("HOME", page="page_main",
                           elements={(600, 190): "Explore"}),
        "Explore": FakeScreen("Explore", page="page_exploration_live",
                              elements={(168, 590): "Soul"}, loading_frames=1),
        "Soul": FakeScreen("Soul", page="page_soul_zones",
                           elements={(159, 230): "SoulBattle"}, loading_frames=1),
        "SoulBattle": FakeScreen("SoulBattle", page=None,
                                 elements={(1050, 550): "_BATTLE"}),
        "_RESULT": FakeScreen("_RESULT", page="page_victory"),
    }
    return screens
