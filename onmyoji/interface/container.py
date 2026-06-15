"""onmyoji.interface.container - Composition Root (noi DUY NHAT wiring cac tang).

Day la cho ghep adapter cu the vao port. Doi tu PythonEye sang RustEye chi sua
O DAY, khong dau khac. Tang application/domain khong biet gi ve viec nay.
"""
from __future__ import annotations

import os

from onmyoji.domain.ports import EyePort, WorldModelPort, KnowledgePort
from onmyoji.application.use_cases import (
    PerceiveUseCase, WaitStableUseCase, NavigateUseCase, ActUseCase,
    AskKnowledgeUseCase,
)


def build_eye() -> EyePort:
    """Chon impl Eye theo env. Mac dinh PythonEye (cv2).

    ONMYOJI_EYE=python  -> PythonEye (cv2 + PowerShell, mac dinh)
    ONMYOJI_EYE=rust    -> RustEye (socket toi onmyoji-eye, perception thuan Rust)
                           Dat ONMYOJI_EYE_SPAWN=1 de tu khoi dong onmyoji-eye --ps.
    ONMYOJI_EYE=fake    -> FakeEye (test, khong can game)
    """
    kind = os.environ.get("ONMYOJI_EYE", "python").lower()
    if kind == "fake":
        from onmyoji.adapters.eye_py.fake_eye import FakeEye
        return FakeEye()
    if kind == "rust":
        from onmyoji.adapters.eye_rs.rust_eye import RustEye
        return RustEye()
    from onmyoji.adapters.eye_py.python_eye import PythonEye
    return PythonEye()


def build_world(eye_kind: str | None = None) -> WorldModelPort | None:
    """WorldModel adapter (lazy). None neu khong load duoc (vd fake/test)."""
    kind = (eye_kind or os.environ.get("ONMYOJI_EYE", "python")).lower()
    if kind == "fake":
        return None
    try:
        from onmyoji.adapters.world.world_model_adapter import WorldModelAdapter
        return WorldModelAdapter()
    except Exception:  # noqa: BLE001
        return None


def build_knowledge() -> KnowledgePort | None:
    """Knowledge adapter (lazy - sklearn nang, chi load khi can)."""
    try:
        from onmyoji.adapters.knowledge.knowledge_adapter import KnowledgeAdapter
        return KnowledgeAdapter()
    except Exception:  # noqa: BLE001
        return None


class Container:
    """Giu cac singleton + factory use case. 1 instance/process."""

    def __init__(self, eye: EyePort | None = None,
                 world: WorldModelPort | None = None,
                 knowledge: KnowledgePort | None = None):
        self.eye = eye or build_eye()
        self._world = world
        self._knowledge = knowledge
        self._world_built = world is not None
        self._knowledge_built = knowledge is not None

    @property
    def world(self) -> WorldModelPort | None:
        if not self._world_built:
            self._world = build_world()
            self._world_built = True
        return self._world

    @property
    def knowledge(self) -> KnowledgePort | None:
        if not self._knowledge_built:
            self._knowledge = build_knowledge()
            self._knowledge_built = True
        return self._knowledge

    # use case factories
    def perceive(self) -> PerceiveUseCase:
        return PerceiveUseCase(self.eye, self.world)

    def wait_stable(self, **kw) -> WaitStableUseCase:
        return WaitStableUseCase(self.eye, **kw)

    def act(self) -> ActUseCase:
        return ActUseCase(self.eye)

    def navigate(self, **kw) -> NavigateUseCase:
        if self.world is None:
            raise RuntimeError("WorldModel khong kha dung (vd dang dung fake eye)")
        return NavigateUseCase(self.eye, self.world, **kw)

    def ask_knowledge(self) -> AskKnowledgeUseCase:
        if self.knowledge is None:
            raise RuntimeError("Knowledge khong kha dung")
        return AskKnowledgeUseCase(self.knowledge)

    def close(self) -> None:
        self.eye.close()
