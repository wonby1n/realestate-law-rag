"""질문 다듬기 (명세: docs/specs/003-query-normalize.md)."""

import re

# 일상어 → 법률 용어. 덧붙이기만 한다.
# 출처: 실무 = 본인이 주택개발팀에서 임차인 응대하며 듣던 말 / 화면 = 화면 테스트에서 실패한 질문
SYNONYMS = {
    "월세": "차임",            # 화면 2026-11-20
    "집주인": "임대인",        # 실무
    "건물주": "임대인",        # 실무
    "세입자": "임차인",        # 실무
    "세입": "임차인",
    "올리": "증액",            # 화면 2026-11-20 ("올린대", "올려도")
    "올린": "증액",
    "인상": "증액",            # 실무
    "내리": "감액",            # 실무
    "깎": "감액",
    "재계약": "갱신",          # 화면 2026-11-20
    "연장": "갱신",            # 실무
    "전세금": "보증금",        # 실무
    "부동산": "중개",          # 실무 ("부동산 수수료")
    "복비": "중개보수",        # 실무
    "수수료": "보수",
    "나가라": "갱신 거절",     # 실무 ("집주인이 나가래요")
    "나가래": "갱신 거절",
}

# 금액·날짜·기간·비율. 조문 번호(제7조, 제6조의3)는 숫자 앞에 '제'나 '의'가 붙어 있어 걸리지 않는다.
NUMBER_EXPR = re.compile(r"(?<![제의\d,.])\d[\d,.]*\s*(만\s*원|천\s*원|억|원|년|개월|월|일|%|퍼센트|프로)?")


def normalize(question: str) -> tuple[str, list[str]]:
    changes = []
    removed = [m.group().strip() for m in NUMBER_EXPR.finditer(question) if m.group().strip()]
    text = NUMBER_EXPR.sub(" ", question)
    if removed:
        changes.append("뺀 숫자: " + ", ".join(removed))

    added = []
    for word, legal in SYNONYMS.items():
        if word in text and legal not in added:
            added.append(legal)
            changes.append(f"{word} → {legal}")
    if added:
        text += " " + " ".join(added)
    return re.sub(r"\s+", " ", text).strip(), changes
