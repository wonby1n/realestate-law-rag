"""검색 평가: 정답지 확정 문항의 조문 재현율@5 (명세: docs/specs/002-bm25-search.md).

재현율@5 = 문항별 (상위 5개에 들어온 정답 조문 수 / 정답 조문 수)의 평균.
항 단위 결과는 같은 조의 항이 여러 개 나올 수 있어서 "조"로 묶어 비교한다.

사용법: python src/evaluate.py
"""

import json
from datetime import date
from pathlib import Path

from search_bm25 import Searcher

ROOT = Path(__file__).resolve().parent.parent
K = 5


def load_questions() -> list[dict]:
    rows = [json.loads(l) for l in (ROOT / "eval" / "questions_draft.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    # 정답 조문이 있는 확정 문항만 (거절·법령 밖 문항은 gold가 비어 있음)
    return [q for q in rows if q.get("verified") and q.get("gold")]


def recall_at_k(searcher: Searcher, q: dict) -> tuple[float, list[str]]:
    hits = searcher.search(q["question"], k=K)
    found = {(c["law"], c["article"]) for c, _ in hits}
    gold = {(g["law"], g["article"]) for g in q["gold"]}
    missed = [f"{law} {art}" for law, art in gold - found]
    return len(gold & found) / len(gold), missed


def main() -> None:
    questions = load_questions()
    print(f"평가 문항 {len(questions)}개, 재현율@{K}\n")
    results = []
    for unit in ["조", "항"]:
        for with_title in [False, True]:
            s = Searcher(unit, with_title)
            per_q = {q["id"]: recall_at_k(s, q) for q in questions}
            score = sum(r for r, _ in per_q.values()) / len(per_q)
            name = f"{unit} 단위, 제목 {'붙임' if with_title else '없음'}"
            fails = {qid: missed for qid, (r, missed) in per_q.items() if r < 1}
            print(f"{name}: {score:.3f}  놓친 문항 {len(fails)}개 {sorted(fails)}")
            results.append({"setting": name, "unit": unit, "with_title": with_title,
                            "recall_at_5": round(score, 3), "missed": fails})

    out = ROOT / "eval" / "results" / f"bm25_{date.today():%Y%m%d}.json"
    out.write_text(json.dumps({"method": "BM25 (어절 + 글자 두 개 묶음)", "k": K,
                               "n_questions": len(questions), "results": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
