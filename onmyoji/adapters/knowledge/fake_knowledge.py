"""onmyoji.adapters.knowledge.fake_knowledge - KnowledgePort gia lap cho test."""
from __future__ import annotations

from onmyoji.domain.ports import KnowledgePort


class FakeKnowledge(KnowledgePort):
    """Tra ket qua co dinh, KHONG load sklearn/vectordb -> test thuan, khong side-effect."""

    def __init__(self, docs: list[dict] | None = None):
        self._docs = docs or [
            {"type": "mode", "title": "Soul", "text": "farm soul o Soul zone", "score": 0.9},
            {"type": "soul", "title": "ATK", "text": "2-set +15% ATK", "score": 0.7},
        ]

    def ask(self, query: str, k: int = 5) -> list[dict]:
        return self._docs[:k]
