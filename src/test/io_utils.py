"""Document 직렬화/역직렬화 유틸리티."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from langchain_core.documents import Document


def save_documents(
    docs: list[Document],
    path: str | Path,
    *,
    pdf_path: str = "",
    loader_type: str = "",
) -> Path:
    """List[Document]를 JSON 파일로 저장한다.

    JSON 구조:
    {
      "pdf_path": "...",
      "loader_type": "pymupdf",
      "created_at": "2026-03-30T12:00:00",
      "doc_count": 12,
      "documents": [
        {"page_content": "...", "metadata": {...}},
        ...
      ]
    }
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "pdf_path": pdf_path,
        "loader_type": loader_type,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "doc_count": len(docs),
        "documents": [
            {"page_content": doc.page_content, "metadata": doc.metadata}
            for doc in docs
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_documents(path: str | Path) -> tuple[list[Document], dict]:
    """JSON 파일에서 List[Document]를 복원한다.

    Returns:
        (docs, meta) 튜플
        meta: pdf_path, loader_type, created_at, doc_count
    """
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    docs = [
        Document(
            page_content=item["page_content"],
            metadata=item["metadata"],
        )
        for item in payload.get("documents", [])
    ]

    meta = {k: payload[k] for k in ("pdf_path", "loader_type", "created_at", "doc_count") if k in payload}
    return docs, meta


def default_save_path(pdf_path: str, loader_type: str, stage: str = "loading") -> Path:
    """저장 경로 자동 생성: src/test/output/{stem}_{loader_type}_{stage}.json"""
    stem = Path(pdf_path).stem if pdf_path else "unknown"
    return Path(__file__).parent / "output" / f"{stem}_{loader_type}_{stage}.json"


def load_embedded_chunks(path: str | Path):
    """임베딩 결과 JSON 파일에서 EmbeddedChunk 리스트를 복원한다.

    Returns:
        (embedded_chunks, meta) 튜플
        meta: input_path, embedder, created_at, chunk_count, embedding_dim, embedding_model
    """
    from src.embedding.strategies.base import EmbeddedChunk

    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    embedded_chunks = [
        EmbeddedChunk(
            document=Document(
                page_content=item["page_content"],
                metadata=item["metadata"],
            ),
            embedding=item["embedding"],
            embedding_model=item["embedding_model"],
        )
        for item in payload.get("chunks", [])
    ]

    meta = {
        k: payload[k]
        for k in ("input_path", "embedder", "created_at", "chunk_count", "embedding_dim", "embedding_model")
        if k in payload
    }
    return embedded_chunks, meta
