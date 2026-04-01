"""
Tab 4 — VectorDB 직접 검색 (LLM 없이 유사 문서 원문 확인).
"""
from __future__ import annotations

import streamlit as st
from frontend.components.api_client import search_vectordb


def render() -> None:
    st.header("VectorDB 직접 검색")
    st.caption("LLM 없이 쿼리와 가장 유사한 청크를 원문 그대로 확인합니다.")

    if not st.session_state.get("session_id"):
        st.warning("먼저 PDF를 업로드하고 파이프라인을 실행하세요.")
        return

    completed = st.session_state.get("completed_steps", [])
    if "vectordb" not in completed:
        st.warning("VectorDB 구축이 완료되어야 검색할 수 있습니다 (파이프라인 탭).")
        return

    # ── 검색 설정 ──────────────────────────────────────────────────────────────
    col1, col2 = st.columns([4, 1])
    query = col1.text_input("검색어를 입력하세요")
    k     = col2.number_input("k (결과 수)", min_value=1, max_value=20, value=5)

    if not (st.button("검색", type="primary") and query.strip()):
        return

    with st.spinner("VectorDB 검색 중..."):
        try:
            res = search_vectordb(st.session_state["session_id"], query, k=k)
        except Exception as e:
            st.error(f"검색 실패: {e}")
            return

    hits = res.get("hits", [])
    st.success(f"검색 완료 — {res.get('total', 0)}개 결과  |  임베딩 모델: `{res.get('embedding_type', '')}`")

    if not hits:
        st.info("결과가 없습니다.")
        return

    # ── 결과 테이블 ─────────────────────────────────────────────────────────────
    st.subheader("검색 결과")

    for hit in hits:
        rank          = hit["rank"]
        score         = hit["score"]
        page          = hit["page"]
        chunking_type = hit.get("chunking_type", "")
        content       = hit["content"]

        with st.expander(
            f"**Rank {rank}** &nbsp;|&nbsp; score: `{score:.6f}` &nbsp;|&nbsp; page: {page} &nbsp;|&nbsp; chunker: {chunking_type}",
            expanded=(rank == 1),
        ):
            st.text(content)
            st.caption(f"문자 수: {len(content)}자")
