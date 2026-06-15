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
