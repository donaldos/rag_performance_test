from __future__ import annotations

from langchain_core.documents import Document

from .base import EmbeddedChunk, EmbeddingStrategy


class HuggingFaceKoEmbeddingStrategy(EmbeddingStrategy):
    """HuggingFace 한국어 특화 임베딩. 로컬 실행, 무료.
    모델: jhgan/ko-sroberta-multitask  차원: 768
    첫 실행 시 자동 다운로드 (~117MB) → ~/.cache/huggingface/

    model_name 변경으로 다른 HuggingFace 모델도 사용 가능:
      - "BM-K/KoSimCSE-roberta"              ← 한국어 유사도 특화
      - "intfloat/multilingual-e5-large"     ← 다국어 고성능 (560MB)
      - "paraphrase-multilingual-MiniLM-L12-v2" ← 다국어 경량
    """

    DEFAULT_MODEL = "jhgan/ko-sroberta-multitask"

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        from langchain_huggingface import HuggingFaceEmbeddings
        self.model_name = model_name
        self._model = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    def embed(self, chunks: list[Document]) -> list[EmbeddedChunk]:
        texts = [c.page_content for c in chunks]
        vectors = self._model.embed_documents(texts)
        return [
            EmbeddedChunk(document=chunk, embedding=vec, embedding_model=self.model_name)
            for chunk, vec in zip(chunks, vectors)
        ]

    def _model_name(self) -> str:
        return self.model_name
