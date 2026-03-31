"""
파이프라인 단계 상태 카드 컴포넌트.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
import streamlit as st

_STATUS_BADGE = {
    "done":    "🟢 완료",
    "running": "🟡 실행 중",
    "error":   "🔴 오류",
    "pending": "⚪ 대기",
}


def step_card(
    title: str,
    status: str,          # "done" | "running" | "error" | "pending"
    summary: Optional[Dict[str, Any]] = None,
) -> None:
    """단계 상태 카드를 렌더링한다."""
    badge = _STATUS_BADGE.get(status, "⚪")
    with st.container(border=True):
        st.markdown(f"**{title}** &nbsp; {badge}")
        if summary:
            cols = st.columns(len(summary))
            for col, (k, v) in zip(cols, summary.items()):
                col.metric(k, v)
