import os

import boto3
from langchain_core.documents import Document

from .base import PDFLoaderStrategy


class TextractLoaderStrategy(PDFLoaderStrategy):
    """스캔 OCR + 표 추출에 최적. AWS Textract 클라우드 서비스.
    환경변수 AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION,
    TEXTRACT_S3_BUCKET 필요.
    """

    def __init__(self, s3_bucket: str | None = None):
        self.s3_bucket = s3_bucket or os.environ.get("TEXTRACT_S3_BUCKET", "")

    def load(self, filepath: str):
        s3 = boto3.client("s3")
        textract = boto3.client("textract")

        filename = os.path.basename(filepath)
        s3_key = f"textract-input/{filename}"

        s3.upload_file(filepath, self.s3_bucket, s3_key)

        response = textract.start_document_text_detection(
            DocumentLocation={"S3Object": {"Bucket": self.s3_bucket, "Name": s3_key}}
        )
        job_id = response["JobId"]

        # 완료 대기
        while True:
            result = textract.get_document_text_detection(JobId=job_id)
            status = result["JobStatus"]
            if status in ("SUCCEEDED", "FAILED"):
                break

        if status == "FAILED":
            raise RuntimeError(f"Textract job {job_id} failed for {filepath}")

        # 페이지별 텍스트 수집
        pages: dict[int, list[str]] = {}
        for block in result.get("Blocks", []):
            if block["BlockType"] == "LINE":
                page_num = block.get("Page", 1)
                pages.setdefault(page_num, []).append(block["Text"])

        docs = [
            Document(
                page_content="\n".join(lines),
                metadata={"source": filepath, "page": page_num},
            )
            for page_num, lines in sorted(pages.items())
        ]
        return self._add_metadata(docs, "textract")
