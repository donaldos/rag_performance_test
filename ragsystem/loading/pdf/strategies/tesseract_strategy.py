import pytesseract
from langchain_core.documents import Document
from pdf2image import convert_from_path

from .base import PDFLoaderStrategy


class TesseractLoaderStrategy(PDFLoaderStrategy):
    """스캔 PDF OCR에 최적. 오픈소스 무료. tesseract 및 poppler 설치 필요."""

    def __init__(self, lang: str = "kor+eng", dpi: int = 300):
        self.lang = lang
        self.dpi = dpi

    def load(self, filepath: str):
        images = convert_from_path(filepath, dpi=self.dpi)
        docs = []
        for i, img in enumerate(images):
            text = pytesseract.image_to_string(img, lang=self.lang)
            docs.append(Document(
                page_content=text,
                metadata={"source": filepath, "page": i + 1},
            ))
        return self._add_metadata(docs, "tesseract")
