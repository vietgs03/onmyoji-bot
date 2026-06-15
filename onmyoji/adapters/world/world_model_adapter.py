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

    def canonical_state(self, dhash: Optional[str], state_id: str,
                        page: Optional[str] = None) -> tuple[Optional[str], bool]:
        """Tra (sid_chuan, confirmed) cho quan sat hien tai - NEO theo do BEN nhat.

        Van de goc: man DONG (vd HOME) co dhash troi >CANON_THR moi frame -> moi
        lan hoc lai sinh 1 node moc coi khac -> verified elements PHAN MANH, recall
        hen xui. Page detector (landmark template) KHONG troi -> dung lam neo chinh.

        Thu tu uu tien:
          1. dhash match 1 state da hoc (hamming<=CANON_THR) -> sid do, confirmed.
          2. page -> resolve_label -> node da co label do (HOME) -> sid CHUAN, confirmed.
             (cac frame HOME khac dhash van hoi tu ve 1 node logic).
          3. chi co page (chua co node label) -> (state_id, confirmed=True) - se tao
             node moi NHUNG da xac nhan (page robust).
          4. khong dhash-match, khong page -> (state_id, confirmed=False) - man LA.
        """
        matched = self.match_state(dhash, state_id)
        if matched is not None:
            return matched, True
        label = self.resolve_page(page) if page else None
        if label:
            anchor = self._label_to_state(label)
            if anchor is not None:
                return anchor, True
            return state_id, True  # co page nhung chua co node -> tao moi, da xac nhan
        return state_id, False  # man LA

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

    def record_element(self, state_id: str, cx: int, cy: int, label: str,
                       dhash: str | None = None) -> None:
        """Ghi element da agent verify cho state (toa do + label). Self-learning.
        dhash cho phep tu tao node neu man chua hoc (man dong/moi)."""
        if hasattr(self._wm, "add_verified_element"):
            self._wm.add_verified_element(state_id, cx, cy, label, dhash=dhash)

    def label_state(self, state_id: str, label: str, desc: str | None = None,
                    dhash: str | None = None) -> None:
        """Gan label + mo ta (ngu nghia) cho state. Tao node moi neu chua co
        (man dong/moi) va co dhash. Self-learning: agent DAY he thong man nay la gi."""
        if hasattr(self._wm, "label_state"):
            self._wm.label_state(state_id, label, desc=desc, dhash=dhash)

    def elements_for(self, state_id: str) -> list[dict]:
        if hasattr(self._wm, "verified_elements"):
            return list(self._wm.verified_elements(state_id))
        return []

    def untried_elements(self, state_id: str) -> list[dict]:
        if hasattr(self._wm, "untried_elements"):
            return list(self._wm.untried_elements(state_id))
        return []

    def frontier(self) -> list[dict]:
        if hasattr(self._wm, "frontier_labels"):
            return list(self._wm.frontier_labels())
        return []

    def explore_stats(self) -> dict:
        if hasattr(self._wm, "explore_stats"):
            return dict(self._wm.explore_stats())
        return {}

    def save(self) -> None:
        self._wm.save()

    def stats(self) -> dict:
        return self._wm.stats()
