"""
POST /vectordb/search — VectorDB 직접 검색 (LLM 없이 유사 문서 반환).
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from langchain_core.documents import Document
from ragsystem.embedding.embedding_context import EmbeddingContext
from ragsystem.vectordb.vectordb_context import VectorDBContext
from api.services import session as session_svc

router = APIRouter()


class SearchRequest(BaseModel):
    session_id: str
    query: str
    k: int = 5
    embedding_type: Optional[str] = None   # None이면 세션의 임베딩 모델 자동 사용


class SearchHit(BaseModel):
    rank: int
    score: float
    page: int
    source: str
    chunking_type: str
    content: str


class SearchResponse(BaseModel):
    query: str
    hits: List[SearchHit]
    total: int
    embedding_type: str


@router.post("/search")
def search(req: SearchRequest):
    state = session_svc.get_session(req.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    if state.store is None:
        raise HTTPException(status_code=400, detail="VectorDB가 아직 구축되지 않았습니다.")

    # 임베딩 타입 결정 (명시 > 세션 자동 감지)
    embedding_type = req.embedding_type
    if not embedding_type and state.embedded:
        model = state.embedded[0].embedding_model
        if "large" in model:
            embedding_type = "openai_large"
        elif "ko" in model or "korean" in model.lower():
            embedding_type = "huggingface_ko"
        else:
            embedding_type = "openai_small"
    embedding_type = embedding_type or "openai_small"

    # 쿼리 임베딩
    query_embedded = EmbeddingContext.EmbeddingChunks(
        [Document(page_content=req.query)],
        embedding_type=embedding_type,
    )
    query_vec = query_embedded[0].embedding

    # VectorDB 검색
    results = VectorDBContext.Search(state.store, query_vec, k=req.k)

    hits = []
    for r in results:
        meta = r.document.metadata if hasattr(r.document, "metadata") else {}
        hits.append(SearchHit(
            rank=r.rank + 1,
            score=round(r.score, 6),
            page=meta.get("page", 0),
            source=meta.get("source", meta.get("loader_type", "")),
            chunking_type=meta.get("chunking_type", ""),
            content=r.document.page_content,
        ))

    return SearchResponse(
        query=req.query,
        hits=hits,
        total=len(hits),
        embedding_type=embedding_type,
    )
