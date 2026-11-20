"""원문(data/raw) → 검색 단위(data/processed)로 쪼개기.

두 가지 단위를 만든다 (검색 실험 1에서 비교):
- chunks_article.jsonl  : 조 단위 (조문 전체)
- chunks_paragraph.jsonl: 항 단위 (항 + 그 아래 호·목). 항이 없는 조문은 조문 전체가 한 덩어리

각 덩어리에는
- text            : 본문만 (개정 표시 제거)
- text_with_title : "법령명 제N조(제목) ②" 를 앞에 붙인 본문 → 제목 붙이기 효과 비교용
- id              : 법령명|제N조의M|항번호 → 정답지와 바로 비교

사용법: python3 src/parse.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

CIRCLED = {c: i + 1 for i, c in enumerate("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳")}
# <개정 2020.7.31>, <신설 ...>, [본조신설 2020.7.31], [전문개정 ...], [시행일: ...] 등
REVISION_TAG = re.compile(r"<(개정|신설|삭제|타법개정)[^>]*>|\[(본조신설|전문개정|제목개정|본조제목개정|종전[^\]]*|시행일[^\]]*)[^\]]*\]")


def as_list(x):
    if not x:
        return []
    return x if isinstance(x, list) else [x]


def as_text(x) -> str:
    """항내용·호내용이 가끔 문자열 목록으로 온다."""
    if isinstance(x, list):
        return "\n".join(as_text(i) for i in x)
    return str(x or "")


def clean(text: str) -> str:
    text = REVISION_TAG.sub("", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def article_label(a: dict) -> str:
    branch = a.get("조문가지번호") or ""
    return f"제{a['조문번호']}조" + (f"의{branch}" if branch else "")


def ho_lines(ho_list) -> list[str]:
    lines = []
    for ho in as_list(ho_list):
        lines.append(as_text(ho.get("호내용")))
        for mok in as_list(ho.get("목")):
            lines.append(as_text(mok.get("목내용")))
    return lines


def law_type(name: str) -> str:
    if name.endswith("시행규칙"):
        return "시행규칙"
    if name.endswith("시행령"):
        return "시행령"
    return "법률"


def parse_law(path: Path):
    law_name, effective = path.stem.rsplit("_", 1)
    units = json.loads(path.read_text(encoding="utf-8"))["법령"]["조문"]["조문단위"]

    articles, paragraphs = [], []
    chapter = ""
    for a in as_list(units):
        if a.get("조문여부") == "전문":  # 장·절 제목 줄
            chapter = clean(as_text(a.get("조문내용")))
            continue

        head = clean(as_text(a.get("조문내용")))
        if re.search(r"^제\d+조(의\d+)?\s*삭제", head):
            continue  # 삭제된 조문

        label = article_label(a)
        if head == label and not a.get("항"):
            continue  # 다른 조로 옮겨지고 번호만 남은 조문 (예: 시행령 제2조의2 → 제9조로 이동)
        title = a.get("조문제목") or ""
        prefix = f"{law_name} {label}({title})"
        base = {
            "law": law_name,
            "law_type": law_type(law_name),
            "effective_date": effective,
            "article": label,
            "title": title,
            "chapter": chapter,
        }

        body_lines = [head]  # 조문 머리 + 항번호 없이 바로 붙는 호
        para_items = []
        for hang in as_list(a.get("항")):
            num = hang.get("항번호")
            lines = [as_text(hang.get("항내용"))] + ho_lines(hang.get("호"))
            lines = [clean(l) for l in lines if clean(l)]
            if lines and re.match(r"^[①-⑳]?\s*삭제\s*(<[^>]*>)?$", lines[0]):
                continue  # 삭제된 항 (예: "① 삭제 <2009.7.1>")
            if num and num.strip() in CIRCLED:
                para_items.append((CIRCLED[num.strip()], lines))
            else:
                body_lines.extend(lines)

        full = "\n".join([clean(l) for l in body_lines if clean(l)] + [l for _, ls in para_items for l in ls])
        articles.append({**base, "id": f"{law_name}|{label}", "paragraph": None,
                         "text": full, "text_with_title": f"{prefix}\n{full}"})

        if not para_items:  # 항이 없으면 조문 전체가 한 덩어리
            paragraphs.append({**articles[-1]})
            continue
        intro = "\n".join(clean(l) for l in body_lines if clean(l))
        for num, lines in para_items:
            text = "\n".join(lines)
            paragraphs.append({**base, "id": f"{law_name}|{label}|{num}", "paragraph": num,
                               "text": text,
                               "text_with_title": f"{prefix} 제{num}항\n{text}",
                               "article_intro": intro})
    return articles, paragraphs


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_articles, all_paragraphs = [], []
    for path in sorted(RAW.glob("*.json")):
        arts, paras = parse_law(path)
        all_articles += arts
        all_paragraphs += paras
        print(f"{path.stem}: 조 {len(arts)}개, 항 단위 {len(paras)}개")

    for name, rows in [("chunks_article.jsonl", all_articles), ("chunks_paragraph.jsonl", all_paragraphs)]:
        (OUT / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"\n합계: 조 {len(all_articles)}개, 항 단위 {len(all_paragraphs)}개 → {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
