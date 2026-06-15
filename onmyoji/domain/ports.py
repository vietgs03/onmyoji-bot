"""onmyoji.domain.ports - Interface (Ports) cho Clean Architecture.

Cac tang ngoai (adapters) PHAI implement nhung interface nay. Tang application
(use case) chi biet Toi Port, KHONG biet implementation cu the.

=> Hom nay EyePort la Python (cv2). Mai doi sang Rust (socket client) ma
   use case khong sua 1 dong. Day la diem cot loi cua viec tach layer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from .entities import Observation, Action, ActionResult


class EyePort(ABC):
    """Tri giac + dieu khien game. SE co 2 impl: PythonEye (cv2) va RustEye (socket)."""

    @abstractmethod
    def observe(self) -> Observation:
        """Chup + phan tich man hinh hien tai -> Observation (khong anh raw)."""

    @abstractmethod
    def act(self, action: Action) -> ActionResult:
        """Thuc thi 1 action len game, tra ket qua + observation moi."""

    def close(self) -> None:  # optional
        pass


class WorldModelPort(ABC):
    """Ban do UI da hoc (graph node/edge). Navigate, path-finding."""

    @abstractmethod
    def resolve_label(self, state_id: str) -> Optional[str]:
        """state_id (dhash) -> label logic (vd 'HOME', 'SHOP')."""

    @abstractmethod
    def path_to(self, from_state: str, to_label: str) -> Optional[list[Action]]:
        """Tra chuoi Action de di tu state hien tai toi man co label dich."""

    @abstractmethod
    def record_transition(self, frm: str, action: Action, to: str) -> None:
        """Ghi nho edge: o state frm, lam action -> toi state to."""


class KnowledgePort(ABC):
    """Tri thuc game (KB + vector search)."""

    @abstractmethod
    def ask(self, query: str, k: int = 5) -> list[dict]:
        """Tra cuu ngu nghia -> list document lien quan."""


class GoalPort(ABC):
    """Muc tieu/reward cho moi mode (vd Realm Raid = farm soul)."""

    @abstractmethod
    def objective_for(self, label: str) -> Optional[str]:
        """man hinh label -> mo ta muc tieu can lam o do."""
