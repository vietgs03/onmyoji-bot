"""onmyoji.domain.entities - Entities thuan (Clean Architecture - tang trong cung).

KHONG import I/O, cv2, socket, framework. Chi dataclass + logic thuan.
Khop 1-1 voi contracts/schema.json. Day la "ngon ngu chung" giua moi tang.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


@dataclass(frozen=True, slots=True)
class Button:
    x: int
    y: int
    w: int
    h: int
    score: float
    text: Optional[str] = None

    @property
    def center(self) -> tuple[int, int]:
        return (self.x, self.y)


@dataclass(frozen=True, slots=True)
class Resources:
    gold: Optional[int] = None
    ap: Optional[int] = None
    jade: Optional[int] = None


@dataclass(frozen=True, slots=True)
class Mark:
    """1 Set-of-Mark element cho LLM agent vision: id + tam (toa do click) + bbox.
    Agent chon SO trong anh marked -> click theo (cx,cy). marks = UNG VIEN (CV co
    the sot/rac) -> agent VERIFY tren anh goc."""
    id: int
    cx: int
    cy: int
    x: int
    y: int
    w: int
    h: int
    score: float

    @property
    def center(self) -> tuple[int, int]:
        return (self.cx, self.cy)


@dataclass(frozen=True, slots=True)
class Size:
    w: int
    h: int


@dataclass(frozen=True, slots=True)
class Observation:
    """EYE -> BRAIN: mot quan sat. KHONG chua anh raw."""
    ts: float
    state_id: str
    loading: bool
    size: Size
    buttons: tuple[Button, ...] = ()
    alive: bool = True
    resources: Resources = field(default_factory=Resources)
    frame_path: Optional[str] = None
    # 64-bit dhash chuoi '0'/'1'. BRAIN dung khop mo (hamming<=12) khi state_id
    # khong trung (md5 khuech dai 1 bit dhash -> id khac han). None = anh sai size.
    dhash: Optional[str] = None
    # Page UI nhan bang landmark template match (vd "page_main"). Robust hon dhash
    # voi man DONG/3D. None neu khong chay page detection / khong khop.
    page: Optional[str] = None
    page_score: Optional[float] = None
    # Set-of-Mark cho LLM agent vision: cac element da danh so + anh marked.
    # marks = UNG VIEN (CV co the sot/rac), agent VERIFY tren anh goc.
    marks: tuple[Mark, ...] = ()
    marked_path: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["buttons"] = [asdict(b) for b in self.buttons]
        d["marks"] = [asdict(m) for m in self.marks]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Observation":
        sz = d["size"]
        return cls(
            ts=d["ts"],
            state_id=d["state_id"],
            loading=d["loading"],
            size=Size(sz["w"], sz["h"]),
            buttons=tuple(Button(**b) for b in d.get("buttons", [])),
            alive=d.get("alive", True),
            resources=Resources(**d.get("resources", {})),
            frame_path=d.get("frame_path"),
            dhash=d.get("dhash"),
            page=d.get("page"),
            page_score=d.get("page_score"),
            marks=tuple(Mark(**m) for m in d.get("marks", [])),
            marked_path=d.get("marked_path"),
        )


class ActionKind(str, Enum):
    CLICK = "click"
    POLITE_CLICK = "polite_click"
    FG_CLICK = "fg_click"
    DRAG = "drag"
    KEY = "key"
    WAIT = "wait"
    NOOP = "noop"


@dataclass(frozen=True, slots=True)
class Action:
    """BRAIN -> EYE: mot hanh dong."""
    kind: ActionKind
    x: Optional[int] = None
    y: Optional[int] = None
    x1: Optional[int] = None
    y1: Optional[int] = None
    steps: Optional[int] = None
    key: Optional[str] = None
    duration_ms: Optional[int] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Action":
        return cls(
            kind=ActionKind(d["kind"]),
            x=d.get("x"), y=d.get("y"),
            x1=d.get("x1"), y1=d.get("y1"),
            steps=d.get("steps"), key=d.get("key"),
            duration_ms=d.get("duration_ms"),
        )

    # --- factory tien dung ---
    @staticmethod
    def click(x: int, y: int) -> "Action":
        return Action(ActionKind.CLICK, x=x, y=y)

    @staticmethod
    def polite_click(x: int, y: int) -> "Action":
        return Action(ActionKind.POLITE_CLICK, x=x, y=y)

    @staticmethod
    def drag(x0: int, y0: int, x1: int, y1: int, steps: int = 14) -> "Action":
        return Action(ActionKind.DRAG, x=x0, y=y0, x1=x1, y1=y1, steps=steps)

    @staticmethod
    def key_press(key: str) -> "Action":
        return Action(ActionKind.KEY, key=key)

    @staticmethod
    def wait(duration_ms: int) -> "Action":
        return Action(ActionKind.WAIT, duration_ms=duration_ms)


@dataclass(frozen=True, slots=True)
class ActionResult:
    ok: bool
    error: Optional[str] = None
    observation: Optional[Observation] = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "error": self.error,
            "observation": self.observation.to_dict() if self.observation else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ActionResult":
        obs = d.get("observation")
        return cls(
            ok=d["ok"],
            error=d.get("error"),
            observation=Observation.from_dict(obs) if obs else None,
        )


# ============================================================================
# AUTONOMY (tu choi) - 4 tang: Outcome/Verdict, TaskSpec/TaskResult.
# Xem AUTONOMY_DESIGN.md. Day la "ngon ngu chung" cho cac use case tu dong hoa.
# ============================================================================


class Outcome(str, Enum):
    """Ket qua 1 hanh dong/battle (tang Outcome Verification)."""
    VICTORY = "victory"        # thang tran
    DEFEAT = "defeat"          # thua tran
    IN_BATTLE = "in_battle"    # dang danh (chua xong)
    LOADING = "loading"        # man chuyen canh
    NO_RESOURCE = "no_resource"  # het AP/ve/dieu kien -> dung
    REWARD = "reward"          # man nhan thuong (sau battle/collect)
    UNKNOWN = "unknown"        # khong nhan dien duoc


@dataclass(frozen=True, slots=True)
class Verdict:
    """Ket luan ve trang thai hien tai sau 1 hanh dong. confidence 0..1."""
    outcome: Outcome
    confidence: float = 0.0
    detail: str = ""
    resources: Resources = field(default_factory=Resources)

    def to_dict(self) -> dict:
        return {"outcome": self.outcome.value, "confidence": self.confidence,
                "detail": self.detail, "resources": asdict(self.resources)}


@dataclass(frozen=True, slots=True)
class TaskSpec:
    """Mo ta 1 NHIEM VU tu dong (tang Task Executor). Task = DU LIEU, khong code cung.

    goal_screen: man dich (label trong world graph, vd 'SoulBattle').
    action: loai viec - 'challenge' (vao danh), 'collect' (nhan thuong), 'navigate' (chi di toi).
    element: (tuy chon) label element can click o goal_screen (vd 'Challenge'). None -> tu suy.
    repeat: so lan lap (vd farm 10 tran).
    stop_on: dung khi gap cac Outcome nay (vd NO_RESOURCE).
    ap_cost: AP ton moi lan (de ResourcePolicy quyet dinh). 0 = khong ton/khong biet.
    max_steps: tran an toan (so action toi da).
    """
    goal_screen: str
    action: str = "challenge"
    element: Optional[str] = None
    repeat: int = 1
    stop_on: tuple[Outcome, ...] = (Outcome.NO_RESOURCE,)
    ap_cost: int = 0
    max_steps: int = 60

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stop_on"] = [o.value for o in self.stop_on]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TaskSpec":
        return cls(
            goal_screen=d["goal_screen"],
            action=d.get("action", "challenge"),
            element=d.get("element"),
            repeat=int(d.get("repeat", 1)),
            stop_on=tuple(Outcome(o) for o in d.get("stop_on", ["no_resource"])),
            ap_cost=int(d.get("ap_cost", 0)),
            max_steps=int(d.get("max_steps", 60)),
        )


@dataclass(frozen=True, slots=True)
class TaskResult:
    """Ket qua chay 1 TaskSpec."""
    ok: bool
    goal_screen: str
    done_count: int = 0          # so lan da DANH xong (thang + thua + reward)
    requested: int = 0           # so lan yeu cau
    stopped_reason: str = ""     # vi sao dung (du repeat / no_resource / loi / chua map duong)
    verdicts: tuple[Verdict, ...] = ()
    wins: int = 0                # so tran THANG (victory + reward)
    losses: int = 0             # so tran THUA (defeat)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "goal_screen": self.goal_screen,
                "done_count": self.done_count, "requested": self.requested,
                "stopped_reason": self.stopped_reason,
                "wins": self.wins, "losses": self.losses,
                "verdicts": [v.to_dict() for v in self.verdicts]}
