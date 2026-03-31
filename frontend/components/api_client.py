"""
FastAPI 서버 HTTP 호출 래퍼.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

API_BASE = "http://localhost:8000"
_TIMEOUT = 300  # RAG 호출은 오래 걸릴 수 있음


def upload_pdfs(files: List) -> Dict[str, Any]:
    """POST /upload — 다중 PDF 업로드 → { session_id, file_count, files, pdf_type }"""
    multipart = [
        ("files", (f.name, f.getvalue(), "application/pdf"))
        for f in files
    ]
    resp = requests.post(
        f"{API_BASE}/upload",
        files=multipart,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def run_step(session_id: str, step: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """POST /pipeline/run → { session_id, step, status, summary }"""
    resp = requests.post(
        f"{API_BASE}/pipeline/run",
        json={"session_id": session_id, "step": step, "options": options or {}},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def get_status(session_id: str) -> Dict[str, Any]:
    """GET /pipeline/status/{session_id} → { completed_steps, summary }"""
    resp = requests.get(
        f"{API_BASE}/pipeline/status/{session_id}",
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def ask_rag(
    session_id: str,
    question: str,
    rag_type: str = "self",
    llm_model: str = "gpt-4o-mini",
    k: int = 5,
) -> Dict[str, Any]:
    """POST /rag/ask → { answer, context, relevance, hallucination, ... }"""
    resp = requests.post(
        f"{API_BASE}/rag/ask",
        json={
            "session_id": session_id,
            "question": question,
            "rag_type": rag_type,
            "llm_model": llm_model,
            "k": k,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()
