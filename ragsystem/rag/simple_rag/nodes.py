from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from ragsystem.embedding.embedding_context import EmbeddingContext
from ragsystem.utils import get_logger
from ragsystem.vectordb.strategies.base import VectorDBStrategy
from ragsystem.vectordb.vectordb_context import VectorDBContext
from ..state import GraphState

logger = get_logger(__name__)

_GENERATE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 PDF 문서를 기반으로 질문에 답변하는 AI 어시스턴트입니다.
아래 문서 내용만을 참고하여 질문에 명확하고 정확하게 답변하세요.
문서에 없는 내용은 "문서에서 찾을 수 없습니다"라고 답하세요.

[문서 내용]
{context}"""),
    ("human", "{question}"),
])


def make_retrieve_node(
    store: VectorDBStrategy,
    embedding_type: str = "openai_small",
    k: int = 5,
):
    """retrieve 노드 팩토리: VectorDB에서 관련 문서를 검색한다."""

    def retrieve(state: GraphState) -> dict:
        question = state["question"]
        logger.info("[Simple-RAG] retrieve 시작: question=%.60s", question)

        query_embedded = EmbeddingContext.EmbeddingChunks(
            [Document(page_content=question)],
            embedding_type=embedding_type,
        )
        query_vec = query_embedded[0].embedding
        results = VectorDBContext.Search(store, query_vec, k=k)
        docs = [r.document for r in results]

        logger.info("[Simple-RAG] retrieve 완료: %d개 문서", len(docs))
        return {"context": docs}

    return retrieve


def make_generate_node(llm_model: str = "gpt-4o-mini"):
    """generate 노드 팩토리: 검색된 Context로 LLM 답변을 생성한다."""
    llm = ChatOpenAI(model=llm_model, temperature=0)
    chain = _GENERATE_PROMPT | llm

    def generate(state: GraphState) -> dict:
        logger.info("[Simple-RAG] generate 시작: context=%d개", len(state["context"]))
        context_text = "\n\n---\n\n".join(doc.page_content for doc in state["context"])
        response = chain.invoke({
            "context": context_text,
            "question": state["question"],
        })
        answer = response.content
        logger.info("[Simple-RAG] generate 완료: %d자", len(answer))
        return {"answer": answer}

    return generate
