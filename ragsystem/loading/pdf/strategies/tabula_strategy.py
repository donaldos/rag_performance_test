import tabula
from langchain_core.documents import Document

from .base import PDFLoaderStrategy


class TabulaLoaderStrategy(PDFLoaderStrategy):
    """표 중심 PDF에 최적. Java 기반, camelot 대안."""

    def load(self, filepath: str):
        dfs = tabula.read_pdf(filepath, pages="all", multiple_tables=True)
        docs = []
        for i, df in enumerate(dfs):
            content = df.to_markdown(index=False)
            docs.append(Document(
                page_content=content,
                metadata={"source": filepath, "table_index": i},
            ))
        return self._add_metadata(docs, "tabula")
