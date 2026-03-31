import os

from langchain_core.documents import Document
from llama_parse import LlamaParse

from .base import PDFLoaderStrategy


class LlamaParseLoaderStrategy(PDFLoaderStrategy):
    """그래프·이미지 포함 PDF에 최적. API 기반 멀티모달 파싱.
    환경변수 LLAMA_CLOUD_API_KEY 필요.
    """

    def __init__(self, result_type: str = "markdown"):
        # result_type: "markdown" | "text"
        self.result_type = result_type

    def load(self, filepath: str):
        parser = LlamaParse(
            api_key=os.environ["LLAMA_CLOUD_API_KEY"],
            result_type=self.result_type,
        )
        raw_docs = parser.load_data(filepath)
        docs = [
            Document(
                page_content=doc.text,
                metadata={"source": filepath, "page": i + 1},
            )
            for i, doc in enumerate(raw_docs)
        ]
        return self._add_metadata(docs, "llamaparse")
