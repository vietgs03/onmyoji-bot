#!/usr/bin/env python3
"""
vectordb.py - Vector database cho tri thuc Onmyoji (semantic search).

Bot "hoi" KB bang ngon ngu tu nhien:
  "soul nao tot cho ATK shikigami?"  -> tra cac soul lien quan
  "lam sao farm soul?"               -> mode Soul/Evo zones
  "shikigami SP la gi?"              -> doc lien quan

Backend: TF-IDF + cosine (nhe, khong can tai model lon). Interface thiet ke de sau
nang cap len sentence-transformers (chi can doi _embed). Index toan bo game_kb.documents().

Luu index: knowledge/vectordb/index.pkl
Dung:
  python vectordb.py build              # build index tu KB
  python vectordb.py query "cau hoi"    # tra cuu
  from vectordb import VectorDB; db=VectorDB.load(); db.search("...", k=5)
"""
import os, sys, pickle, re, json, time
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "knowledge"))
VDB_DIR = os.path.join(ROOT, "knowledge", "vectordb")
os.makedirs(VDB_DIR, exist_ok=True)
INDEX_PATH = os.path.join(VDB_DIR, "index.pkl")
# Tri thuc AGENT TU HOC (runtime): append-only, ben vung qua rebuild. Moi doc =
# {id, type, title, text, meta}. Build se gop ca KB + learned -> search thay het.
LEARNED_PATH = os.path.join(VDB_DIR, "learned.json")


def _load_learned():
    """Doc cac doc agent da hoc (append-only JSON). Tra list[dict]."""
    if not os.path.exists(LEARNED_PATH):
        return []
    try:
        with open(LEARNED_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return []


def _save_learned(docs):
    tmp = LEARNED_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    os.replace(tmp, LEARNED_PATH)


class VectorDB:
    def __init__(self, vectorizer, matrix, docs):
        self.vectorizer = vectorizer
        self.matrix = matrix          # (N, F) sparse tf-idf
        self.docs = docs              # list[dict]

    # ---------- build ----------
    @classmethod
    def build(cls):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from game_kb import KB
        docs = KB().documents() + _load_learned()  # gop ca tri thuc agent tu hoc
        corpus = [f"{d['title']} {d['title']} {d['text']}" for d in docs]  # title x2 = boost
        vec = TfidfVectorizer(lowercase=True, ngram_range=(1, 2),
                              min_df=1, max_df=0.6, sublinear_tf=True)
        matrix = vec.fit_transform(corpus)
        db = cls(vec, matrix, docs)
        with open(INDEX_PATH, "wb") as f:
            pickle.dump({"vectorizer": vec, "matrix": matrix, "docs": docs}, f)
        print(f"built vector index: {len(docs)} docs, vocab {len(vec.vocabulary_)} "
              f"-> {INDEX_PATH}")
        return db

    @classmethod
    def load(cls):
        with open(INDEX_PATH, "rb") as f:
            d = pickle.load(f)
        return cls(d["vectorizer"], d["matrix"], d["docs"])

    # ---------- add (agent tu hoc runtime) ----------
    def add(self, title, text, doc_type="learned", doc_id=None, meta=None):
        """Them 1 tri thuc agent VUA HOC (vd 'screen Soul Zone = farm ngoc hon').
        Luu append-only (ben vung) + transform ngay bang vectorizer hien tai de
        search duoc LIEN (vocab moi se duoc nap day du o lan build sau).
        Neu doc_id da co -> CAP NHAT (thay the). Tra doc da luu."""
        import scipy.sparse as sp
        doc_id = doc_id or f"learned:{int(time.time()*1000)}"
        doc = {"id": doc_id, "type": doc_type, "title": title, "text": text,
               "meta": meta or {}}
        # persist append-only (cap nhat neu trung id)
        learned = _load_learned()
        learned = [d for d in learned if d.get("id") != doc_id]
        learned.append(doc)
        _save_learned(learned)
        # cap nhat index trong bo nho (search duoc ngay, khong can rebuild)
        # neu doc_id da co trong self.docs -> thay the dong tuong ung
        corpus = f"{title} {title} {text}"
        row = self.vectorizer.transform([corpus])
        existing = next((i for i, d in enumerate(self.docs) if d.get("id") == doc_id), None)
        if existing is not None:
            self.docs[existing] = doc
            # thay dong matrix (rebuild matrix nho gon hon la sua sparse in-place)
            self.matrix = sp.vstack(
                [self.matrix[:existing], row, self.matrix[existing + 1:]]
            ).tocsr()
        else:
            self.docs.append(doc)
            self.matrix = sp.vstack([self.matrix, row]).tocsr()
        # luu lai index de lan load sau co ngay (khong can rebuild)
        with open(INDEX_PATH, "wb") as f:
            pickle.dump({"vectorizer": self.vectorizer, "matrix": self.matrix,
                         "docs": self.docs}, f)
        return doc

    # ---------- query ----------
    def search(self, query, k=5, type_filter=None):
        """Tra top-k doc khop ngu nghia. type_filter: 'soul'|'mode'|'shikigami'|..."""
        from sklearn.metrics.pairwise import cosine_similarity
        qv = self.vectorizer.transform([query])
        sims = cosine_similarity(qv, self.matrix)[0]
        order = np.argsort(sims)[::-1]
        out = []
        for i in order:
            d = self.docs[i]
            if type_filter and d["type"] != type_filter:
                continue
            out.append({**d, "score": float(sims[i])})
            if len(out) >= k:
                break
        return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        VectorDB.build()
    elif cmd == "query":
        q = " ".join(sys.argv[2:])
        db = VectorDB.load()
        print(f"Q: {q}\n")
        for r in db.search(q, k=6):
            print(f"  [{r['score']:.3f}] ({r['type']}) {r['title']}")
            print(f"        {r['text'][:110]}...")
    else:
        print("usage: vectordb.py build | query <cau hoi>")


if __name__ == "__main__":
    main()
