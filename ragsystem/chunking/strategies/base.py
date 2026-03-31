from abc import ABC, abstractmethod

from langchain_core.documents import Document


class ChunkingStrategy(ABC):
    """모든 청킹 전략의 공통 인터페이스."""

    @abstractmethod
    def chunk(self, docs: list[Document]) -> list[Document]:
        """Document 리스트를 청킹하여 반환한다."""
        pass

    def _add_metadata(
        self, chunks: list[Document], chunking_type: str
    ) -> list[Document]:
        """공통 메타데이터(chunking_type, chunk_index)를 추가한다."""
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunking_type"] = chunking_type
            chunk.metadata["chunk_index"] = i
        return chunks
