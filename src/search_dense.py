"""임베딩 검색과 하이브리드 (명세: docs/specs/004-dense-hybrid.md)."""

from pathlib import Path

import numpy as np

from query import normalize
from search_bm25 import FILES, PROCESSED, Searcher as BM25Searcher, load_chunks

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "index"
MODEL_NAME = "BAAI/bge-m3"
RRF_K = 60

_model = None


def get_model():
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = SentenceTransformer(MODEL_NAME, device=device)
        if device == "cuda":
            _model.half()
    return _model


def embed(texts: list[str]) -> np.ndarray:
    return get_model().encode(texts, batch_size=16, normalize_embeddings=True,
                              convert_to_numpy=True, show_progress_bar=len(texts) > 50).astype(np.float32)


class DenseSearcher:
    def __init__(self, unit: str = "조"):
        self.chunks = load_chunks(unit)
        src = PROCESSED / FILES[unit]
        cache = INDEX / f"{unit}_{MODEL_NAME.split('/')[-1]}.npy"
        # 덩어리 파일이 캐시보다 새로우면 다시 계산
        if cache.exists() and cache.stat().st_mtime > src.stat().st_mtime:
            self.vecs = np.load(cache)
        else:
            INDEX.mkdir(parents=True, exist_ok=True)
            self.vecs = embed([c["text_with_title"] for c in self.chunks])
            np.save(cache, self.vecs)

    def scores(self, query: str) -> np.ndarray:
        return self.vecs @ embed([query])[0]

    def search(self, query: str, k: int = 5) -> list[tuple[dict, float]]:
        s = self.scores(query)
        top = np.argsort(-s)[:k]
        return [(self.chunks[i], float(s[i])) for i in top]


class HybridSearcher:
    """BM25(다듬은 질문) 순위와 임베딩(원래 질문) 순위를 RRF로 합친다."""

    def __init__(self, unit: str = "조"):
        self.bm25 = BM25Searcher(unit, with_title=True)
        self.dense = DenseSearcher(unit)
        self.chunks = self.dense.chunks

    def search(self, query: str, k: int = 5) -> list[tuple[dict, float]]:
        b = np.array(self.bm25.bm25.scores(normalize(query)[0]))
        d = self.dense.scores(query)
        rrf = np.zeros(len(self.chunks))
        for s in (b, d):
            ranks = np.empty(len(s), dtype=int)
            ranks[np.argsort(-s)] = np.arange(1, len(s) + 1)
            rrf += 1 / (RRF_K + ranks)
        top = np.argsort(-rrf)[:k]
        return [(self.chunks[i], float(rrf[i])) for i in top]


RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
CANDIDATES = 20
_reranker = None


def get_reranker():
    global _reranker
    if _reranker is None:
        import torch
        from sentence_transformers import CrossEncoder
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _reranker = CrossEncoder(RERANK_MODEL, device=device, max_length=1024)
        if device == "cuda":
            _reranker.model.half()
    return _reranker


class RerankSearcher:
    """하이브리드 상위 20개를 리랭커로 다시 매긴다 (명세 005)."""

    def __init__(self, unit: str = "조"):
        self.hybrid = HybridSearcher(unit)
        self.chunks = self.hybrid.chunks

    def search(self, query: str, k: int = 5) -> list[tuple[dict, float]]:
        cands = [c for c, _ in self.hybrid.search(query, k=CANDIDATES)]
        scores = get_reranker().predict([(query, c["text_with_title"]) for c in cands], batch_size=8)
        order = np.argsort(-scores)[:k]
        return [(cands[i], float(scores[i])) for i in order]
