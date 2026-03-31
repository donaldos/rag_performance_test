from __future__ import annotations

from typing import Literal

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.embedding.embedding_context import EmbeddingContext
from src.utils import get_logger
from src.vectordb.strategies.base import VectorDBStrategy
from src.vectordb.vectordb_context import VectorDBContext
from ..state import GraphState

logger = get_logger(__name__)

MAX_RETRY = 2  # rewrite_query → retrieve 최대 반복 횟수

# ── Pydantic structured output 모델 ─────────────────────────────────────────

class GradeDocuments(BaseModel):
    """문서 관련성 평가 결과."""
    binary_score: Literal["relevant", "irrelevant"] = Field(
        description="문서가 질문과 관련 있으면 'relevant', 없으면 'irrelevant'"
    )


class GradeHallucination(BaseModel):
    """환각 여부 평가 결과."""
    binary_score: Literal["grounded", "hallucinated"] = Field(
        description="답변이 문서에 근거하면 'grounded', 근거 없이 생성되면 'hallucinated'"
    )


# ── 공통 프롬프트 ────────────────────────────────────────────────────────────

_GRADE_DOCS_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "다음 문서가 사용자 질문과 관련이 있는지 판단하세요. "
     "관련 있으면 'relevant', 없으면 'irrelevant'로만 답하세요."),
    ("human", "질문: {question}\n\n문서 내용:\n{document}"),
])

_REWRITE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "사용자 질문을 벡터 검색에 더 적합하도록 재작성하세요. "
     "핵심 키워드를 명확히 하고 질문의 의도를 유지하세요. 재작성된 질문만 출력하세요."),
    ("human", "원래 질문: {question}"),
])

_GENERATE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 PDF 문서를 기반으로 질문에 답변하는 AI 어시스턴트입니다.
아래 문서 내용만을 참고하여 질문에 명확하고 정확하게 답변하세요.
문서에 없는 내용은 "문서에서 찾을 수 없습니다"라고 답하세요.

[문서 내용]
{context}"""),
    ("human", "{question}"),
])

_HALLUCINATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "아래 답변이 제공된 문서 내용에만 근거하는지 평가하세요. "
     "문서에 근거하면 'grounded', 문서에 없는 내용을 포함하면 'hallucinated'로만 답하세요."),
    ("human", "문서 내용:\n{context}\n\n생성된 답변:\n{answer}"),
])


# ── 노드 팩토리 ──────────────────────────────────────────────────────────────

def make_retrieve_node(
    store: VectorDBStrategy,
    embedding_type: str = "openai_small",
    k: int = 5,
):
    def retrieve(state: GraphState) -> dict:
        question = state["question"]
        logger.info("[Self-RAG] retrieve 시작: question=%.60s", question)

        query_embedded = EmbeddingContext.EmbeddingChunks(
            [Document(page_content=question)],
            embedding_type=embedding_type,
        )
        query_vec = query_embedded[0].embedding
        results = VectorDBContext.Search(store, query_vec, k=k)
        docs = [r.document for r in results]

        logger.info("[Self-RAG] retrieve 완료: %d개 문서", len(docs))
        return {"context": docs}

    return retrieve


def make_grade_documents_node(llm_model: str = "gpt-4o-mini"):
    llm = ChatOpenAI(model=llm_model, temperature=0)
    grader = (_GRADE_DOCS_PROMPT | llm.with_structured_output(GradeDocuments))

    def grade_documents(state: GraphState) -> dict:
        question = state["question"]
        docs = state["context"]
        logger.info("[Self-RAG] grade_documents 시작: %d개 문서 평가", len(docs))

        relevant_docs = []
        for doc in docs:
            result: GradeDocuments = grader.invoke({
                "question": question,
                "document": doc.page_content,
            })
            if result.binary_score == "relevant":
                relevant_docs.append(doc)

        relevance = "relevant" if relevant_docs else "irrelevant"
        logger.info(
            "[Self-RAG] grade_documents 결과: %s (%d/%d 관련)",
            relevance, len(relevant_docs), len(docs),
        )
        return {"context": relevant_docs, "relevance": relevance}

    return grade_documents


def make_rewrite_query_node(llm_model: str = "gpt-4o-mini"):
    llm = ChatOpenAI(model=llm_model, temperature=0)
    chain = _REWRITE_PROMPT | llm

    def rewrite_query(state: GraphState) -> dict:
        retry_count = state.get("retry_count", 0)
        logger.info("[Self-RAG] rewrite_query 시작: retry=%d", retry_count)

        response = chain.invoke({"question": state["question"]})
        new_question = response.content.strip()

        logger.info("[Self-RAG] 재작성된 질문: %.80s", new_question)
        return {"question": new_question, "retry_count": retry_count + 1}

    return rewrite_query


def make_generate_node(llm_model: str = "gpt-4o-mini", tag: str = "Self-RAG"):
    llm = ChatOpenAI(model=llm_model, temperature=0)
    chain = _GENERATE_PROMPT | llm

    def generate(state: GraphState) -> dict:
        logger.info("[%s] generate 시작: context=%d개", tag, len(state["context"]))
        context_text = "\n\n---\n\n".join(doc.page_content for doc in state["context"])
        response = chain.invoke({
            "context": context_text,
            "question": state["question"],
        })
        answer = response.content
        logger.info("[%s] generate 완료: %d자", tag, len(answer))
        return {"answer": answer}

    return generate


def make_check_hallucination_node(llm_model: str = "gpt-4o-mini"):
    llm = ChatOpenAI(model=llm_model, temperature=0)
    checker = (_HALLUCINATION_PROMPT | llm.with_structured_output(GradeHallucination))

    def check_hallucination(state: GraphState) -> dict:
        logger.info("[Self-RAG] check_hallucination 시작")
        context_text = "\n\n---\n\n".join(doc.page_content for doc in state["context"])
        result: GradeHallucination = checker.invoke({
            "context": context_text,
            "answer": state["answer"],
        })
        logger.info("[Self-RAG] check_hallucination 결과: %s", result.binary_score)
        return {"hallucination": result.binary_score}

    return check_hallucination


# ── 엣지 조건 함수 ───────────────────────────────────────────────────────────

def decide_after_grade(state: GraphState) -> Literal["generate", "rewrite_query"]:
    """grade_documents 이후: relevant → generate, irrelevant → rewrite_query (최대 MAX_RETRY)."""
    if state["relevance"] == "relevant":
        return "generate"
    if state.get("retry_count", 0) >= MAX_RETRY:
        logger.warning("[Self-RAG] 최대 재시도(%d) 초과 → generate 강제 진행", MAX_RETRY)
        return "generate"
    return "rewrite_query"


def decide_after_hallucination(state: GraphState) -> Literal["__end__", "generate"]:
    """check_hallucination 이후: grounded → END, hallucinated → generate 재시도."""
    if state["hallucination"] == "grounded":
        return "__end__"
    if state.get("retry_count", 0) >= MAX_RETRY:
        logger.warning("[Self-RAG] 최대 재시도(%d) 초과 → 현재 답변 반환", MAX_RETRY)
        return "__end__"
    # 환각 발생 시 retry_count 증가 후 재생성
    return "generate"
