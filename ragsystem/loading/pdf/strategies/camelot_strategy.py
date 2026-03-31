import camelot
from langchain_core.documents import Document

from .base import PDFLoaderStrategy


class CamelotLoaderStrategy(PDFLoaderStrategy):
    """표 중심 PDF에 최적. lattice(선 있는 표) / stream(선 없는 표) 방식 선택 가능."""

    def __init__(self, flavor: str = "lattice"):
        # flavor: "lattice" | "stream"
        self.flavor = flavor

    def load(self, filepath: str):
        tables = camelot.read_pdf(filepath, pages="all", flavor=self.flavor)
        docs = []
        for i, table in enumerate(tables):
            content = table.df.to_markdown(index=False)
            docs.append(Document(
                page_content=content,
                metadata={"source": filepath, "table_index": i},
            ))
        return self._add_metadata(docs, "camelot")
