"""검색 평가: 정답지 확정 문항의 조문 재현율@5.

재현율@5 = 문항별 (상위 5개에 들어온 정답 조문 수 / 정답 조문 수)의 평균.
항 단위 결과는 같은 조의 항이 여러 개 나올 수 있어서 "조"로 묶어 비교한다.

비교 (명세 002·003·004):
- bm25          : BM25, 원래 질문
- bm25+다듬기   : BM25, 질문 다듬기 적용
- dense         : 임베딩(bge-m3), 원래 질문
- dense+다듬기  : 임베딩, 질문 다듬기 적용
- hybrid        : bm25+다듬기 와 dense 를 RRF로 합침
- hybrid+rerank : hybrid 상위 20개를 리랭커로 다시 매김 (명세 005)
  + hybrid 상위 20개 안에 정답이 있는지(후보 재현율@20)도 출력
모두 법령명·조문 제목을 붙인 덩어리 기준 (E01).

사용법: python src/evaluate.py
"""

import json
import time
from datetime import date
from pathlib import Path

from query import normalize
from search_bm25 import Searcher as BM25Searcher
from search_dense import CANDIDATES, DenseSearcher, HybridSearcher, RerankSearcher

ROOT = Path(__file__).resolve().parent.parent
K = 5


def load_questions() -> list[dict]:
    rows = [json.loads(l) for l in (ROOT / "eval" / "questions_draft.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    # 정답 조문이 있는 확정 문항만 (거절·법령 밖 문항은 gold가 비어 있음)
    return [q for q in rows if q.get("verified") and q.get("gold")]


def recall_at_k(searcher, query: str, gold: list[dict]) -> tuple[float, list[str], list[str]]:
    hits = searcher.search(query, k=K)
    found = {(c["law"], c["article"]) for c, _ in hits}
    gold_set = {(g["law"], g["article"]) for g in gold}
    missed = [f"{law} {art}" for law, art in gold_set - found]
    return len(gold_set & found) / len(gold_set), missed, [c["id"] for c, _ in hits]


def main() -> None:
    questions = load_questions()
    print(f"평가 문항 {len(questions)}개, 재현율@{K}\n")
    results = []
    for unit in ["조", "항"]:
        bm25, dense, hybrid = BM25Searcher(unit, True), DenseSearcher(unit), HybridSearcher(unit)
        rerank = RerankSearcher(unit)
        configs = [("bm25", bm25, False), ("bm25+다듬기", bm25, True),
                   ("dense", dense, False), ("dense+다듬기", dense, True),
                   ("hybrid", hybrid, False), ("hybrid+rerank", rerank, False)]
        for name, searcher, use_norm in configs:
            per_q = {}
            start = time.perf_counter()
            for q in questions:
                query = normalize(q["question"])[0] if use_norm else q["question"]
                per_q[q["id"]] = recall_at_k(searcher, query, q["gold"])
            per_sec = (time.perf_counter() - start) / len(questions)
            score = sum(r for r, _, _ in per_q.values()) / len(per_q)
            fails = {qid: {"missed": m, "top5": top} for qid, (r, m, top) in per_q.items() if r < 1}
            print(f"{unit} 단위 {name:14s}: {score:.3f}  ({per_sec:.2f}초/문항)  놓친 문항 {len(fails)}개 {sorted(fails)}")
            results.append({"unit": unit, "method": name, "recall_at_5": round(score, 3),
                            "sec_per_question": round(per_sec, 3), "failures": fails})
        cand = {}
        for q in questions:
            hits = hybrid.search(q["question"], k=CANDIDATES)
            found = {(c["law"], c["article"]) for c, _ in hits}
            gold = {(g["law"], g["article"]) for g in q["gold"]}
            cand[q["id"]] = len(gold & found) / len(gold)
        r20 = sum(cand.values()) / len(cand)
        no_cand = sorted(qid for qid, r in cand.items() if r < 1)
        print(f"{unit} 단위 hybrid 후보 재현율@{CANDIDATES}: {r20:.3f}  후보에도 없는 문항 {no_cand}\n")
        results.append({"unit": unit, "method": f"hybrid 후보@{CANDIDATES}", "recall": round(r20, 3), "missing": no_cand})

    out = ROOT / "eval" / "results" / f"retrieval_{date.today():%Y%m%d}.json"
    out.write_text(json.dumps({"k": K, "n_questions": len(questions), "embedding": "BAAI/bge-m3", "reranker": "BAAI/bge-reranker-v2-m3",
                               "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
