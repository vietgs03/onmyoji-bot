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

    def _locate(self) -> tuple[str | None, str | None, bool]:
        """Xac dinh (sid_xuat_phat, label, qua_dhash) hien tai.
        Thu dhash truoc (chinh xac, ghi-duoc edge), page sau (robust nhung sid la
        state CU -> KHONG ghi edge de tranh lam ban graph).
        qua_dhash=True neu xac dinh bang dhash (sid that), False neu page-fallback."""
        # tang 1: dhash (nhanh, sid CHINH XAC tu quan sat hien tai)
        obs = self._eye.observe_nav()
        sid = self._world.match_state(obs.dhash, obs.state_id) or obs.state_id
        label = self._world.resolve_label(sid)
        if label is not None:
            return sid, label, True
        # tang 2: page detector (landmark, robust voi man DONG) - chi khi dhash bi.
        # sid tra ve la state CU (state_for_label) -> chi de path_to, KHONG ghi edge.
        obs_pg = self._eye.observe_page()
        page_label = self._world.resolve_page(obs_pg.page)
        if page_label is not None:
            start = self._world.state_for_label(page_label) or sid
            return start, page_label, False
        return sid, None, True

    def execute(self, target_label: str) -> bool:
        for _ in range(self._max_steps):
            sid, label, via_dhash = self._locate()
            if label == target_label:
                return True
            path = self._world.path_to(sid, target_label)
            if not path:
                return False
            action = path[0]
            result = self._eye.act(action)
            if not result.ok:
                return False
            # CHI ghi edge khi xac dinh nguon bang dhash (sid that). Page-fallback
            # cho sid = state CU -> ghi edge se lam ban graph (edge tu state stale
            # toi state moi/khong ro). Bo qua record trong truong hop do.
            if via_dhash and result.observation:
                to_obs = result.observation
                to_sid = self._world.match_state(to_obs.dhash, to_obs.state_id)
                if to_sid is not None:  # chi ghi khi dich cung nhan dien duoc
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


# ============================================================================
# AUTONOMY use cases (4 tang). Xem AUTONOMY_DESIGN.md.
# ============================================================================

from onmyoji.domain.entities import (  # noqa: E402
    Outcome, Verdict, TaskSpec, TaskResult, Resources,
)


# Page label -> Outcome (data, KHONG hardcode flow). Mo rong bang add_live_page +
# them o day khi hoc them man ket qua. CHI map khi CHAC chan (verify vision).
_PAGE_OUTCOME = {
    "page_victory": Outcome.VICTORY,
    "page_defeat": Outcome.DEFEAT,
    "page_reward": Outcome.REWARD,
}


def _bitdiff(a: Optional[str], b: Optional[str]) -> int:
    """So bit khac giua 2 dhash (chuoi cung do dai). 999 neu khong so duoc.
    Dung do man ON DINH (battle xong) - khong import perception (giu domain sach)."""
    if not a or not b or len(a) != len(b):
        return 999
    return sum(1 for x, y in zip(a, b) if x != y)


