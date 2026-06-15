"""onmyoji.interface.container - Composition Root (noi DUY NHAT wiring cac tang).

Day la cho ghep adapter cu the vao port. Doi tu PythonEye sang RustEye chi sua
O DAY, khong dau khac. Tang application/domain khong biet gi ve viec nay.
"""
from __future__ import annotations

import os

from onmyoji.domain.ports import EyePort
from onmyoji.application.use_cases import (
    PerceiveUseCase, WaitStableUseCase, NavigateUseCase, ActUseCase,
    AskKnowledgeUseCase,
)


def build_eye() -> EyePort:
    """Chon impl Eye theo env. Mac dinh PythonEye (cv2).

    ONMYOJI_EYE=python  -> PythonEye (cv2 + PowerShell, hien tai)
    ONMYOJI_EYE=rust    -> RustEye (socket toi onmyoji-eye.exe) [chua co]
    ONMYOJI_EYE=fake    -> FakeEye (test, khong can game)
    """
    kind = os.environ.get("ONMYOJI_EYE", "python").lower()
    if kind == "fake":
        from onmyoji.adapters.eye_py.fake_eye import FakeEye
        return FakeEye()
    if kind == "rust":
        # TODO: from onmyoji.adapters.eye_rs.rust_eye import RustEye
        raise NotImplementedError("RustEye chua implement - dung ONMYOJI_EYE=python")
    from onmyoji.adapters.eye_py.python_eye import PythonEye
    return PythonEye()


class Container:
    """Giu cac singleton + factory use case. 1 instance/process."""

    def __init__(self, eye: EyePort | None = None):
        self.eye = eye or build_eye()

    # use case factories
    def perceive(self) -> PerceiveUseCase:
        return PerceiveUseCase(self.eye)

    def wait_stable(self, **kw) -> WaitStableUseCase:
        return WaitStableUseCase(self.eye, **kw)

    def act(self) -> ActUseCase:
        return ActUseCase(self.eye)

    def close(self) -> None:
        self.eye.close()
