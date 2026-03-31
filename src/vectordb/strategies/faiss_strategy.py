from __future__ import annotations

import json
from pathlib import Path

from langchain_core.documents import Document

from .base import SearchResult, VectorDBStrategy

_INDEX_FILE = "index.faiss"
_DOCS_FILE = "documents.json"


class FAISSVectorDBStrategy(VectorDBStrategy):
    """
    FAISS 기반 벡터 인덱스 전략.

    - 인메모리 IndexFlatL2 사용 (L2 거리, 낮을수록 유사)
    - build() 후 save()로 디스크 저장 가능
    - load_from()으로 복원 가능
    """

    def __init__(self) -> None:
        self._index = None
        self._documents: list[Document] = []
        self._dim: int = 0

    # ─── 구축 ────────────────────────────────────────────────────────────────

    def build(self, embedded_chunks: list) -> None:
        import faiss
        import numpy as np

        vectors = [ec.embedding for ec in embedded_chunks]
        self._documents = [ec.document for ec in embedded_chunks]
        self._dim = len(vectors[0]) if vectors else 0

        mat = np.array(vectors, dtype=np.float32)
        self._index = faiss.IndexFlatL2(self._dim)
        self._index.add(mat)

    # ─── 검색 ────────────────────────────────────────────────────────────────

    def search(self, query_embedding: list[float], k: int = 5) -> list[SearchResult]:
        if self._index is None:
            raise RuntimeError("build()를 먼저 호출하세요.")
        import numpy as np

        k = min(k, len(self._documents))
        query = np.array([query_embedding], dtype=np.float32)
        distances, indices = self._index.search(query, k)

        results = []
        for rank, (idx, dist) in enumerate(zip(indices[0], distances[0])):
            if idx < 0:
                continue
            results.append(SearchResult(
                document=self._documents[idx],
                score=float(dist),
                rank=rank,
                vectordb_type="faiss",
            ))
        return results

    # ─── 저장 / 로드 ──────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> Path:
        import faiss

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self._index, str(path / _INDEX_FILE))

        docs_payload = [
            {"page_content": doc.page_content, "metadata": doc.metadata}
            for doc in self._documents
        ]
        (path / _DOCS_FILE).write_text(
            json.dumps(docs_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    @classmethod
    def load_from(cls, path: str | Path) -> "FAISSVectorDBStrategy":
        import faiss

        path = Path(path)
        obj = cls()
        obj._index = faiss.read_index(str(path / _INDEX_FILE))
        obj._dim = obj._index.d

        raw = json.loads((path / _DOCS_FILE).read_text(encoding="utf-8"))
        obj._documents = [
            Document(page_content=item["page_content"], metadata=item["metadata"])
            for item in raw
        ]
        return obj

    # ─── 유틸 ────────────────────────────────────────────────────────────────

    @property
    def vectordb_name(self) -> str:
        return "faiss"

    def __len__(self) -> int:
        return len(self._documents)
