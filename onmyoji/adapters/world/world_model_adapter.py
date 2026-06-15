"""onmyoji.adapters.world.world_model_adapter - boc world_model.py thanh WorldModelPort.

KHONG viet lai graph logic - chi adapt API cu (bfs_path tra list click) sang
contract moi (path_to tra list[Action]).
"""
from __future__ import annotations

import os
import sys
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
for _p in ("scripts", "automation"):
    _full = os.path.join(_ROOT, _p)
    if _full not in sys.path:
        sys.path.insert(0, _full)

from onmyoji.domain.entities import Action, ActionKind
from onmyoji.domain.ports import WorldModelPort


class WorldModelAdapter(WorldModelPort):
    """Boc scripts/world_model.py WorldModel."""

    def __init__(self, world=None):
        if world is None:
            from world_model import WorldModel
            world = WorldModel().load()
        self._wm = world

    def resolve_label(self, state_id: str) -> Optional[str]:
        st = self._wm.states.get(state_id)
        return st.get("label") if st else None

    def match_state(self, dhash: Optional[str], state_id: str) -> Optional[str]:
        """Khop MO theo dhash (hamming <= CANON_THR) -> tra sid CHUAN da luu.

        Day la cau noi quan trong giua EYE (Rust/Python) va world model: 2 lop CV
        co the cho dhash lech vai bit (Rust vs cv2) -> state_id md5 khac han. Ham
        nay dua vao logic goc cua world_model (hamming) de van nhan ra cung man.
        Khong co dhash -> chi khop chinh xac (giu hanh vi cu)."""
        # khop chinh xac truoc (nhanh, va dung khi EYE chinh la Python goc)
        if state_id in self._wm.states:
            return state_id
        if not dhash:
            return None
        from perception import hamming  # noqa: PLC0415
        from world_model import CANON_THR  # noqa: PLC0415
        best_sid, best_d = None, CANON_THR + 1
        for sid, st in self._wm.states.items():
            stored = st.get("dhash")
            if not stored:
                continue
            d = hamming(dhash, stored)
            if d <= CANON_THR and d < best_d:
                best_sid, best_d = sid, d
        return best_sid

    def _label_to_state(self, label: str) -> Optional[str]:
        for sid, st in self._wm.states.items():
            if st.get("label") == label:
                return sid
        # cho phep truyen state_id truc tiep lam "label"
        return label if label in self._wm.states else None

    def path_to(self, from_state: str, to_label: str) -> Optional[list[Action]]:
        dst = self._label_to_state(to_label)
        if dst is None:
            return None
        clicks = self._wm.bfs_path(from_state, dst)
        if clicks is None:
            return None
        return [Action.click(int(x), int(y)) for (x, y) in clicks]

    def record_transition(self, frm: str, action: Action, to: str) -> None:
        if action.kind in (ActionKind.CLICK, ActionKind.POLITE_CLICK, ActionKind.FG_CLICK):
            self._wm.add_edge(frm, (action.x, action.y), to)
            self._wm.mark_tried(frm, (action.x, action.y))

    def save(self) -> None:
        self._wm.save()

    def stats(self) -> dict:
        return self._wm.stats()
