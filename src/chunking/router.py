from langchain_core.documents import Document

from src.utils import get_logger

logger = get_logger(__name__)


class ChunkingRouter:
    """
    Document 리스트의 pdf_type 메타데이터를 읽어
    최적 chunking_type을 결정하는 라우터.

    route() → (pdf_type, chunking_type) 튜플 반환
    """

    # pdf_type → 우선순위 정렬된 chunking_type 목록 (index 0이 기본값)
    _routing_table: dict[str, list[str]] = {
        "text":  ["recursive", "semantic", "token"],
        "table": ["page", "markdown_header"],
        "graph": ["page"],
        "scan":  ["sentence", "recursive"],
        "mixed": ["recursive", "semantic"],
    }

    _FALLBACK_PDF_TYPE = "text"

    def route(self, docs: list[Document], rank: int = 0) -> tuple[str, str]:
        """
        docs의 첫 번째 Document에서 pdf_type을 읽어 chunking_type을 반환한다.

        Args:
            docs: LoadingPDFDatas() 반환값
            rank: 우선순위 인덱스 (0=기본, 1=폴백, ...)

        Returns:
            (pdf_type, chunking_type) 튜플
        """
        pdf_type = self._FALLBACK_PDF_TYPE
        if docs:
            pdf_type = docs[0].metadata.get("pdf_type", self._FALLBACK_PDF_TYPE)
            logger.debug("메타데이터에서 pdf_type 읽기: %s", pdf_type)
        else:
            logger.warning("빈 docs — pdf_type 기본값 '%s' 사용", self._FALLBACK_PDF_TYPE)

        candidates = self._routing_table.get(pdf_type, ["recursive"])
        chunking_type = candidates[min(rank, len(candidates) - 1)]
        logger.info("라우팅 결정: pdf_type=%s → chunking_type=%s (rank=%d)", pdf_type, chunking_type, rank)
        return pdf_type, chunking_type
