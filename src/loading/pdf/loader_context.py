from __future__ import annotations

from langchain_core.documents import Document

from src.utils import get_logger

from .router import PDFTypeRouter
from .strategies.base import PDFLoaderStrategy

logger = get_logger(__name__)


def _make_strategies() -> dict[str, PDFLoaderStrategy]:
    """
    설치된 의존성만 등록한다.
    미설치 라이브러리는 ImportError를 무시하고 건너뛴다.
    """
    strategies: dict[str, PDFLoaderStrategy] = {}

    try:
        from .strategies.pymupdf_strategy import PyMuPDFLoaderStrategy
        strategies["pymupdf"] = PyMuPDFLoaderStrategy()
        logger.debug("로더 등록: pymupdf")
    except ImportError:
        logger.warning("pymupdf 미설치 — 로더 제외")

    try:
        from .strategies.pdfplumber_strategy import PDFPlumberLoaderStrategy
        strategies["pdfplumber"] = PDFPlumberLoaderStrategy()
        logger.debug("로더 등록: pdfplumber")
    except ImportError:
        logger.warning("pdfplumber 미설치 — 로더 제외")

    try:
        from .strategies.camelot_strategy import CamelotLoaderStrategy
        strategies["camelot"] = CamelotLoaderStrategy(flavor="lattice")
        logger.debug("로더 등록: camelot")
    except ImportError:
        logger.warning("camelot 미설치 — 로더 제외")

    try:
        from .strategies.tabula_strategy import TabulaLoaderStrategy
        strategies["tabula"] = TabulaLoaderStrategy()
        logger.debug("로더 등록: tabula")
    except ImportError:
        logger.warning("tabula 미설치 — 로더 제외")

    try:
        from .strategies.unstructured_strategy import UnstructuredLoaderStrategy
        strategies["unstructured"] = UnstructuredLoaderStrategy()
        logger.debug("로더 등록: unstructured")
    except ImportError:
        logger.warning("unstructured 미설치 — 로더 제외")

    try:
        from .strategies.llamaparse_strategy import LlamaParseLoaderStrategy
        strategies["llamaparse"] = LlamaParseLoaderStrategy()
        logger.debug("로더 등록: llamaparse")
    except ImportError:
        logger.warning("llamaparse 미설치 — 로더 제외")

    try:
        from .strategies.tesseract_strategy import TesseractLoaderStrategy
        strategies["tesseract"] = TesseractLoaderStrategy(lang="kor+eng")
        logger.debug("로더 등록: tesseract")
    except ImportError:
        logger.warning("tesseract 미설치 — 로더 제외")

    try:
        from .strategies.textract_strategy import TextractLoaderStrategy
        strategies["textract"] = TextractLoaderStrategy()
        logger.debug("로더 등록: textract")
    except ImportError:
        logger.warning("textract 미설치 — 로더 제외")

    try:
        from .strategies.azure_di_strategy import AzureDILoaderStrategy
        strategies["azure_di"] = AzureDILoaderStrategy()
        logger.debug("로더 등록: azure_di")
    except ImportError:
        logger.warning("azure_di 미설치 — 로더 제외")

    logger.info("사용 가능한 PDF 로더: %s", list(strategies.keys()))
    return strategies


class PDFLoaderContext:
    """
    Router + Strategy Pattern Context.

    - loader_type=None  → PDFTypeRouter가 PDF를 분석하여 최적 로더 자동 선택
    - loader_type 명시  → Router 우회, 해당 전략 직접 사용 (Override)

    상위 파이프라인은 이 클래스만 알면 된다.
    """

    _strategies: dict[str, PDFLoaderStrategy] = _make_strategies()
    _router = PDFTypeRouter()

    @classmethod
    def available_loaders(cls) -> list[str]:
        """현재 설치된 의존성 기준으로 사용 가능한 loader_type 목록을 반환한다."""
        return list(cls._strategies.keys())

    @classmethod
    def LoadingPDFDatas(
        cls,
        pdffilepath: str,
        loader_type: str | None = None,
    ) -> list[Document]:
        """
        PDF를 로딩하여 List[Document]를 반환한다.

        Args:
            pdffilepath: PDF 파일 경로
            loader_type: 사용할 로더 키. None이면 PDFTypeRouter가 자동 결정.

        Returns:
            List[Document]
              metadata["loader_type"]  : 실제 사용된 로더
              metadata["pdf_type"]     : 감지된 PDF 유형 (자동 라우팅 시)
              metadata["auto_routed"]  : 자동 라우팅 여부

        Raises:
            ValueError: 지원하지 않는 loader_type 명시 시
        """
        auto_routed = loader_type is None
        detected_pdf_type: str | None = None

        logger.debug("LoadingPDFDatas 시작: path=%s, loader_type=%s", pdffilepath, loader_type)

        if auto_routed:
            detected_pdf_type, loader_type = cls._router.route_available(
                pdffilepath, cls.available_loaders()
            )
            logger.info("자동 라우팅: pdf_type=%s → loader_type=%s", detected_pdf_type, loader_type)
        else:
            logger.info("수동 지정: loader_type=%s", loader_type)

        if loader_type not in cls._strategies:
            available = cls.available_loaders()
            logger.error("지원하지 않는 loader_type: '%s'. 사용 가능: %s", loader_type, available)
            raise ValueError(
                f"사용할 수 없는 loader_type: '{loader_type}'. "
                f"현재 사용 가능: {available}"
            )

        try:
            docs = cls._strategies[loader_type].load(pdffilepath)
        except Exception as e:
            logger.error("로딩 실패 [%s]: %s", loader_type, e, exc_info=True)
            raise

        for doc in docs:
            doc.metadata["auto_routed"] = auto_routed
            if detected_pdf_type:
                doc.metadata["pdf_type"] = detected_pdf_type

        logger.info("로딩 완료: loader=%s, 문서 수=%d", loader_type, len(docs))
        return docs

    @classmethod
    def register(cls, loader_type: str, strategy: PDFLoaderStrategy) -> None:
        """새 로더 전략을 런타임에 등록한다 (OCP 준수)."""
        cls._strategies[loader_type] = strategy
