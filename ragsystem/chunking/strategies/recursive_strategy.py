from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .base import ChunkingStrategy


class RecursiveChunkingStrategy(ChunkingStrategy):
    """단락 → 문장 → 단어 순으로 재귀 분할. 가장 범용적인 기본 전략.

    separators 우선순위: 단락(\\n\\n) → 줄바꿈(\\n) → 공백 → 문자
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, docs: list[Document]) -> list[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
        )
        chunks = splitter.split_documents(docs)
        return self._add_metadata(chunks, "recursive")
