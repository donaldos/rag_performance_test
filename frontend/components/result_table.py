"""
RAG 검색 결과 테이블 컴포넌트.
"""
from __future__ import annotations

from typing import Any, Dict, List
import streamlit as st


def result_table(context: List[Dict[str, Any]]) -> None:
    """참조 문서 목록을 expander 형태로 렌더링한다."""
    if not context:
        st.info("참조 문서가 없습니다.")
        return

    for ctx in context:
        rank  = ctx.get("rank", "?")
        page  = ctx.get("page", "?")
        score = ctx.get("score", 0.0)
        content = ctx.get("content", "")
        with st.expander(f"[Rank {rank}]  page: {page}  |  score: {score:.4f}"):
            st.text(content)