class VerifyUseCase:
    """Tang 1: nhan dien KET QUA hien tai (thang/thua/loading/reward) de dong vong
    feedback. Uu tien page detector (landmark robust), fallback loading flag.
    KHONG hardcode toa do - dua page + trang thai."""

    def __init__(self, eye: EyePort, world: Optional[WorldModelPort] = None):
        self._eye = eye
        self._world = world

    def classify(self, obs: Optional[Observation] = None) -> Verdict:
        if obs is None:
            obs = self._eye.observe_page() if hasattr(self._eye, "observe_page") else self._eye.observe()
        res = obs.resources if obs.resources else Resources()
        if obs.loading:
            return Verdict(Outcome.LOADING, 0.9, "man loading/chuyen canh", res)
        # page-based (robust). page_score lam confidence.
        pg = obs.page
        if pg in _PAGE_OUTCOME:
            return Verdict(_PAGE_OUTCOME[pg], obs.page_score or 0.9,
                           f"page={pg}", res)
        # neu world resolve page -> label co chua 'victory'/'defeat' (self-learned)
        if self._world is not None and pg and hasattr(self._world, "resolve_page"):
            lbl = (self._world.resolve_page(pg) or "").lower()
            if "victory" in lbl or "win" in lbl:
                return Verdict(Outcome.VICTORY, 0.8, f"label={lbl}", res)
            if "defeat" in lbl or "lose" in lbl:
                return Verdict(Outcome.DEFEAT, 0.8, f"label={lbl}", res)
        return Verdict(Outcome.UNKNOWN, 0.0, f"page={pg}", res)

    def wait_outcome(self, accept: tuple[Outcome, ...],
                     max_wait_s: float = 90.0, poll_s: float = 1.5) -> Verdict:
        """Cho den khi classify ra 1 trong `accept` (vd VICTORY/DEFEAT) - dung cho
        battle tu chay. Tra Verdict cuoi (UNKNOWN neu het gio).

        Toi uu (review): trong battle man DONG (damage bay) -> chua het. Chi chay
        page detection (nang) khi man co dau hieu ON DINH (battle xong, man ket qua
        tinh). Dung observe_nav nhe de do on dinh truoc -> giam tai page detector."""
        deadline = time.time() + max_wait_s
        last = Verdict(Outcome.UNKNOWN, 0.0, "chua bat dau")
        prev_dh = None
        stable = 0
        has_nav = hasattr(self._eye, "observe_nav")
        while time.time() < deadline:
            # buoc 1: do on dinh bang observe_nav (nhe). Battle dang chay -> dhash
            # doi lien tuc -> chua can page detect.
            if has_nav:
                nav = self._eye.observe_nav()
                dh = nav.dhash
                if prev_dh is not None and dh and _bitdiff(dh, prev_dh) <= 2:
                    stable += 1
                else:
                    stable = 0
                prev_dh = dh
                # man chua on dinh (battle dang chay) -> doi tiep, KHONG page detect
                if stable < 1:
                    time.sleep(poll_s)
                    continue
            # buoc 2: man on dinh -> classify (page detect)
            v = self.classify()
            last = v
            if v.outcome in accept:
                return v
            time.sleep(poll_s)
        return last


class ResourcePolicy:
    """Tang 4: quyet dinh dua tai nguyen (gold/ap/jade da co trong Observation).
    Thuan logic, khong I/O. Cost lay tu TaskSpec.ap_cost (data)."""

    @staticmethod
    def can_afford(spec: TaskSpec, resources: Resources) -> bool:
        if spec.ap_cost <= 0:
            return True  # khong biet cost -> cho lam (battle se tu bao het ve)
        if resources is None or resources.ap is None:
            return True  # khong doc duoc AP -> khong chan (tranh dung oan)
        return resources.ap >= spec.ap_cost

    @staticmethod
    def should_stop(spec: TaskSpec, resources: Resources) -> Optional[Outcome]:
        if not ResourcePolicy.can_afford(spec, resources):
            return Outcome.NO_RESOURCE
        return None


