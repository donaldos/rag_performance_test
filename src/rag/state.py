from __future__ import annotations

from typing import List
from typing_extensions import TypedDict

from langchain_core.documents import Document


class GraphState(TypedDict):
    """RAG 워크플로우 전체에서 공유되는 상태."""

    # 공통
    question: str            # 사용자 질문 (rewrite_query에서 교체될 수 있음)
    context: List[Document]  # 검색된 문서 청크
    answer: str              # 생성된 최종 답변
    retry_count: int         # 재시도 횟수 (rewrite → retrieve 루프 횟수)

    # Self-RAG / Adaptive-RAG 전용
    relevance: str           # "relevant" | "irrelevant" | "" — grade_documents 결과
    hallucination: str       # "grounded" | "hallucinated" | "" — check_hallucination 결과

    # Adaptive-RAG 전용
    route: str               # "vectorstore" | "general" | "" — route_question 결과
