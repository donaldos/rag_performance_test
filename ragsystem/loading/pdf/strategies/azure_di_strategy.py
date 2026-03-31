import os

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from langchain_core.documents import Document

from .base import PDFLoaderStrategy


class AzureDILoaderStrategy(PDFLoaderStrategy):
    """스캔 OCR + 레이아웃 분석에 최적. Azure Document Intelligence 클라우드 서비스.
    환경변수 AZURE_DI_ENDPOINT, AZURE_DI_KEY 필요.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        key: str | None = None,
        model_id: str = "prebuilt-layout",
    ):
        self.endpoint = endpoint or os.environ["AZURE_DI_ENDPOINT"]
        self.key = key or os.environ["AZURE_DI_KEY"]
        self.model_id = model_id

    def load(self, filepath: str):
        client = DocumentAnalysisClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.key),
        )

        with open(filepath, "rb") as f:
            poller = client.begin_analyze_document(self.model_id, f)
        result = poller.result()

        # 페이지별 텍스트 수집
        docs = []
        for page in result.pages:
            lines = [line.content for line in (page.lines or [])]
            docs.append(Document(
                page_content="\n".join(lines),
                metadata={"source": filepath, "page": page.page_number},
            ))
        return self._add_metadata(docs, "azure_di")
