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
from links import law_url  # noqa: E402
from query import normalize  # noqa: E402
from search_bm25 import Searcher  # noqa: E402
from search_dense import DenseSearcher, HybridSearcher, RerankSearcher  # noqa: E402

LOGS = ROOT / "logs"
DISCLAIMER = "※ 참고용이며 법률 자문이 아닙니다. 근거 조문과 시행일을 직접 확인하세요."

st.set_page_config(page_title="부동산 법령 질문", page_icon="🏠")


METHODS = {"임베딩 (기본, E03 최고)": "dense", "하이브리드 (BM25 + 임베딩)": "hybrid", "하이브리드 + 리랭커": "rerank", "BM25": "bm25"}


@st.cache_resource
def get_searcher(method: str, unit: str, with_title: bool):
    if method == "rerank":
        return RerankSearcher(unit)
    if method == "hybrid":
        return HybridSearcher(unit)
    if method == "dense":
        return DenseSearcher(unit)
    return Searcher(unit, with_title)


with st.sidebar:
    role = st.radio("내 역할", ["임차인", "임대인", "시행사", "시공사", "잘 모름"])
    st.caption("역할은 아직 검색에 반영하지 않고 기록만 합니다 (실험 3 전).")
    st.divider()
    st.subheader("검색 설정")
    method_label = st.radio("검색 방식", list(METHODS))
    method = METHODS[method_label]
    unit = st.radio("쪼갠 단위", ["조", "항"], horizontal=True)
    with_title = st.toggle("법령명·조문 제목 붙이기 (BM25만)", value=True, disabled=method != "bm25")
    use_norm = st.toggle("질문 다듬기 (일상어→법률 용어, 숫자 빼기)", value=True)
    st.caption("하이브리드는 BM25 쪽에만 질문 다듬기를 씁니다.")
    if st.button("대화 지우기"):
        st.session_state.messages = []

st.title("부동산 법령 질문")

if "messages" not in st.session_state:
    st.session_state.messages = []


def render_hits(hits: list[dict], changes: list[str], method_label: str) -> None:
    if changes:
        st.caption("질문 다듬기: " + " / ".join(changes))
    if not hits:
        st.write("맞는 조문을 찾지 못했습니다.")
        return
    st.write(f"검색된 조문 상위 {len(hits)}개 ({method_label})")
    for h in hits:
        para = f" 제{h['paragraph']}항" if h.get("paragraph") else ""
        label = f"{h['law']} {h['article']}({h['title']}){para} · 점수 {h['score']:.3g}"
        with st.expander(label):
            st.markdown(f"[국가법령정보센터에서 보기 ↗]({law_url(h['law'], h['article'])}) · "
                        f"시행일 {h['effective_date']} · {h['chapter']}")
            st.text(h["text"])


for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        if m["role"] == "user":
            st.write(m["content"])
        else:
            render_hits(m["hits"], m.get("changes", []), m.get("method", "BM25"))
            st.caption(DISCLAIMER)

if question := st.chat_input("예: 2025년 3월 1일에 계약했는데 갱신 요구할 수 있나요?"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    query, changes = normalize(question) if use_norm else (question, [])
    if method in ("hybrid", "rerank"):  # 하이브리드는 안에서 BM25 쪽만 다듬음
        query = question
    with st.spinner("검색 중 (처음에는 모델을 불러오느라 시간이 걸립니다)"):
        results = get_searcher(method, unit, with_title).search(query, k=5)
    hits = [{**c, "score": s} for c, s in results]
    st.session_state.messages.append({"role": "assistant", "hits": hits, "changes": changes, "method": method_label})
    with st.chat_message("assistant"):
        render_hits(hits, changes, method_label)
        st.caption(DISCLAIMER)

    LOGS.mkdir(exist_ok=True)
    log = {"time": datetime.now().isoformat(timespec="seconds"), "question": question, "role": role, "method": method,
           "unit": unit, "with_title": with_title, "normalize": use_norm, "query": query, "hits": [h["id"] for h in hits]}
    with (LOGS / f"chat_{datetime.now():%Y%m%d}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(log, ensure_ascii=False) + "\n")
