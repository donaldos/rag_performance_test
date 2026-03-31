from __future__ import annotations

from langchain_core.documents import Document

from .base import EmbeddedChunk, EmbeddingStrategy


class OpenAILargeEmbeddingStrategy(EmbeddingStrategy):
    """OpenAI text-embedding-3-large. 최고 정확도.
    차원: 3072  비용: $0.13/1M 토큰
    환경변수 OPENAI_API_KEY 필요 (config/.env).
    """

    MODEL = "text-embedding-3-large"

    def __init__(self) -> None:
        from langchain_openai import OpenAIEmbeddings
        self._model = OpenAIEmbeddings(model=self.MODEL)

    def embed(self, chunks: list[Document]) -> list[EmbeddedChunk]:
        texts = [c.page_content for c in chunks]
        vectors = self._model.embed_documents(texts)
        return [
            EmbeddedChunk(document=chunk, embedding=vec, embedding_model=self.MODEL)
            for chunk, vec in zip(chunks, vectors)
        ]

    def _model_name(self) -> str:
        return self.MODEL
