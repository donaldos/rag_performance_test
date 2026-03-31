from abc import ABC, abstractmethod

from langchain_core.documents import Document


class PDFLoaderStrategy(ABC):
    """모든 PDF 로더 전략의 공통 인터페이스."""

    @abstractmethod
    def load(self, filepath: str) -> list[Document]:
        """PDF를 로딩하여 Document 리스트로 반환한다."""
        pass

    def _add_metadata(
        self, docs: list[Document], loader_type: str
    ) -> list[Document]:
        """공통 메타데이터(loader_type)를 추가한다."""
        for doc in docs:
            doc.metadata["loader_type"] = loader_type
        return docs
