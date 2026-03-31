"""
Tab 2 — 파이프라인 실행 (Loading → Chunking → Embedding → VectorDB).
"""
from __future__ import annotations

import streamlit as st
from frontend.components import api_client
from frontend.components.step_card import step_card


def _session_id() -> str:
    return st.session_state.get("session_id", "")


def _completed() -> list:
    return st.session_state.get("completed_steps", [])


def _mark_done(step: str) -> None:
    steps = st.session_state.get("completed_steps", [])
    if step not in steps:
        steps.append(step)
    st.session_state["completed_steps"] = steps


def render() -> None:
    st.header("Step 2~5 — 파이프라인 실행")

    if not _session_id():
        st.warning("먼저 PDF를 업로드하세요 (Tab 1).")
        return

    # ── 현재 상태 카드 ──────────────────────────────────────────────────────────
    try:
        status_res = api_client.get_status(_session_id())
        completed = status_res.get("completed_steps", [])
        summary   = status_res.get("summary", {})
        st.session_state["completed_steps"] = completed
    except Exception:
        completed = _completed()
        summary   = {}

    col1, col2, col3, col4 = st.columns(4)
    for col, step in zip([col1, col2, col3, col4], ["loading", "chunking", "embedding", "vectordb"]):
        with col:
            s = "done" if step in completed else "pending"
            step_card(step.capitalize(), s, summary.get(step))

    st.divider()

    # ── Step 2: Loading ─────────────────────────────────────────────────────────
    with st.expander("Step 2 — Loading", expanded="loading" not in completed):
        loader_options = ["자동 감지", "pymupdf", "pdfplumber", "camelot", "tabula",
                          "unstructured", "llamaparse", "tesseract", "textract", "azure_di"]
        loader_sel = st.selectbox("로더 선택", loader_options, key="loader_sel")
        loader_type = None if loader_sel == "자동 감지" else loader_sel

        if st.button("Loading 실행", disabled="loading" in completed):
            with st.spinner("Loading 중..."):
                try:
                    res = api_client.run_step(_session_id(), "loading", {"loader_type": loader_type})
                except Exception as e:
                    st.error(f"오류: {e}")
                    return
            if res["status"] == "success":
                _mark_done("loading")
                s = res["summary"]
                col1, col2, col3 = st.columns(3)
                col1.metric("문서 수", s.get("doc_count"))
                col2.metric("로더", s.get("loader_type"))
                col3.metric("소요 시간", f"{s.get('elapsed_ms', 0):.0f}ms")
                st.success("Loading 완료!")
                st.rerun()
            else:
                st.error(res.get("error", "알 수 없는 오류"))

    # ── Step 3: Chunking ────────────────────────────────────────────────────────
    with st.expander("Step 3 — Chunking", expanded="loading" in completed and "chunking" not in completed):
        chunker_options = ["자동 선택", "recursive", "token", "sentence",
                           "semantic", "page", "markdown_header", "parent_child"]
        chunker_sel  = st.selectbox("청킹 전략", chunker_options, key="chunker_sel")
        chunking_type = None if chunker_sel == "자동 선택" else chunker_sel

        disabled = "loading" not in completed or "chunking" in completed
        if st.button("Chunking 실행", disabled=disabled):
            with st.spinner("Chunking 중..."):
                try:
                    res = api_client.run_step(_session_id(), "chunking", {
                        "chunking_type": chunking_type,
                    })
                except Exception as e:
                    st.error(f"오류: {e}")
                    return
            if res["status"] == "success":
                _mark_done("chunking")
                s = res["summary"]
                col1, col2, col3 = st.columns(3)
                col1.metric("청크 수", s.get("chunk_count"))
                col2.metric("평균 크기", f"{s.get('avg_chunk_size', 0)}자")
                col3.metric("소요 시간", f"{s.get('elapsed_ms', 0):.0f}ms")
                st.success("Chunking 완료!")
                st.rerun()
            else:
                st.error(res.get("error", "알 수 없는 오류"))

    # ── Step 4: Embedding ───────────────────────────────────────────────────────
    with st.expander("Step 4 — Embedding", expanded="chunking" in completed and "embedding" not in completed):
        embed_options = ["자동 감지", "openai_small", "openai_large", "huggingface_ko"]
        embed_sel     = st.selectbox("임베딩 모델", embed_options, key="embed_sel")
        embedding_type = None if embed_sel == "자동 감지" else embed_sel

        disabled = "chunking" not in completed or "embedding" in completed
        if st.button("Embedding 실행", disabled=disabled):
            with st.spinner("Embedding 중... (시간이 걸릴 수 있습니다)"):
                try:
                    res = api_client.run_step(_session_id(), "embedding", {"embedding_type": embedding_type})
                except Exception as e:
                    st.error(f"오류: {e}")
                    return
            if res["status"] == "success":
                _mark_done("embedding")
                s = res["summary"]
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("벡터 수", s.get("vector_count"))
                col2.metric("차원", s.get("dim"))
                col3.metric("모델", s.get("model", "")[:20])
                col4.metric("소요 시간", f"{s.get('elapsed_ms', 0):.0f}ms")
                st.success("Embedding 완료!")
                st.rerun()
            else:
                st.error(res.get("error", "알 수 없는 오류"))

    # ── Step 5: VectorDB ────────────────────────────────────────────────────────
    with st.expander("Step 5 — VectorDB", expanded="embedding" in completed and "vectordb" not in completed):
        db_options  = ["자동 선택", "chromadb", "faiss"]
        db_sel      = st.selectbox("VectorDB", db_options, key="db_sel")
        vectordb_type = None if db_sel == "자동 선택" else db_sel

        disabled = "embedding" not in completed or "vectordb" in completed
        if st.button("VectorDB 구축", disabled=disabled):
            with st.spinner("VectorDB 구축 중..."):
                try:
                    res = api_client.run_step(_session_id(), "vectordb", {"vectordb_type": vectordb_type})
                except Exception as e:
                    st.error(f"오류: {e}")
                    return
            if res["status"] == "success":
                _mark_done("vectordb")
                s = res["summary"]
                col1, col2, col3 = st.columns(3)
                col1.metric("DB 종류", s.get("db_type"))
                col2.metric("인덱스 크기", s.get("index_size"))
                col3.metric("소요 시간", f"{s.get('elapsed_ms', 0):.0f}ms")
                st.success("VectorDB 구축 완료! RAG 질의 탭으로 이동하세요.")
                st.rerun()
            else:
                st.error(res.get("error", "알 수 없는 오류"))
