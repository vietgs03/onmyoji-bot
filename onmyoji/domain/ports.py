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
        """Chup + phan tich man hinh hien tai -> Observation (khong anh raw).

        Mac dinh day du (co detect_buttons). Dung observe_nav() khi chi can
        dieu huong (state_id/loading) de nhanh hon ~9x."""

    def observe_nav(self) -> Observation:
        """Tier "nav": chup + chi tinh dhash/state_id/loading, BO detect_buttons
        (~88% chi phi). Dung cho dieu huong khi chua can toa do nut.
        Mac dinh = observe() (adapter co the override de nhanh hon)."""
        return self.observe()

    def observe_page(self) -> Observation:
        """Tier "page": chup + nhan PAGE bang landmark template match (robust hon
        dhash voi man DONG/3D). Tra Observation co .page/.page_score.
        Mac dinh = observe() (adapter ho tro page se override)."""
        return self.observe()

    def observe_som(self, with_page: bool = False) -> Observation:
        """Tier "agent vision": tao Set-of-Mark (danh so element + luu anh marked)
        cho LLM agent NHIN va chon SO -> click dung toa do. Tra Observation co
        .marks + .marked_path. marks = UNG VIEN (CV co the sot/rac), agent VERIFY
        tren anh goc. Mac dinh = observe() (adapter ho tro SoM se override)."""
        return self.observe()

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

    def resolve_page(self, page: Optional[str]) -> Optional[str]:
        """OAS page name (vd 'page_main') -> label logic (vd 'HOME').

        Page detector (landmark template match) robust hon dhash voi man DONG/3D.
        Dung lam fallback khi dhash khong khop state da hoc. Mac dinh: khong map."""
        return None

    def state_for_label(self, label: str) -> Optional[str]:
        """Tra 1 state_id da luu co label nay (de lam diem xuat phat cho path_to
        khi chi biet label, vd tu page detector). None neu chua hoc label do.
        Mac dinh: khong tra (adapter override)."""
        return None

    def match_state(self, dhash: Optional[str], state_id: str) -> Optional[str]:
        """Tra ve state_id CHUAN da luu khop voi quan sat hien tai.

        Vi sao can: state_id = md5(dhash)[:10]. md5 khuech dai 1 bit dhash thanh
        id KHAC HAN -> so khop state_id chinh xac se truot du man hinh giong nhau
        (vd Rust EYE lech 1 bit dhash so Python). World model goc khop MO bang
        hamming(dhash) <= 12. Method nay tra sid chuan de resolve_label/path_to
        dung tiep. Mac dinh (khong co dhash): chi khop chinh xac state_id."""
        return state_id

    @abstractmethod
    def path_to(self, from_state: str, to_label: str) -> Optional[list[Action]]:
        """Tra chuoi Action de di tu state hien tai toi man co label dich."""

    @abstractmethod
    def record_transition(self, frm: str, action: Action, to: str) -> None:
        """Ghi nho edge: o state frm, lam action -> toi state to."""

    def record_element(self, state_id: str, cx: int, cy: int, label: str,
                       dhash: Optional[str] = None) -> None:
        """Ghi 1 element DA DUOC AGENT XAC NHAN (vision verify) cho state: toa do
        + label. Self-learning: lan sau gap lai man (cung label) -> dung luon,
        khong can CV/agent lai. `dhash` cho phep tu tao node neu man chua hoc.
        Mac dinh: khong lam gi (adapter override)."""

    def elements_for(self, state_id: str) -> list[dict]:
        """Tra cac element da verify cho state ([{cx,cy,label}]). Mac dinh rong."""
        return []

    def untried_elements(self, state_id: str) -> list[dict]:
        """Element da verify nhung CHUA click thu (frontier cap element). Rong = mac dinh."""
        return []

    def frontier(self) -> list[dict]:
        """Cac man da nhan dien nhung con element chua kham pha het ([{label,sid,
        untried}]). Dung de agent biet di dau tiep -> phu het cay ban do."""
        return []

    def explore_stats(self) -> dict:
        """Tong quan tien do kham pha (states/labeled/described/frontier)."""
        return {}


class KnowledgePort(ABC):
    """Tri thuc game (KB + vector search)."""

    @abstractmethod
    def ask(self, query: str, k: int = 5) -> list[dict]:
        """Tra cuu ngu nghia -> list document lien quan."""

    def learn(self, title: str, text: str, doc_type: str = "learned",
              doc_id: Optional[str] = None, meta: Optional[dict] = None) -> dict:
        """GHI tri thuc agent VUA HOC (vd 'screen Soul Zone = farm ngoc hon').
        Search duoc ngay sau do. doc_id trung -> cap nhat. Mac dinh: no-op."""
        return {}


class GoalPort(ABC):
    """Muc tieu/reward cho moi mode (vd Realm Raid = farm soul)."""

    @abstractmethod
    def objective_for(self, label: str) -> Optional[str]:
        """man hinh label -> mo ta muc tieu can lam o do."""
