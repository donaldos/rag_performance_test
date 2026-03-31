from langchain_core.documents import Document
from langchain_text_splitters import SentenceTransformersTokenTextSplitter

from .base import ChunkingStrategy


class SentenceChunkingStrategy(ChunkingStrategy):
    """문장 경계를 보존하며 분할. OCR 오류가 섞인 스캔 PDF에 유리.

    model_name: SentenceTransformers 호환 모델
    """

    def __init__(
        self,
        chunk_overlap: int = 0,
        tokens_per_chunk: int = 256,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ):
        self.chunk_overlap = chunk_overlap
        self.tokens_per_chunk = tokens_per_chunk
        self.model_name = model_name

    def chunk(self, docs: list[Document]) -> list[Document]:
        splitter = SentenceTransformersTokenTextSplitter(
            chunk_overlap=self.chunk_overlap,
            tokens_per_chunk=self.tokens_per_chunk,
            model_name=self.model_name,
        )
        chunks = splitter.split_documents(docs)
        return self._add_metadata(chunks, "sentence")
