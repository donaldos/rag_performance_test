from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .base import ChunkingStrategy


class ParentChildChunkingStrategy(ChunkingStrategy):
    """큰 부모 청크와 작은 자식 청크를 함께 생성.

    - 자식 청크: 임베딩 및 검색에 사용 (정밀도↑)
    - 부모 청크: 검색 후 LLM에 전달하는 컨텍스트 (재현율↑)
    - 자식 청크 metadata["parent_id"]로 부모 추적 가능
    """

    def __init__(
        self,
        parent_chunk_size: int = 2000,
        child_chunk_size: int = 400,
        chunk_overlap: int = 50,
    ):
        self.parent_chunk_size = parent_chunk_size
        self.child_chunk_size = child_chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, docs: list[Document]) -> list[Document]:
        parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.parent_chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.child_chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        all_chunks: list[Document] = []
        for parent_idx, parent in enumerate(parent_splitter.split_documents(docs)):
            parent.metadata["chunk_role"] = "parent"
            parent.metadata["parent_id"] = parent_idx
            all_chunks.append(parent)

            children = child_splitter.split_documents([parent])
            for child in children:
                child.metadata["chunk_role"] = "child"
                child.metadata["parent_id"] = parent_idx
            all_chunks.extend(children)

        return self._add_metadata(all_chunks, "parent_child")
