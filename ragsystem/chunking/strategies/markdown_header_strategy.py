from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

from .base import ChunkingStrategy


class MarkdownHeaderChunkingStrategy(ChunkingStrategy):
    """Markdown 헤더 계층(#, ##, ###)을 기준으로 섹션 단위 분할.
    llamaparse 등 Markdown 출력 로더와 함께 사용할 때 효과적.
    """

    # 분할 기준 헤더 레벨
    _HEADERS = [
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ]

    def __init__(self, strip_headers: bool = False):
        # strip_headers: True이면 청크에서 헤더 줄 제거
        self.strip_headers = strip_headers

    def chunk(self, docs: list[Document]) -> list[Document]:
        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self._HEADERS,
            strip_headers=self.strip_headers,
        )
        chunks: list[Document] = []
        for doc in docs:
            splits = splitter.split_text(doc.page_content)
            for split in splits:
                # 상위 Document의 메타데이터(source, page 등) 상속
                merged_meta = {**doc.metadata, **split.metadata}
                chunks.append(Document(page_content=split.page_content, metadata=merged_meta))
        return self._add_metadata(chunks, "markdown_header")
