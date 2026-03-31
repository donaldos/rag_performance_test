from __future__ import annotations

import re

from langchain_core.documents import Document

from src.utils import get_logger

logger = get_logger(__name__)


class EmbeddingRouter:
    """
    청크 내용의 언어 비율을 분석하여 최적 embedding_type을 결정하는 라우터.

    route() → (language, embedding_type) 튜플 반환
    """

    # language → 우선순위 정렬된 embedding_type 목록 (index 0이 기본값)
    _routing_table: dict[str, list[str]] = {
        "ko":    ["huggingface_ko", "openai_small"],
        "en":    ["openai_small", "openai_large"],
        "mixed": ["openai_small", "huggingface_ko"],
    }

    # 한국어 판별 기준: 전체 문자 중 한글 비율이 이 값 이상이면 한국어
    _KO_RATIO_THRESHOLD = 0.20

    _KO_PATTERN = re.compile(r"[가-힣]")

    def detect_language(self, chunks: list[Document]) -> str:
        """청크 샘플에서 한글 비율을 측정하여 언어를 반환한다.

        Returns:
            "ko"    — 한글 비율 ≥ 20%
            "mixed" — 한글 비율 5~20%
            "en"    — 한글 비율 < 5%
        """
        # 최대 5개 청크, 각 500자 샘플링
        sample = " ".join(c.page_content[:500] for c in chunks[:5])
        total = len(sample.replace(" ", ""))
        if total == 0:
            logger.warning("샘플 텍스트 없음 — 언어 기본값 'en' 사용")
            return "en"

        ko_count = len(self._KO_PATTERN.findall(sample))
        ratio = ko_count / total
        logger.debug("언어 감지: 샘플 길이=%d, 한글 수=%d, 비율=%.3f", total, ko_count, ratio)

        if ratio >= self._KO_RATIO_THRESHOLD:
            language = "ko"
        elif ratio >= 0.05:
            language = "mixed"
        else:
            language = "en"

        logger.info("언어 감지 결과: %s (한글 비율=%.1f%%)", language, ratio * 100)
        return language

    def route(self, chunks: list[Document], rank: int = 0) -> tuple[str, str]:
        """
        청크 언어를 감지하여 최적 embedding_type을 반환한다.

        Args:
            chunks: ChunkingDocs() 반환값
            rank: 우선순위 인덱스 (0=기본, 1=폴백, ...)

        Returns:
            (language, embedding_type) 튜플
        """
        language = self.detect_language(chunks)
        candidates = self._routing_table.get(language, ["openai_small"])
        embedding_type = candidates[min(rank, len(candidates) - 1)]
        logger.info("라우팅 결정: language=%s → embedding_type=%s (rank=%d)", language, embedding_type, rank)
        return language, embedding_type
