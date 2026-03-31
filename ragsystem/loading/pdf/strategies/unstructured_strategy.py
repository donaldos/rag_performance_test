import sys
import types

from langchain_community.document_loaders import UnstructuredPDFLoader

from .base import PDFLoaderStrategy


def _patch_pi_heif() -> None:
    """pi_heif 미설치 시 빈 모듈로 대체한다.
    unstructured가 HEIF 이미지 처리용으로 import하지만 PDF 파싱에는 불필요하다.
    """
    if "pi_heif" not in sys.modules:
        mock = types.ModuleType("pi_heif")
        mock.register_heif_opener = lambda: None  # type: ignore[attr-defined]
        sys.modules["pi_heif"] = mock


_patch_pi_heif()


class UnstructuredLoaderStrategy(PDFLoaderStrategy):
    """복합형 PDF에 최적. 유형 자동 분류. 처리 속도가 느림.

    strategy:
      "fast"    — pdfminer 기반, 텍스트 레이어 있는 PDF (poppler 불필요, 기본값)
      "hi_res"  — detectron2 기반, 레이아웃 정밀 분석 (poppler + detectron2 필요)
      "ocr_only"— 전체 OCR (tesseract 필요)
      "auto"    — 자동 선택 (환경에 따라 폴백 발생 가능)
    """

    def __init__(self, strategy: str = "fast"):
        self.strategy = strategy

    def load(self, filepath: str):
        docs = UnstructuredPDFLoader(
            filepath, mode="elements", strategy=self.strategy
        ).load()
        return self._add_metadata(docs, "unstructured")
