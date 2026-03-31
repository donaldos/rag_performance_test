from __future__ import annotations

from pathlib import Path

from ragsystem.utils import get_logger

from .router import VectorDBRouter
from .strategies.base import SearchResult, VectorDBStrategy

logger = get_logger(__name__)


def _make_strategies() -> dict[str, VectorDBStrategy]:
    """설치된 의존성만 등록한다. 미설치 패키지는 건너뛴다."""
    strategies: dict[str, VectorDBStrategy] = {}

    try:
        from .strategies.faiss_strategy import FAISSVectorDBStrategy
        strategies["faiss"] = FAISSVectorDBStrategy
        logger.debug("VectorDB 전략 등록: faiss")
    except (ImportError, Exception) as e:
        logger.warning("faiss 전략 로드 실패 — 제외: %s", e)

    try:
        from .strategies.chroma_strategy import ChromaDBVectorDBStrategy
        strategies["chromadb"] = ChromaDBVectorDBStrategy
        logger.debug("VectorDB 전략 등록: chromadb")
    except (ImportError, Exception) as e:
        logger.warning("chromadb 전략 로드 실패 — 제외: %s", e)

    logger.info("사용 가능한 VectorDB 전략: %s", list(strategies.keys()))
    return strategies


class VectorDBContext:
    """
    Router + Strategy Pattern Context.

    - vectordb_type=None  → VectorDBRouter가 청크 수로 최적 DB 자동 선택
    - vectordb_type 명시  → Router 우회, 해당 DB 직접 사용 (Override)
    """

    # 전략 클래스 딕셔너리 (인스턴스가 아닌 클래스를 저장)
    _strategy_classes: dict[str, type] = _make_strategies()
    _router = VectorDBRouter()

    @classmethod
    def available_vectordbs(cls) -> list[str]:
        """현재 사용 가능한 vectordb_type 목록을 반환한다."""
        return list(cls._strategy_classes.keys())

    @classmethod
    def BuildVectorDB(
        cls,
        embedded_chunks: list,
        vectordb_type: str | None = None,
        persist_dir: str | Path | None = None,
    ) -> VectorDBStrategy:
        """
        EmbeddedChunk 리스트로 VectorDB 인덱스를 구축한다.

        Args:
            embedded_chunks : EmbeddingContext.EmbeddingChunks() 반환값
            vectordb_type   : "faiss" | "chromadb" | None (자동 라우팅)
            persist_dir     : 저장 디렉터리. None이면 인메모리.

        Returns:
            build()가 완료된 VectorDBStrategy 인스턴스

        Raises:
            ValueError: 지원하지 않는 vectordb_type 명시 시
        """
        logger.debug(
            "BuildVectorDB 시작: 청크 수=%d, vectordb_type=%s, persist_dir=%s",
            len(embedded_chunks), vectordb_type, persist_dir,
        )
        auto_routed = vectordb_type is None
        detected_size: str | None = None

        if auto_routed:
            detected_size, vectordb_type = cls._router.route(embedded_chunks)
            logger.info("자동 라우팅: size_type=%s → vectordb_type=%s", detected_size, vectordb_type)
        else:
            logger.info("수동 지정: vectordb_type=%s", vectordb_type)

        if vectordb_type not in cls._strategy_classes:
            available = cls.available_vectordbs()
            logger.error("지원하지 않는 vectordb_type: '%s'. 사용 가능: %s", vectordb_type, available)
            raise ValueError(
                f"사용할 수 없는 vectordb_type: '{vectordb_type}'. "
                f"현재 사용 가능: {available}"
            )

        StrategyClass = cls._strategy_classes[vectordb_type]

        # ChromaDB는 persist_dir 파라미터를 지원
        if vectordb_type == "chromadb" and persist_dir is not None:
            store = StrategyClass(persist_dir=persist_dir)
        else:
            store = StrategyClass()

        try:
            store.build(embedded_chunks)
        except Exception as e:
            logger.error("VectorDB 구축 실패 [%s]: %s", vectordb_type, e, exc_info=True)
            raise

        logger.info("VectorDB 구축 완료: type=%s, 청크 수=%d", vectordb_type, len(embedded_chunks))
        return store

    @classmethod
    def Search(
        cls,
        store: VectorDBStrategy,
        query_embedding: list[float],
        k: int = 5,
    ) -> list[SearchResult]:
        """
        구축된 VectorDB에서 유사 문서를 검색한다.

        Args:
            store          : BuildVectorDB() 반환값
            query_embedding: 질의 텍스트의 임베딩 벡터
            k              : 반환할 최대 결과 수

        Returns:
            List[SearchResult] (rank 오름차순)
        """
        logger.debug("Search 시작: k=%d, 벡터 차원=%d", k, len(query_embedding))
        try:
            results = store.search(query_embedding, k=k)
        except Exception as e:
            logger.error("검색 실패: %s", e, exc_info=True)
            raise

        if not results:
            logger.warning("검색 결과 없음 (k=%d)", k)
        else:
            logger.info("검색 완료: 결과 수=%d", len(results))
        return results

    @classmethod
    def register(cls, vectordb_type: str, strategy_class: type) -> None:
        """새 VectorDB 전략 클래스를 런타임에 등록한다 (OCP 준수)."""
        cls._strategy_classes[vectordb_type] = strategy_class
