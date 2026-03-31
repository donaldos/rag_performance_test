"""
POST /rag/ask — VectorDB에 질문하고 LLM 답변을 반환한다.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from ragsystem.rag.rag_context import RAGContext
from api.models.rag import RagRequest, RagResponse, ContextItem
from api.services import session as session_svc

router = APIRouter()


@router.post("/ask")
def ask_rag(req: RagRequest):
    state = session_svc.get_session(req.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    if state.store is None:
        raise HTTPException(status_code=400, detail="VectorDB가 아직 구축되지 않았습니다.")

    # 임베딩 모델 결정 (embedding 단계에서 사용한 모델 재사용)
    embedding_type = "openai_small"
    if state.embedded:
        model = state.embedded[0].embedding_model
        if "large" in model:
            embedding_type = "openai_large"
        elif "ko" in model or "korean" in model.lower():
            embedding_type = "huggingface_ko"

    t0 = time.time()
    result = RAGContext.ask(
        store=state.store,
        question=req.question,
        rag_type=req.rag_type,
        embedding_type=embedding_type,
        k=req.k,
        llm_model=req.llm_model,
    )
    elapsed_ms = (time.time() - t0) * 1000

    # context 문서 → ContextItem 변환
    context_items = []
    for i, doc in enumerate(result.get("context", []), 1):
        score = doc.metadata.get("score", 0.0) if hasattr(doc, "metadata") else 0.0
        page = doc.metadata.get("page", 0) if hasattr(doc, "metadata") else 0
        content = doc.page_content if hasattr(doc, "page_content") else str(doc)
        context_items.append(ContextItem(rank=i, score=score, page=page, content=content))

    return RagResponse(
        answer=result.get("answer", ""),
        rag_type=result.get("rag_type", req.rag_type),
        retry_count=result.get("retry_count", 0),
        relevance=result.get("relevance") or None,
        hallucination=result.get("hallucination") or None,
        route=result.get("route") or None,
        context=context_items,
        elapsed_ms=round(elapsed_ms, 1),
    )
