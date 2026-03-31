from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.vectordb.strategies.base import VectorDBStrategy
from ..state import GraphState
from .nodes import make_generate_node, make_retrieve_node


def build_simple_rag_graph(
    store: VectorDBStrategy,
    embedding_type: str = "openai_small",
    k: int = 5,
    llm_model: str = "gpt-4o-mini",
):
    """
    Simple RAG 그래프를 구축하고 컴파일된 그래프를 반환한다.

    흐름: retrieve → generate → END
    """
    retrieve = make_retrieve_node(store, embedding_type, k)
    generate = make_generate_node(llm_model)

    builder = StateGraph(GraphState)
    builder.add_node("retrieve", retrieve)
    builder.add_node("generate", generate)

    builder.set_entry_point("retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)

    return builder.compile()
