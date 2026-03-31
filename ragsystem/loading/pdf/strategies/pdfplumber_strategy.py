from langchain_community.document_loaders import PDFPlumberLoader

from .base import PDFLoaderStrategy


class PDFPlumberLoaderStrategy(PDFLoaderStrategy):
    """표 + 텍스트 혼합 PDF에 최적. 좌표 기반 표 추출."""

    def load(self, filepath: str):
        docs = PDFPlumberLoader(filepath).load()
        return self._add_metadata(docs, "pdfplumber")
