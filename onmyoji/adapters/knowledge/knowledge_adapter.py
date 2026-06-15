"""onmyoji.adapters.knowledge.knowledge_adapter - boc vectordb.py thanh KnowledgePort."""
from __future__ import annotations

import os
import sys
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
for _p in ("knowledge", "ml"):
    _full = os.path.join(_ROOT, _p)
    if _full not in sys.path:
        sys.path.insert(0, _full)

from onmyoji.domain.ports import KnowledgePort


class KnowledgeAdapter(KnowledgePort):
    """Boc knowledge/vectordb.py VectorDB (TF-IDF semantic search)."""

    def __init__(self, vdb=None):
        self._vdb = vdb  # lazy load (sklearn nang ~3s)

    def _db(self):
        if self._vdb is None:
            from vectordb import VectorDB
            self._vdb = VectorDB.load()
        return self._vdb

    def ask(self, query: str, k: int = 5) -> list[dict]:
        results = self._db().search(query, k=k)
        # chuan hoa key tra ve (giu type/title/text/score)
        return [
            {
                "type": r.get("type"),
                "title": r.get("title"),
                "text": r.get("text", "")[:300],
                "score": r.get("score", 0.0),
            }
            for r in results
        ]

    def learn(self, title: str, text: str, doc_type: str = "learned",
              doc_id=None, meta=None) -> dict:
        """Ghi tri thuc agent vua hoc vao vector DB (append-only + search ngay)."""
        return self._db().add(title=title, text=text, doc_type=doc_type,
                              doc_id=doc_id, meta=meta)
