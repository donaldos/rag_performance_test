"""
ragsystem 각 단계를 호출하고 SessionState를 갱신한다.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from dotenv import load_dotenv
load_dotenv("config/.env")

from ragsystem.loading.pdf.loader_context import PDFLoaderContext
from ragsystem.chunking.chunking_context import ChunkingContext
from ragsystem.embedding.embedding_context import EmbeddingContext
from ragsystem.vectordb.vectordb_context import VectorDBContext

from api.services.session import SessionState
from api.models.pipeline import StepSummary


def run_loading(state: SessionState, options: Optional[Dict[str, Any]] = None) -> StepSummary:
    loader_type = (options or {}).get("loader_type") or None
    t0 = time.time()

    # 다중 PDF를 각각 로딩한 후 합산
    all_docs = []
    for path in state.pdf_paths:
        docs = PDFLoaderContext.LoadingPDFDatas(path, loader_type=loader_type)
        all_docs.extend(docs)

    elapsed = (time.time() - t0) * 1000

    state.docs = all_docs
    state.pdf_type = all_docs[0].metadata.get("pdf_type", "") if all_docs else ""
    if "loading" not in state.completed_steps:
        state.completed_steps.append("loading")

    detected_loader = all_docs[0].metadata.get("loader_type", loader_type or "auto") if all_docs else "auto"
    summary = StepSummary(
        doc_count=len(all_docs),
        loader_type=detected_loader,
        pdf_type=state.pdf_type,
        elapsed_ms=round(elapsed, 1),
    )
    state.summary["loading"] = {
        "doc_count": summary.doc_count,
        "loader_type": summary.loader_type,
        "pdf_type": summary.pdf_type,
        "file_count": len(state.pdf_paths),
    }
    return summary


def run_chunking(state: SessionState, options: Optional[Dict[str, Any]] = None) -> StepSummary:
    chunking_type = (options or {}).get("chunking_type") or None
    t0 = time.time()
    chunks = ChunkingContext.ChunkingDocs(
        state.docs,
        chunking_type=chunking_type,
    )
    elapsed = (time.time() - t0) * 1000

    state.chunks = chunks
    if "chunking" not in state.completed_steps:
        state.completed_steps.append("chunking")

    detected_chunker = chunks[0].metadata.get("chunking_type", chunking_type or "auto") if chunks else "auto"
    avg_size = int(sum(len(c.page_content) for c in chunks) / len(chunks)) if chunks else 0
    summary = StepSummary(
        chunk_count=len(chunks),
        avg_chunk_size=avg_size,
        chunking_type=detected_chunker,
        elapsed_ms=round(elapsed, 1),
    )
    state.summary["chunking"] = {
        "chunk_count": summary.chunk_count,
        "avg_chunk_size": summary.avg_chunk_size,
        "chunking_type": summary.chunking_type,
    }
    return summary


def run_embedding(state: SessionState, options: Optional[Dict[str, Any]] = None) -> StepSummary:
    embedding_type = (options or {}).get("embedding_type") or None
    t0 = time.time()
    embedded = EmbeddingContext.EmbeddingChunks(state.chunks, embedding_type=embedding_type)
    elapsed = (time.time() - t0) * 1000

    state.embedded = embedded
    if "embedding" not in state.completed_steps:
        state.completed_steps.append("embedding")

    first = embedded[0] if embedded else None
    summary = StepSummary(
        vector_count=len(embedded),
        dim=first.embedding_dim if first else None,
        model=first.embedding_model if first else None,
        language=first.document.metadata.get("language", "") if first else None,
        elapsed_ms=round(elapsed, 1),
    )
    state.summary["embedding"] = {
        "vector_count": summary.vector_count,
        "dim": summary.dim,
        "model": summary.model,
    }
    return summary


def run_vectordb(state: SessionState, options: Optional[Dict[str, Any]] = None) -> StepSummary:
    vectordb_type = (options or {}).get("vectordb_type") or None
    t0 = time.time()
    store = VectorDBContext.BuildVectorDB(state.embedded, vectordb_type=vectordb_type)
    elapsed = (time.time() - t0) * 1000

    state.store = store
    if "vectordb" not in state.completed_steps:
        state.completed_steps.append("vectordb")

    db_type = type(store).__name__.lower().replace("strategy", "").replace("vectordb", "")
    summary = StepSummary(
        db_type=vectordb_type or db_type,
        index_size=len(state.embedded),
        elapsed_ms=round(elapsed, 1),
    )
    state.summary["vectordb"] = {
        "db_type": summary.db_type,
        "index_size": summary.index_size,
    }
    return summary