class ExecuteTaskUseCase:
    """Tang 2: lam TRON 1 nhiem vu - dieu huong + lap + verify + dung dung luc.

    Moi buoc dua DU LIEU (world graph bfs_path + verified_elements + page), KHONG
    hardcode toa do. Phu thuoc tang 1 (VerifyUseCase) + tang 4 (ResourcePolicy)."""

    def __init__(self, eye: EyePort, world: WorldModelPort,
                 verify: VerifyUseCase, navigate, act,
                 settle=None):
        self._eye = eye
        self._world = world
        self._verify = verify
        self._navigate = navigate  # NavigateUseCase
        self._act = act            # ActUseCase
        self._settle = settle      # callable(eye)->(obs,ok) doi man on dinh (tuy chon)

    def _element_xy(self, screen: str, element: Optional[str]) -> Optional[tuple[int, int]]:
        """Tim toa do element (da verify) tren man screen. element=None -> chon nut
        hanh dong dau tien khong phai 'back'/'close'."""
        sid = self._world.state_for_label(screen) if hasattr(self._world, "state_for_label") else None
        if sid is None:
            return None
        els = self._world.elements_for(sid) if hasattr(self._world, "elements_for") else []
        if element:
            for e in els:
                if e.get("label") == element:
                    return (int(e["cx"]), int(e["cy"]))
            return None
        # tu suy: uu tien element ten 'Challenge'/'Enter'/'Search', tranh back/close
        skip = {"back", "close"}
        prefer = ("challenge", "enter", "search", "start")
        cand = [e for e in els if e.get("label", "").lower() not in skip]
        for e in cand:
            if e.get("label", "").lower() in prefer:
                return (int(e["cx"]), int(e["cy"]))
        return (int(cand[0]["cx"]), int(cand[0]["cy"])) if cand else None

    def _center(self) -> tuple[int, int]:
        """Tam man hinh HIEN TAI (theo Observation.size, KHONG hardcode). Dung de
        dismiss reward (tap giua khi khong biet nut). Fallback 568,320 (1136x640/2)."""
        try:
            obs = self._eye.observe_nav() if hasattr(self._eye, "observe_nav") else self._eye.observe()
            if obs.size and obs.size.w and obs.size.h:
                return (obs.size.w // 2, obs.size.h // 2)
        except Exception:  # noqa: BLE001
            pass
        return (568, 320)

    def _dismiss_until_screen(self, target_screen: str, taps: int = 4) -> bool:
        """Dismiss man ket qua/reward bang cach tap giua + cho ve target_screen.
        Hoc tu OAS (lap tap toi khi man muc tieu xuat hien) thay vi tap mu 1 lan.
        Tra True neu ve duoc target_screen."""
        cx, cy = self._center()
        for _ in range(taps):
            cur = self._eye.observe_page() if hasattr(self._eye, "observe_page") else self._eye.observe()
            # da ve target?
            if self._world is not None and cur.page and hasattr(self._world, "resolve_page"):
                if self._world.resolve_page(cur.page) == target_screen:
                    return True
            self._act.execute(Action.click(cx, cy))
            if self._settle:
                self._settle(self._eye)
        return False

    def execute(self, spec: TaskSpec) -> TaskResult:
        verdicts: list[Verdict] = []
        wins = losses = 0
        # 1) DIEU HUONG toi goal_screen (qua world graph)
        try:
            reached = self._navigate.execute(spec.goal_screen)
        except Exception as e:  # noqa: BLE001
            return TaskResult(False, spec.goal_screen, 0, spec.repeat,
                              f"loi dieu huong: {e}", ())
        if not reached:
            return TaskResult(False, spec.goal_screen, 0, spec.repeat,
                              "chua map duong toi man nay (can explore)", ())
        if spec.action == "navigate":
            return TaskResult(True, spec.goal_screen, 1, 1, "da toi man", ())

        # 2) LOOP repeat lan
        done = 0
        for i in range(spec.repeat):
            # 4) resource check (observe_nav - nhanh, chi can resources)
            obs = self._eye.observe_nav() if hasattr(self._eye, "observe_nav") else self._eye.observe()
            stop = ResourcePolicy.should_stop(spec, obs.resources)
            if stop is not None and stop in spec.stop_on:
                return TaskResult(True, spec.goal_screen, done, spec.repeat,
                                  "het tai nguyen (NO_RESOURCE)", tuple(verdicts), wins, losses)
            # tim nut hanh dong
            xy = self._element_xy(spec.goal_screen, spec.element)
            if xy is None:
                return TaskResult(False, spec.goal_screen, done, spec.repeat,
                                  f"chua hoc element '{spec.element or 'hanh dong'}' o {spec.goal_screen}",
                                  tuple(verdicts), wins, losses)
            # click vao -> co the qua pre-battle -> battle
            self._act.execute(Action.click(*xy))
            if self._settle:
                self._settle(self._eye)
            if spec.action == "collect":
                v = self._verify.classify()
                verdicts.append(v)
                done += 1
                if v.outcome in (Outcome.VICTORY, Outcome.REWARD):
                    wins += 1
                # dismiss reward -> ve goal_screen (lap, khong tap mu 1 lan)
                self._dismiss_until_screen(spec.goal_screen)
                continue
            # action == 'challenge': xu ly chuoi battle
            v = self._run_battle(spec)
            verdicts.append(v)
            if v.outcome in (Outcome.VICTORY, Outcome.REWARD):
                wins += 1
                done += 1
            elif v.outcome == Outcome.DEFEAT:
                losses += 1
                done += 1
            if v.outcome in spec.stop_on:
                return TaskResult(True, spec.goal_screen, done, spec.repeat,
                                  f"dung do gap {v.outcome.value}", tuple(verdicts), wins, losses)
            # ve lai goal_screen cho vong sau (navigate lai cho chac)
            if i < spec.repeat - 1:
                try:
                    self._navigate.execute(spec.goal_screen)
                except Exception:  # noqa: BLE001
                    break
        return TaskResult(True, spec.goal_screen, done, spec.repeat,
                          "hoan thanh", tuple(verdicts), wins, losses)

    def _run_battle(self, spec: TaskSpec) -> Verdict:
        """Xu ly chuoi pre-battle (Ready) -> in-battle (Auto/cho) -> ket qua.
        GENERIC (khong hardcode label man): dua page detector + element da hoc.
        Hoc tu OAS GeneralBattle: cho WIN/DEFEAT/REWARD roi dismiss bang cach
        lap tap toi khi ve man goal."""
        # 1) neu man hien tai la pre-battle (co element 'Ready') -> bam Ready.
        #    Khong gia dinh ten man - check element 'Ready' tren CHINH man hien tai.
        cur = self._eye.observe_page() if hasattr(self._eye, "observe_page") else self._eye.observe()
        cur_label = None
        if self._world is not None and cur.page and hasattr(self._world, "resolve_page"):
            cur_label = self._world.resolve_page(cur.page)
        if cur_label:
            ready = self._element_xy(cur_label, "Ready")
            if ready is not None:
                self._act.execute(Action.click(*ready))
                if self._settle:
                    self._settle(self._eye)
                # sau Ready -> man battle moi, cap nhat label
                cur = self._eye.observe_page() if hasattr(self._eye, "observe_page") else self._eye.observe()
                cur_label = (self._world.resolve_page(cur.page)
                             if self._world and cur.page and hasattr(self._world, "resolve_page") else None)
        # 2) bat Auto neu man battle co element Auto (tran tu chay)
        if cur_label:
            auto = self._element_xy(cur_label, "Auto")
            if auto is not None:
                self._act.execute(Action.click(*auto))
        # 3) cho ket qua (page victory/defeat/reward)
        v = self._verify.wait_outcome(
            accept=(Outcome.VICTORY, Outcome.DEFEAT, Outcome.REWARD),
            max_wait_s=spec.max_steps * 2.0, poll_s=1.5)
        # 4) dismiss man ket qua -> ve goal_screen (lap tap, khong tap mu)
        if v.outcome in (Outcome.VICTORY, Outcome.DEFEAT, Outcome.REWARD):
            self._dismiss_until_screen(spec.goal_screen, taps=5)
        return v


class PlanDailyUseCase:
    """Tang 3: tu daily_plan.json (data) + trang thai -> sinh chuoi TaskSpec hop ly.
    Loc: chi giu man DA MAP (co duong tu HOME) + sap theo priority."""

    def __init__(self, world: Optional[WorldModelPort], plan_path: str):
        self._world = world
        self._plan_path = plan_path

    def plan(self, from_screen: str = "HOME") -> list[TaskSpec]:
        import json
        import os
        if not os.path.exists(self._plan_path):
            return []
        try:
            raw = json.load(open(self._plan_path, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return []
        items = [r for r in raw if isinstance(r, dict) and not str(r.get("screen", "")).startswith("_")]
        # sap theo priority (nho = uu tien)
        items.sort(key=lambda r: r.get("priority", 99))
        specs: list[TaskSpec] = []
        for r in items:
            screen = r.get("screen")
            if not screen:
                continue
            # loc: chi giu man da map (co the dieu huong toi)
            if self._world is not None and hasattr(self._world, "path_to"):
                if self._world.state_for_label(screen) is None:
                    continue  # chua hoc man nay -> bo qua (explore truoc)
            specs.append(TaskSpec(
                goal_screen=screen,
                action=r.get("action", "challenge"),
                element=r.get("element"),
                repeat=int(r.get("repeat", 1)),
                stop_on=tuple(Outcome(o) for o in r.get("stop_on", ["no_resource"])),
                ap_cost=int(r.get("ap_cost", 0)),
            ))
        return specs
