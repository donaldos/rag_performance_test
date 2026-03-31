from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.documents import Document


@dataclass
class SearchResult:
    """벡터 검색 결과 단위."""

    document: Document
    score: float        # L2 거리 (낮을수록 유사) 또는 유사도 점수 (높을수록 유사)
    rank: int           # 검색 순위 (0부터 시작)
    vectordb_type: str = field(default="")


class VectorDBStrategy(ABC):
    """모든 VectorDB 전략의 공통 인터페이스."""

    @abstractmethod
    def build(self, embedded_chunks: list) -> None:
        """EmbeddedChunk 리스트로 인덱스를 구축한다."""
        pass

    @abstractmethod
    def search(self, query_embedding: list[float], k: int = 5) -> list[SearchResult]:
        """쿼리 벡터로 유사 문서를 검색한다."""
        pass

    @abstractmethod
    def save(self, path: str | Path) -> Path:
        """인덱스를 디스크에 저장한다. 저장된 디렉터리 경로를 반환한다."""
        pass

    @classmethod
    @abstractmethod
    def load_from(cls, path: str | Path) -> "VectorDBStrategy":
        """디스크에서 인덱스를 로드한다."""
        pass

    @property
    def vectordb_name(self) -> str:
        return self.__class__.__name__

    def __len__(self) -> int:
        return 0
