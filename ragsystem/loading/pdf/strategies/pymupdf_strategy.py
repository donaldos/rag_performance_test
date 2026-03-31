from langchain_community.document_loaders import PyMuPDFLoader

from .base import PDFLoaderStrategy


class PyMuPDFLoaderStrategy(PDFLoaderStrategy):
    """네이티브 텍스트 레이어 PDF에 최적. 가장 빠름, 범용."""

    def load(self, filepath: str):
        docs = PyMuPDFLoader(filepath).load()
        return self._add_metadata(docs, "pymupdf")
