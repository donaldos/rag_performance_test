from __future__ import annotations

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from ragsystem.utils import get_logger
from ..state import GraphState

# Self-RAG 노드 전체 재사용 (retrieve, grade, rewrite, generate, check_hallucination)
from ..self_rag.nodes import (  # noqa: F401  (re-export)
    decide_after_grade,
    decide_after_hallucination,
    make_check_hallucination_node,
    make_generate_node,
    make_grade_documents_node,
    make_retrieve_node,
    make_rewrite_query_node,
)

logger = get_logger(__name__)


# ── Pydantic structured output 모델 ─────────────────────────────────────────

class RouteQuestion(BaseModel):
    """질문 유형 분류 결과."""
    datasource: Literal["vectorstore", "general"] = Field(
        description=(
            "PDF/문서 내용 검색이 필요하면 'vectorstore', "
            "일반 지식으로 직접 답변 가능하면 'general'"
        )
    )


# ── Adaptive 전용 노드 팩토리 ────────────────────────────────────────────────

_ROUTE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """사용자 질문을 보고 PDF 문서 검색이 필요한지 판단하세요.

- 특정 문서 내용, 수치, 사실 확인, 논문·보고서 관련 질문 → 'vectorstore'
- 일반 상식, 개념 설명, 문서와 무관한 질문 → 'general'
"""),
    ("human", "{question}"),
])

_DIRECT_GENERATE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 도움이 되는 AI 어시스턴트입니다. 질문에 명확하고 간결하게 답변하세요."),
    ("human", "{question}"),
])


def make_route_question_node(llm_model: str = "gpt-4o-mini"):
    """route_question 노드 팩토리: 질문 유형을 분류해 vectorstore/general로 분기한다."""
    llm = ChatOpenAI(model=llm_model, temperature=0)
    router = (_ROUTE_PROMPT | llm.with_structured_output(RouteQuestion))

    def route_question(state: GraphState) -> dict:
        question = state["question"]
        logger.info("[Adaptive-RAG] route_question 시작: question=%.60s", question)

        result: RouteQuestion = router.invoke({"question": question})
        logger.info("[Adaptive-RAG] route_question 결과: %s", result.datasource)
        return {"route": result.datasource}

    return route_question


def make_direct_generate_node(llm_model: str = "gpt-4o-mini"):
    """direct_generate 노드 팩토리: 문서 검색 없이 LLM이 직접 답변한다."""
    llm = ChatOpenAI(model=llm_model, temperature=0)
    chain = _DIRECT_GENERATE_PROMPT | llm

    def direct_generate(state: GraphState) -> dict:
        logger.info("[Adaptive-RAG] direct_generate 시작 (문서 검색 없이)")
        response = chain.invoke({"question": state["question"]})
        answer = response.content
        logger.info("[Adaptive-RAG] direct_generate 완료: %d자", len(answer))
        # 직접 답변은 문서 근거 없이 생성되므로 hallucination 체크 생략
        return {"answer": answer, "hallucination": "grounded"}

    return direct_generate


# ── 엣지 조건 함수 ───────────────────────────────────────────────────────────

def decide_route(state: GraphState) -> Literal["retrieve", "direct_generate"]:
    """route_question 이후: vectorstore → retrieve, general → direct_generate."""
    return "retrieve" if state["route"] == "vectorstore" else "direct_generate"
