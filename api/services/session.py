"""
세션별 파이프라인 상태를 in-memory로 관리한다.

세션 TTL: 1시간. get_session() 호출 시 만료된 세션을 정리한다.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

SESSION_TTL_HOURS = 1

# ── 타입 aliase (ragsystem 임포트 회피) ───────────────────────────────────────
Document = Any
EmbeddedChunk = Any
VectorStore = Any


@dataclass
class SessionState:
    session_id: str
    pdf_path: str
    pdf_type: str = ""
    docs: List[Document] = field(default_factory=list)
    chunks: List[Document] = field(default_factory=list)
    embedded: List[EmbeddedChunk] = field(default_factory=list)
    store: Optional[VectorStore] = None
    completed_steps: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime = field(default_factory=datetime.utcnow)


# ── In-memory 저장소 ──────────────────────────────────────────────────────────
_sessions: Dict[str, SessionState] = {}


def create_session(pdf_path: str) -> SessionState:
    session_id = str(uuid.uuid4())[:8]
    state = SessionState(session_id=session_id, pdf_path=pdf_path)
    _sessions[session_id] = state
    return state


def get_session(session_id: str) -> Optional[SessionState]:
    _cleanup_expired()
    state = _sessions.get(session_id)
    if state:
        state.last_used = datetime.utcnow()
    return state


def _cleanup_expired() -> None:
    threshold = datetime.utcnow() - timedelta(hours=SESSION_TTL_HOURS)
    expired = [sid for sid, s in _sessions.items() if s.last_used < threshold]
    for sid in expired:
        del _sessions[sid]
