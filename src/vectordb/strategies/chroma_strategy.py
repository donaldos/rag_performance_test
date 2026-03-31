from __future__ import annotations

import json
from pathlib import Path

from langchain_core.documents import Document

from .base import SearchResult, VectorDBStrategy

_COLLECTION_NAME = "rag_collection"
_META_FILE = "chroma_meta.json"


def _sanitize_metadata(metadata: dict) -> dict:
    """ChromaDB는 str/int/float/bool만 허용 — 나머지는 JSON 문자열로 변환."""
    result = {}
    for k, v in metadata.items():
        if isinstance(v, (str, int, float, bool)):
            result[k] = v
        else:
            result[k] = json.dumps(v, ensure_ascii=False)
    return result


class ChromaDBVectorDBStrategy(VectorDBStrategy):
    """
    ChromaDB 기반 벡터 인덱스 전략.

    - 인메모리(기본) 또는 영구 저장(persist_dir 지정) 모드
    - 코사인 유사도 사용 (높을수록 유사, 반환 score는 1-distance)
    - build() 후 save()로 persist_dir에 보존
    """

    def __init__(self, persist_dir: str | Path | None = None) -> None:
        self._persist_dir = Path(persist_dir) if persist_dir else None
        self._client = None
        self._collection = None
        self._doc_count: int = 0

    # ─── 구축 ────────────────────────────────────────────────────────────────

    def build(self, embedded_chunks: list) -> None:
        import chromadb

        if self._persist_dir:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self._persist_dir))
        else:
            self._client = chromadb.EphemeralClient()

        # 기존 컬렉션 초기화
        try:
            self._client.delete_collection(_COLLECTION_NAME)
        except Exception:
            pass

        self._collection = self._client.create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        ids = [str(i) for i in range(len(embedded_chunks))]
        embeddings = [ec.embedding for ec in embedded_chunks]
        documents = [ec.document.page_content for ec in embedded_chunks]
        metadatas = [_sanitize_metadata(ec.document.metadata) for ec in embedded_chunks]

        # ChromaDB는 최대 5461개씩 배치 추가
        batch = 5000
        for start in range(0, len(ids), batch):
            self._collection.add(
                ids=ids[start:start + batch],
                embeddings=embeddings[start:start + batch],
                documents=documents[start:start + batch],
                metadatas=metadatas[start:start + batch],
            )

        self._doc_count = len(embedded_chunks)

    # ─── 검색 ────────────────────────────────────────────────────────────────

    def search(self, query_embedding: list[float], k: int = 5) -> list[SearchResult]:
        if self._collection is None:
            raise RuntimeError("build()를 먼저 호출하세요.")

        k = min(k, self._doc_count)
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        results = []
        docs = result["documents"][0]
        metas = result["metadatas"][0]
        dists = result["distances"][0]

        for rank, (doc_text, meta, dist) in enumerate(zip(docs, metas, dists)):
            # cosine space에서 distance 범위: 0(동일) ~ 2(반대)
            # 유사도로 변환: 1 - dist/2 → 0~1
            score = 1.0 - dist / 2.0
            results.append(SearchResult(
                document=Document(page_content=doc_text, metadata=meta),
                score=score,
                rank=rank,
                vectordb_type="chromadb",
            ))
        return results

    # ─── 저장 / 로드 ──────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        if self._persist_dir and self._persist_dir == path:
            # PersistentClient는 자동 저장됨
            pass
        else:
            # persist_dir 재설정하여 저장
            import chromadb
            path.mkdir(parents=True, exist_ok=True)
            new_client = chromadb.PersistentClient(path=str(path))
            try:
                new_client.delete_collection(_COLLECTION_NAME)
            except Exception:
                pass
            new_col = new_client.create_collection(
                name=_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            if self._collection is not None:
                existing = self._collection.get(include=["embeddings", "documents", "metadatas"])
                if existing["ids"]:
                    new_col.add(
                        ids=existing["ids"],
                        embeddings=existing["embeddings"],
                        documents=existing["documents"],
                        metadatas=existing["metadatas"],
                    )

        meta = {"persist_dir": str(path), "doc_count": self._doc_count}
        (path / _META_FILE).write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )
        return path

    @classmethod
    def load_from(cls, path: str | Path) -> "ChromaDBVectorDBStrategy":
        import chromadb

        path = Path(path)
        obj = cls(persist_dir=path)
        obj._client = chromadb.PersistentClient(path=str(path))
        obj._collection = obj._client.get_collection(_COLLECTION_NAME)

        meta_path = path / _META_FILE
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            obj._doc_count = meta.get("doc_count", obj._collection.count())
        else:
            obj._doc_count = obj._collection.count()
        return obj

    # ─── 유틸 ────────────────────────────────────────────────────────────────

    @property
    def vectordb_name(self) -> str:
        return "chromadb"

    def __len__(self) -> int:
        return self._doc_count
