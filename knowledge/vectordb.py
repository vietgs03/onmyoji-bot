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
import os, sys, pickle, re
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "knowledge"))
VDB_DIR = os.path.join(ROOT, "knowledge", "vectordb")
os.makedirs(VDB_DIR, exist_ok=True)
INDEX_PATH = os.path.join(VDB_DIR, "index.pkl")


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
        docs = KB().documents()
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
