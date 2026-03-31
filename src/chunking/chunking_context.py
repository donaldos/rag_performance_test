from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from src.utils import get_logger

from .router import ChunkingRouter
from .strategies.base import ChunkingStrategy

logger = get_logger(__name__)


def _make_strategies(embeddings: Embeddings | None = None) -> dict[str, ChunkingStrategy]:
    """설치된 의존성만 등록한다. 미설치 라이브러리는 건너뛴다."""
    strategies: dict[str, ChunkingStrategy] = {}

    try:
        from .strategies.recursive_strategy import RecursiveChunkingStrategy
        strategies["recursive"] = RecursiveChunkingStrategy()
        logger.debug("청킹 전략 등록: recursive")
    except ImportError:
        logger.warning("langchain-text-splitters 미설치 — recursive 전략 제외")

    try:
        from .strategies.token_strategy import TokenChunkingStrategy
        strategies["token"] = TokenChunkingStrategy()
        logger.debug("청킹 전략 등록: token")
    except ImportError:
        logger.warning("tiktoken 미설치 — token 전략 제외")

    try:
        from .strategies.sentence_strategy import SentenceChunkingStrategy
        strategies["sentence"] = SentenceChunkingStrategy()
        logger.debug("청킹 전략 등록: sentence")
    except ImportError:
        logger.warning("sentence-transformers 미설치 — sentence 전략 제외")

    try:
        from .strategies.page_strategy import PageChunkingStrategy
        strategies["page"] = PageChunkingStrategy()
        logger.debug("청킹 전략 등록: page")
    except ImportError:
        logger.warning("page 전략 로드 실패 — 제외")

    try:
        from .strategies.markdown_header_strategy import MarkdownHeaderChunkingStrategy
        strategies["markdown_header"] = MarkdownHeaderChunkingStrategy()
        logger.debug("청킹 전략 등록: markdown_header")
    except ImportError:
        logger.warning("markdown_header 전략 로드 실패 — 제외")

    try:
        from .strategies.parent_child_strategy import ParentChildChunkingStrategy
        strategies["parent_child"] = ParentChildChunkingStrategy()
        logger.debug("청킹 전략 등록: parent_child")
    except ImportError:
        logger.warning("parent_child 전략 로드 실패 — 제외")

    # semantic: 임베딩 모델이 주입된 경우에만 등록
    if embeddings is not None:
        try:
            from .strategies.semantic_strategy import SemanticChunkingStrategy
            strategies["semantic"] = SemanticChunkingStrategy(embeddings=embeddings)
            logger.debug("청킹 전략 등록: semantic")
        except ImportError:
            logger.warning("langchain-experimental 미설치 — semantic 전략 제외")

    logger.info("사용 가능한 청킹 전략: %s", list(strategies.keys()))
    return strategies


class ChunkingContext:
    """
    Router + Strategy Pattern Context.

    - chunking_type=None  → ChunkingRouter가 pdf_type을 읽어 최적 전략 자동 선택
    - chunking_type 명시  → Router 우회, 해당 전략 직접 사용 (Override)
    - semantic 사용 시    → set_embeddings()로 임베딩 모델 주입 필요

    상위 파이프라인은 이 클래스만 알면 된다.
    """

    _strategies: dict[str, ChunkingStrategy] = _make_strategies()
    _router = ChunkingRouter()

    @classmethod
    def set_embeddings(cls, embeddings: Embeddings) -> None:
        """semantic 전략에 사용할 임베딩 모델을 주입한다."""
        from .strategies.semantic_strategy import SemanticChunkingStrategy
        cls._strategies["semantic"] = SemanticChunkingStrategy(embeddings=embeddings)

    @classmethod
    def available_chunkers(cls) -> list[str]:
        """현재 사용 가능한 chunking_type 목록을 반환한다."""
        return list(cls._strategies.keys())

    @classmethod
    def ChunkingDocs(
        cls,
        docs: list[Document],
        chunking_type: str | None = None,
    ) -> list[Document]:
        """
        Document 리스트를 청킹하여 반환한다.

        Args:
            docs: LoadingPDFDatas() 반환값 (List[Document])
            chunking_type: 사용할 전략 키. None이면 ChunkingRouter가 자동 결정.

        Returns:
            List[Document]
              metadata["chunking_type"] : 실제 사용된 전략
              metadata["chunk_index"]   : 청크 순번
              metadata["chunk_role"]    : "parent" | "child" (parent_child 전략 시)
              metadata["parent_id"]     : 부모 청크 인덱스 (parent_child 전략 시)

        Raises:
            ValueError: 지원하지 않는 chunking_type 명시 시
        """
        logger.debug("ChunkingDocs 시작: 문서 수=%d, chunking_type=%s", len(docs), chunking_type)
        auto_routed = chunking_type is None

        if auto_routed:
            pdf_type, chunking_type = cls._router.route(docs)
            logger.info("자동 라우팅: pdf_type=%s → chunking_type=%s", pdf_type, chunking_type)
        else:
            logger.info("수동 지정: chunking_type=%s", chunking_type)

        if chunking_type not in cls._strategies:
            available = cls.available_chunkers()
            logger.error("지원하지 않는 chunking_type: '%s'. 사용 가능: %s", chunking_type, available)
            raise ValueError(
                f"사용할 수 없는 chunking_type: '{chunking_type}'. "
                f"현재 사용 가능: {available}"
            )

        try:
            chunks = cls._strategies[chunking_type].chunk(docs)
        except Exception as e:
            logger.error("청킹 실패 [%s]: %s", chunking_type, e, exc_info=True)
            raise

        for chunk in chunks:
            chunk.metadata["auto_routed_chunking"] = auto_routed

        logger.info("청킹 완료: strategy=%s, 청크 수=%d", chunking_type, len(chunks))
        return chunks

    @classmethod
    def register(cls, chunking_type: str, strategy: ChunkingStrategy) -> None:
        """새 청킹 전략을 런타임에 등록한다 (OCP 준수)."""
        cls._strategies[chunking_type] = strategy
