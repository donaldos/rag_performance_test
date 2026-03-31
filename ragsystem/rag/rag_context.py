from __future__ import annotations

from typing import Literal

from langchain_core.documents import Document

from ragsystem.utils import get_logger
from ragsystem.vectordb.strategies.base import VectorDBStrategy
from .state import GraphState

logger = get_logger(__name__)

RagType = Literal["simple", "self", "adaptive"]


class RAGContext:
    """
    외부 파라미터로 RAG 워크플로우를 선택하는 통합 진입점.

    rag_type="simple"   → Simple RAG  : retrieve → generate
    rag_type="self"     → Self-RAG    : + grade_documents, rewrite_query, check_hallucination
    rag_type="adaptive" → Adaptive RAG: + route_question, direct_generate
    """

    @classmethod
    def build_graph(
        cls,
        store: VectorDBStrategy,
        rag_type: RagType = "self",
        embedding_type: str = "openai_small",
        k: int = 5,
        llm_model: str = "gpt-4o-mini",
    ):
        """컴파일된 LangGraph 그래프를 반환한다."""
        logger.info(
            "RAG 그래프 구축: rag_type=%s, llm=%s, k=%d, embedding=%s",
            rag_type, llm_model, k, embedding_type,
        )
        if rag_type == "simple":
            from .simple_rag.graph import build_simple_rag_graph
            return build_simple_rag_graph(store, embedding_type, k, llm_model)
        elif rag_type == "self":
            from .self_rag.graph import build_self_rag_graph
            return build_self_rag_graph(store, embedding_type, k, llm_model)
        elif rag_type == "adaptive":
            from .adaptive_rag.graph import build_adaptive_rag_graph
            return build_adaptive_rag_graph(store, embedding_type, k, llm_model)
        else:
            raise ValueError(
                f"지원하지 않는 rag_type: '{rag_type}'. 사용 가능: simple | self | adaptive"
            )

    @classmethod
    def ask(
        cls,
        store: VectorDBStrategy,
        question: str,
        rag_type: RagType = "self",
        embedding_type: str = "openai_small",
        k: int = 5,
        llm_model: str = "gpt-4o-mini",
    ) -> dict:
        """
        질문을 입력받아 RAG 워크플로우를 실행하고 결과를 반환한다.

        Args:
            store          : VectorDBContext.BuildVectorDB() 반환값
            question       : 사용자 질문
            rag_type       : "simple" | "self" | "adaptive"
            embedding_type : 쿼리 임베딩 모델
            k              : 검색할 문서 수
            llm_model      : 생성 LLM 모델명

        Returns:
            dict with keys:
                answer       : 최종 답변 (str)
                context      : 검색된 Document 리스트
                question     : 실제 사용된 질문 (재작성 후 변경될 수 있음)
                rag_type     : 사용된 워크플로우 종류
                retry_count  : 재시도 횟수
                relevance    : grade_documents 결과 (self/adaptive)
                hallucination: check_hallucination 결과 (self/adaptive)
                route        : route_question 결과 (adaptive)
        """
        graph = cls.build_graph(store, rag_type, embedding_type, k, llm_model)

        initial_state: GraphState = {
            "question": question,
            "context": [],
            "answer": "",
            "retry_count": 0,
            "relevance": "",
            "hallucination": "",
            "route": "",
        }

        logger.info("RAG 실행 시작: rag_type=%s, question=%.60s", rag_type, question)
        result = graph.invoke(initial_state)
        result["rag_type"] = rag_type
        logger.info(
            "RAG 실행 완료: answer=%d자, retry=%d",
            len(result.get("answer", "")),
            result.get("retry_count", 0),
        )
        return result
