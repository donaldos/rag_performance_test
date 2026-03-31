from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from .base import ChunkingStrategy


class SemanticChunkingStrategy(ChunkingStrategy):
    """임베딩 유사도로 의미 경계를 감지하여 분할. 의미 손실이 가장 적음.
    langchain-experimental 및 임베딩 모델 필요.

    breakpoint_threshold_type:
      "percentile"       — 기본값. 거리 분포의 상위 X%를 경계로 사용
      "standard_deviation" — 평균 + N*표준편차를 경계로 사용
      "interquartile"    — IQR 기반 이상치를 경계로 사용
    """

    def __init__(
        self,
        embeddings: Embeddings,
        breakpoint_threshold_type: str = "percentile",
        breakpoint_threshold_amount: float = 95.0,
    ):
        self.embeddings = embeddings
        self.breakpoint_threshold_type = breakpoint_threshold_type
        self.breakpoint_threshold_amount = breakpoint_threshold_amount

    def chunk(self, docs: list[Document]) -> list[Document]:
        from langchain_experimental.text_splitter import SemanticChunker

        splitter = SemanticChunker(
            embeddings=self.embeddings,
            breakpoint_threshold_type=self.breakpoint_threshold_type,
            breakpoint_threshold_amount=self.breakpoint_threshold_amount,
        )
        chunks = splitter.split_documents(docs)
        return self._add_metadata(chunks, "semantic")
