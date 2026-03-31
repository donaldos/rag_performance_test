from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.vectordb.strategies.base import VectorDBStrategy
from ..state import GraphState
from .nodes import (
    decide_after_grade,
    decide_after_hallucination,
    make_check_hallucination_node,
    make_generate_node,
    make_grade_documents_node,
    make_retrieve_node,
    make_rewrite_query_node,
)


def build_self_rag_graph(
    store: VectorDBStrategy,
    embedding_type: str = "openai_small",
    k: int = 5,
    llm_model: str = "gpt-4o-mini",
):
    """
    Self-RAG 그래프를 구축하고 컴파일된 그래프를 반환한다.

    흐름:
        retrieve
          → grade_documents
              → [relevant]   generate → check_hallucination → [grounded] END
              → [irrelevant] rewrite_query → retrieve (최대 MAX_RETRY)
                                             check_hallucination → [hallucinated] generate (최대 MAX_RETRY)
    """
    retrieve          = make_retrieve_node(store, embedding_type, k)
    grade_documents   = make_grade_documents_node(llm_model)
    rewrite_query     = make_rewrite_query_node(llm_model)
    generate          = make_generate_node(llm_model, tag="Self-RAG")
    check_hallucination = make_check_hallucination_node(llm_model)

    builder = StateGraph(GraphState)
    builder.add_node("retrieve",            retrieve)
    builder.add_node("grade_documents",     grade_documents)
    builder.add_node("rewrite_query",       rewrite_query)
    builder.add_node("generate",            generate)
    builder.add_node("check_hallucination", check_hallucination)

    builder.set_entry_point("retrieve")
    builder.add_edge("retrieve", "grade_documents")
    builder.add_conditional_edges(
        "grade_documents",
        decide_after_grade,
        {"generate": "generate", "rewrite_query": "rewrite_query"},
    )
    builder.add_edge("rewrite_query", "retrieve")
    builder.add_edge("generate", "check_hallucination")
    builder.add_conditional_edges(
        "check_hallucination",
        decide_after_hallucination,
        {"__end__": END, "generate": "generate"},
    )

    return builder.compile()
