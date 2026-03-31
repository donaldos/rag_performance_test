from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from langchain_core.documents import Document


@dataclass
class EmbeddedChunk:
    """청크 + 임베딩 벡터를 함께 보관하는 데이터 클래스."""

    document: Document
    embedding: list[float]
    embedding_model: str
    embedding_dim: int = field(init=False)

    def __post_init__(self) -> None:
        self.embedding_dim = len(self.embedding)


class EmbeddingStrategy(ABC):
    """모든 임베딩 전략의 공통 인터페이스."""

    @abstractmethod
    def embed(self, chunks: list[Document]) -> list[EmbeddedChunk]:
        """청크 리스트를 임베딩하여 EmbeddedChunk 리스트로 반환한다."""
        pass

    def _model_name(self) -> str:
        """MLflow 로깅용 모델 식별자."""
        return self.__class__.__name__
