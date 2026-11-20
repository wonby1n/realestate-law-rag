"""BM25 검색 (명세: docs/specs/002-bm25-search.md).

외부 검색 라이브러리 없이 점수 계산을 직접 구현한다.
"""

import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
FILES = {"조": "chunks_article.jsonl", "항": "chunks_paragraph.jsonl"}


def tokenize(text: str) -> list[str]:
    """어절 + 어절 안의 글자 두 개 묶음. "갱신요구" → [갱신요구, 갱신, 신요, 요구]"""
    tokens = []
    for word in re.findall(r"[가-힣]+|[A-Za-z]+|\d+", text):
        tokens.append(word)
        if len(word) > 2 and re.match(r"[가-힣]", word):
            tokens += [word[i:i + 2] for i in range(len(word) - 1)]
    return tokens


def load_chunks(unit: str) -> list[dict]:
    path = PROCESSED / FILES[unit]
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tfs = [Counter(tokenize(d)) for d in docs]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avg_len = sum(self.lens) / len(self.lens)
        n = len(docs)
        df = Counter(t for tf in self.tfs for t in tf)
        # 흔한 토큰일수록 낮은 가중치 (+1로 음수 방지)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def scores(self, query: str) -> list[float]:
        q = tokenize(query)
        out = []
        for tf, length in zip(self.tfs, self.lens):
            s = 0.0
            norm = self.k1 * (1 - self.b + self.b * length / self.avg_len)
            for t in q:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + norm)
            out.append(s)
        return out


class Searcher:
    def __init__(self, unit: str = "항", with_title: bool = True):
        self.chunks = load_chunks(unit)
        field = "text_with_title" if with_title else "text"
        self.bm25 = BM25([c[field] for c in self.chunks])

    def search(self, query: str, k: int = 5) -> list[tuple[dict, float]]:
        scored = sorted(zip(self.chunks, self.bm25.scores(query)), key=lambda x: -x[1])
        return [(c, s) for c, s in scored[:k] if s > 0]
