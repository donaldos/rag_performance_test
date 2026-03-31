from langchain_core.documents import Document

from .base import ChunkingStrategy


class PageChunkingStrategy(ChunkingStrategy):
    """페이지 단위를 그대로 청크로 사용. 표·이미지 레이아웃 보존에 유리."""

    def chunk(self, docs: list[Document]) -> list[Document]:
        return self._add_metadata(list(docs), "page")
