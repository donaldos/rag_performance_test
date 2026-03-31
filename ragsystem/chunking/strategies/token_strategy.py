from langchain_core.documents import Document
from langchain_text_splitters import TokenTextSplitter

from .base import ChunkingStrategy


class TokenChunkingStrategy(ChunkingStrategy):
    """LLM 토크나이저 기준으로 분할. 컨텍스트 윈도우 초과 방지에 유리.

    encoding_name: tiktoken 인코딩 (cl100k_base = GPT-4 기준)
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding_name = encoding_name

    def chunk(self, docs: list[Document]) -> list[Document]:
        splitter = TokenTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            encoding_name=self.encoding_name,
        )
        chunks = splitter.split_documents(docs)
        return self._add_metadata(chunks, "token")
