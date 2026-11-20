"""채팅 화면 (명세: docs/specs/001-chat-ui.md).

실행: .venv/bin/streamlit run app/chat.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from search_bm25 import Searcher  # noqa: E402

LOGS = ROOT / "logs"
DISCLAIMER = "※ 참고용이며 법률 자문이 아닙니다. 근거 조문과 시행일을 직접 확인하세요."

st.set_page_config(page_title="부동산 법령 질문", page_icon="🏠")


@st.cache_resource
def get_searcher(unit: str, with_title: bool) -> Searcher:
    return Searcher(unit, with_title)


with st.sidebar:
    role = st.radio("내 역할", ["임차인", "임대인", "시행사", "시공사", "잘 모름"])
    st.caption("역할은 아직 검색에 반영하지 않고 기록만 합니다 (실험 3 전).")
    st.divider()
    st.subheader("검색 설정")
    unit = st.radio("쪼갠 단위", ["조", "항"], horizontal=True)
    with_title = st.toggle("법령명·조문 제목 붙이기", value=True)
    if st.button("대화 지우기"):
        st.session_state.messages = []

st.title("부동산 법령 질문")

if "messages" not in st.session_state:
    st.session_state.messages = []


def render_hits(hits: list[dict]) -> None:
    if not hits:
        st.write("맞는 조문을 찾지 못했습니다.")
        return
    st.write(f"검색된 조문 상위 {len(hits)}개 (BM25)")
    for h in hits:
        para = f" 제{h['paragraph']}항" if h.get("paragraph") else ""
        label = f"{h['law']} {h['article']}({h['title']}){para} · 점수 {h['score']:.1f}"
        with st.expander(label):
            st.caption(f"시행일 {h['effective_date']} · {h['chapter']}")
            st.text(h["text"])


for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        if m["role"] == "user":
            st.write(m["content"])
        else:
            render_hits(m["hits"])
            st.caption(DISCLAIMER)

if question := st.chat_input("예: 2025년 3월 1일에 계약했는데 갱신 요구할 수 있나요?"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    results = get_searcher(unit, with_title).search(question, k=5)
    hits = [{**c, "score": s} for c, s in results]
    st.session_state.messages.append({"role": "assistant", "hits": hits})
    with st.chat_message("assistant"):
        render_hits(hits)
        st.caption(DISCLAIMER)

    LOGS.mkdir(exist_ok=True)
    log = {"time": datetime.now().isoformat(timespec="seconds"), "question": question, "role": role,
           "unit": unit, "with_title": with_title, "hits": [h["id"] for h in hits]}
    with (LOGS / f"chat_{datetime.now():%Y%m%d}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(log, ensure_ascii=False) + "\n")
