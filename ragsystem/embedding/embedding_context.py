from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document

from ragsystem.utils import get_logger

from .router import EmbeddingRouter
from .strategies.base import EmbeddedChunk, EmbeddingStrategy

# config/.env 자동 로드 (OPENAI_API_KEY 등)
_ENV_PATH = Path(__file__).resolve().parents[2] / "config" / ".env"
load_dotenv(_ENV_PATH)

logger = get_logger(__name__)


def _make_strategies() -> dict[str, EmbeddingStrategy]:
    """설치된 의존성만 등록한다. 미설치 패키지는 건너뛴다."""
    strategies: dict[str, EmbeddingStrategy] = {}

    try:
        from .strategies.openai_small_strategy import OpenAISmallEmbeddingStrategy
        strategies["openai_small"] = OpenAISmallEmbeddingStrategy()
        logger.debug("임베딩 전략 등록: openai_small")
    except (ImportError, Exception) as e:
        logger.warning("openai_small 전략 로드 실패 — 제외: %s", e)

    try:
        from .strategies.openai_large_strategy import OpenAILargeEmbeddingStrategy
        strategies["openai_large"] = OpenAILargeEmbeddingStrategy()
        logger.debug("임베딩 전략 등록: openai_large")
    except (ImportError, Exception) as e:
        logger.warning("openai_large 전략 로드 실패 — 제외: %s", e)

    try:
        from .strategies.huggingface_ko_strategy import HuggingFaceKoEmbeddingStrategy
        strategies["huggingface_ko"] = HuggingFaceKoEmbeddingStrategy()
        logger.debug("임베딩 전략 등록: huggingface_ko")
    except (ImportError, Exception) as e:
        logger.warning("huggingface_ko 전략 로드 실패 — 제외: %s", e)

    logger.info("사용 가능한 임베딩 전략: %s", list(strategies.keys()))
    return strategies


class EmbeddingContext:
    """
    Router + Strategy Pattern Context.

    - embedding_type=None  → EmbeddingRouter가 언어를 감지하여 최적 모델 자동 선택
    - embedding_type 명시  → Router 우회, 해당 모델 직접 사용 (Override)

    config/.env의 OPENAI_API_KEY를 자동으로 로드한다.
    상위 파이프라인은 이 클래스만 알면 된다.
    """

    _strategies: dict[str, EmbeddingStrategy] = _make_strategies()
    _router = EmbeddingRouter()

    @classmethod
    def available_embeddings(cls) -> list[str]:
        """현재 사용 가능한 embedding_type 목록을 반환한다."""
        return list(cls._strategies.keys())

    @classmethod
    def EmbeddingChunks(
        cls,
        chunks: list[Document],
        embedding_type: str | None = None,
    ) -> list[EmbeddedChunk]:
        """
        청크 리스트를 임베딩하여 EmbeddedChunk 리스트를 반환한다.

        Args:
            chunks: ChunkingDocs() 반환값 (List[Document])
            embedding_type: 사용할 모델 키. None이면 EmbeddingRouter가 자동 결정.

        Returns:
            List[EmbeddedChunk]
              .document        : 원본 Document (metadata 포함)
              .embedding       : 임베딩 벡터 (List[float])
              .embedding_model : 사용된 모델명
              .embedding_dim   : 벡터 차원 수

        Raises:
            ValueError: 지원하지 않는 embedding_type 명시 시
        """
        logger.debug("EmbeddingChunks 시작: 청크 수=%d, embedding_type=%s", len(chunks), embedding_type)
        auto_routed = embedding_type is None
        detected_language: str | None = None

        if auto_routed:
            detected_language, embedding_type = cls._router.route(chunks)
            logger.info("자동 라우팅: language=%s → embedding_type=%s", detected_language, embedding_type)
        else:
            logger.info("수동 지정: embedding_type=%s", embedding_type)

        if embedding_type not in cls._strategies:
            available = cls.available_embeddings()
            logger.error("지원하지 않는 embedding_type: '%s'. 사용 가능: %s", embedding_type, available)
            raise ValueError(
                f"사용할 수 없는 embedding_type: '{embedding_type}'. "
                f"현재 사용 가능: {available}"
            )

        try:
            embedded = cls._strategies[embedding_type].embed(chunks)
        except Exception as e:
            logger.error("임베딩 실패 [%s]: %s", embedding_type, e, exc_info=True)
            raise

        # 라우팅 메타데이터를 document에 추가
        for ec in embedded:
            ec.document.metadata["embedding_model"] = ec.embedding_model
            ec.document.metadata["embedding_dim"] = ec.embedding_dim
            ec.document.metadata["auto_routed_embedding"] = auto_routed
            if detected_language:
                ec.document.metadata["detected_language"] = detected_language

        logger.info(
            "임베딩 완료: model=%s, 벡터 수=%d, 차원=%d",
            embedded[0].embedding_model if embedded else "N/A",
            len(embedded),
            embedded[0].embedding_dim if embedded else 0,
        )
        return embedded

    @classmethod
    def register(cls, embedding_type: str, strategy: EmbeddingStrategy) -> None:
        """새 임베딩 전략을 런타임에 등록한다 (OCP 준수)."""
        cls._strategies[embedding_type] = strategy
