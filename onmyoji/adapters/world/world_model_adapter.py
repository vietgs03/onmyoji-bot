"""onmyoji.adapters.world.world_model_adapter - boc world_model.py thanh WorldModelPort.

KHONG viet lai graph logic - chi adapt API cu (bfs_path tra list click) sang
contract moi (path_to tra list[Action]).
"""
from __future__ import annotations

import json
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

# Anh xa OAS page name -> WM label (data, khong hardcode). Page detector robust
# hon dhash voi man DONG -> fallback khi dhash khong khop. Load 1 lan.
_PAGE_MAP_PATH = os.path.join(_ROOT, "knowledge", "page_label_map.json")


def _load_page_map() -> dict:
    try:
        with open(_PAGE_MAP_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return {k: v for k, v in d.items() if not k.startswith("_")}
    except Exception:  # noqa: BLE001
        return {}


class WorldModelAdapter(WorldModelPort):
    """Boc scripts/world_model.py WorldModel."""

    def __init__(self, world=None):
        if world is None:
            from world_model import WorldModel
            world = WorldModel().load()
        self._wm = world
        self._page_map = _load_page_map()

    def resolve_label(self, state_id: str) -> Optional[str]:
        st = self._wm.states.get(state_id)
        return st.get("label") if st else None

    def resolve_page(self, page: Optional[str]) -> Optional[str]:
        """OAS page name -> WM label qua page_label_map.json. None neu khong map."""
        if not page:
            return None
        return self._page_map.get(page)

    def state_for_label(self, label: str) -> Optional[str]:
        """1 state_id da luu co label nay (diem xuat phat cho path_to)."""
        return self._label_to_state(label)

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

    def record_element(self, state_id: str, cx: int, cy: int, label: str) -> None:
        """Ghi element da agent verify cho state (toa do + label). Self-learning."""
        if hasattr(self._wm, "add_verified_element"):
            self._wm.add_verified_element(state_id, cx, cy, label)

    def elements_for(self, state_id: str) -> list[dict]:
        if hasattr(self._wm, "verified_elements"):
            return list(self._wm.verified_elements(state_id))
        return []

    def save(self) -> None:
        self._wm.save()

    def stats(self) -> dict:
        return self._wm.stats()
