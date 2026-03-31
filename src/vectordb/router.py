from __future__ import annotations

from src.utils import get_logger

logger = get_logger(__name__)


class VectorDBRouter:
    """
    EmbeddedChunk 리스트 크기를 분석하여 최적 vectordb_type을 결정하는 라우터.

    route() → (size_type, vectordb_type) 튜플 반환
    """

    # size_type → 우선순위 정렬된 vectordb_type 목록 (index 0이 기본값)
    _routing_table: dict[str, list[str]] = {
        "small":  ["chromadb", "faiss"],   # < 500 청크: 메타데이터 필터링 유리
        "large":  ["faiss", "chromadb"],   # >= 500 청크: 순수 벡터 검색 성능 우선
    }

    _LARGE_THRESHOLD = 500

    def detect_size_type(self, embedded_chunks: list) -> str:
        """청크 수로 데이터셋 크기 유형을 반환한다.

        Returns:
            "small" — 청크 수 < 500
            "large" — 청크 수 >= 500
        """
        count = len(embedded_chunks)
        size_type = "large" if count >= self._LARGE_THRESHOLD else "small"
        logger.debug("크기 감지: 청크 수=%d → size_type=%s (임계값=%d)", count, size_type, self._LARGE_THRESHOLD)
        return size_type

    def route(self, embedded_chunks: list, rank: int = 0) -> tuple[str, str]:
        """
        청크 수를 기반으로 최적 vectordb_type을 반환한다.

        Args:
            embedded_chunks: EmbeddingContext.EmbeddingChunks() 반환값
            rank: 우선순위 인덱스 (0=기본, 1=폴백)

        Returns:
            (size_type, vectordb_type) 튜플
        """
        size_type = self.detect_size_type(embedded_chunks)
        candidates = self._routing_table.get(size_type, ["faiss"])
        vectordb_type = candidates[min(rank, len(candidates) - 1)]
        logger.info("라우팅 결정: size_type=%s → vectordb_type=%s (rank=%d)", size_type, vectordb_type, rank)
        return size_type, vectordb_type
