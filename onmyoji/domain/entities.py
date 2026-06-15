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

    def to_dict(self) -> dict:
        d = asdict(self)
        d["buttons"] = [asdict(b) for b in self.buttons]
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
