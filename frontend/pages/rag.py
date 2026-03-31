"""
Tab 3 — RAG 질의 및 결과 비교.
"""
from __future__ import annotations

import streamlit as st
from frontend.components import api_client
from frontend.components.result_table import result_table


def _session_id() -> str:
    return st.session_state.get("session_id", "")


def _render_answer(res: dict) -> None:
    """단일 RAG 결과를 렌더링한다."""
    st.subheader("답변")
    st.write(res.get("answer", ""))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("소요 시간", f"{res.get('elapsed_ms', 0):.0f}ms")
    col2.metric("재시도", res.get("retry_count", 0))
    col3.metric("관련성", res.get("relevance") or "-")
    col4.metric("환각", res.get("hallucination") or "-")

    if res.get("route"):
        st.caption(f"라우팅 결과: `{res['route']}`")

    st.subheader("참조 문서")
    result_table(res.get("context", []))


def render() -> None:
    st.header("Step 6 — RAG 질의")

    if not _session_id():
        st.warning("먼저 PDF를 업로드하고 파이프라인을 실행하세요.")
        return

    completed = st.session_state.get("completed_steps", [])
    if "vectordb" not in completed:
        st.warning("VectorDB 구축이 완료되어야 질의할 수 있습니다 (Tab 2).")
        return

    # ── 질의 설정 ────────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    rag_type  = col1.radio("워크플로우", ["simple", "self", "adaptive"], horizontal=True)
    llm_model = col2.selectbox("LLM 모델", ["gpt-4o-mini", "gpt-4o"])
    k         = col3.slider("검색 문서 수 (k)", 1, 20, 5)

    question = st.text_area("질문을 입력하세요", height=80)

    tab_single, tab_compare = st.tabs(["단일 질의", "3가지 비교"])

    # ── 단일 질의 탭 ─────────────────────────────────────────────────────────────
    with tab_single:
        if st.button("질의", type="primary", key="btn_single", disabled=not question.strip()):
            with st.spinner(f"{rag_type.upper()} RAG 실행 중..."):
                try:
                    res = api_client.ask_rag(_session_id(), question, rag_type, llm_model, k)
                except Exception as e:
                    st.error(f"오류: {e}")
                    return
            st.session_state["last_answer"] = res
            _render_answer(res)

        elif st.session_state.get("last_answer"):
            _render_answer(st.session_state["last_answer"])

    # ── 3가지 비교 탭 ────────────────────────────────────────────────────────────
    with tab_compare:
        if st.button("3가지 모두 실행", type="primary", key="btn_compare", disabled=not question.strip()):
            results = {}
            for rt in ["simple", "self", "adaptive"]:
                with st.spinner(f"{rt.upper()} RAG 실행 중..."):
                    try:
                        results[rt] = api_client.ask_rag(_session_id(), question, rt, llm_model, k)
                    except Exception as e:
                        results[rt] = {"error": str(e)}

            cols = st.columns(3)
            for col, rt in zip(cols, ["simple", "self", "adaptive"]):
                with col:
                    st.subheader(f"{rt.upper()} RAG")
                    if "error" in results.get(rt, {}):
                        st.error(results[rt]["error"])
                    else:
                        r = results[rt]
                        st.write(r.get("answer", ""))
                        st.caption(
                            f"소요: {r.get('elapsed_ms', 0):.0f}ms | "
                            f"환각: {r.get('hallucination') or '-'} | "
                            f"관련성: {r.get('relevance') or '-'}"
                        )
