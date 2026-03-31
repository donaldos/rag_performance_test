import fitz  # PyMuPDF — 추가 의존성 없이 빠른 사전 검사

from ragsystem.utils import get_logger

logger = get_logger(__name__)


class PDFTypeRouter:
    """
    PDF 특성을 분석하여 최적 loader_type을 결정하는 라우터.

    detect_pdf_type() → pdf_type 문자열 반환
    route()           → (pdf_type, loader_type) 튜플 반환
    """

    # pdf_type → 우선순위 정렬된 loader_type 목록 (index 0이 기본값)
    _routing_table: dict[str, list[str]] = {
        "text":  ["pymupdf", "pdfplumber"],
        "table": ["camelot", "pdfplumber", "tabula"],
        "graph": ["llamaparse", "unstructured"],
        "scan":  ["azure_di", "textract", "tesseract"],
        "mixed": ["pymupdf", "unstructured", "llamaparse"],
    }

    # 이미지 면적 비율 기준: 페이지 면적 대비 이미지 면적이 이 값 이상이면 graph/scan 후보
    _IMAGE_AREA_RATIO = 0.30
    # 스캔 판별 기준: 페이지당 평균 문자 수가 이 값 미만이면 스캔 후보
    _SCAN_CHAR_THRESHOLD = 50
    # 표 판별 기준: 페이지당 평균 수평선 수가 이 값 초과이면 표 후보
    _TABLE_HLINE_THRESHOLD = 5

    def detect_pdf_type(self, filepath: str) -> str:
        """
        pymupdf로 PDF를 빠르게 사전 검사하여 pdf_type을 반환한다.

        검사 순서:
          1. 텍스트 레이어 밀도 → 낮으면 'scan'
          2. 이미지 면적 비율 + 수평선 밀도 → 높으면 'graph' 또는 'mixed'
          3. 수평선 밀도 → 높으면 'table'
          4. 이미지가 약간 있으면 'mixed', 나머지는 'text'
        """
        doc = fitz.open(filepath)
        total_pages = len(doc)

        total_chars = 0
        image_area_ratio_sum = 0.0
        hline_count = 0

        for page in doc:
            page_area = page.rect.width * page.rect.height or 1.0

            # 텍스트 밀도
            total_chars += len(page.get_text("text").strip())

            # 이미지 면적 비율
            for img in page.get_image_info():
                img_w = img.get("width", 0)
                img_h = img.get("height", 0)
                image_area_ratio_sum += (img_w * img_h) / page_area

            # 수평선 밀도 (표 특성)
            for path in page.get_drawings():
                if path["type"] == "l" and abs(path["rect"].height) < 2:
                    hline_count += 1

        doc.close()

        avg_chars = total_chars / total_pages
        avg_img_ratio = image_area_ratio_sum / total_pages
        avg_hlines = hline_count / total_pages

        logger.debug(
            "PDF 분석: pages=%d, avg_chars=%.1f, avg_img_ratio=%.3f, avg_hlines=%.1f",
            total_pages, avg_chars, avg_img_ratio, avg_hlines,
        )

        if avg_chars < self._SCAN_CHAR_THRESHOLD:
            pdf_type = "scan"
        elif avg_img_ratio >= self._IMAGE_AREA_RATIO:
            pdf_type = "mixed" if avg_hlines > self._TABLE_HLINE_THRESHOLD else "graph"
        elif avg_hlines > self._TABLE_HLINE_THRESHOLD:
            pdf_type = "table"
        elif avg_img_ratio > 0.05:
            pdf_type = "mixed"
        else:
            pdf_type = "text"

        logger.info("PDF 유형 감지: %s (avg_chars=%.1f)", pdf_type, avg_chars)
        return pdf_type

    def route(self, filepath: str, rank: int = 0) -> tuple[str, str]:
        """
        PDF에 최적인 loader_type을 반환한다.

        Args:
            filepath: PDF 파일 경로
            rank: 우선순위 인덱스 (0=기본, 1=폴백, ...)

        Returns:
            (pdf_type, loader_type) 튜플
        """
        pdf_type = self.detect_pdf_type(filepath)
        candidates = self._routing_table.get(pdf_type, ["pymupdf"])
        loader_type = candidates[min(rank, len(candidates) - 1)]
        logger.info("라우팅 결정: pdf_type=%s → loader_type=%s (rank=%d)", pdf_type, loader_type, rank)
        return pdf_type, loader_type

    def route_available(self, filepath: str, available: list[str]) -> tuple[str, str]:
        """
        설치된 로더 목록을 고려하여 사용 가능한 최적 loader_type을 반환한다.
        1순위가 미설치이면 다음 후보로 자동 폴백한다.

        Args:
            filepath:  PDF 파일 경로
            available: 현재 사용 가능한 loader_type 목록

        Returns:
            (pdf_type, loader_type) 튜플
        """
        pdf_type = self.detect_pdf_type(filepath)
        candidates = self._routing_table.get(pdf_type, ["pymupdf"])

        for candidate in candidates:
            if candidate in available:
                logger.info(
                    "라우팅(폴백 포함): pdf_type=%s → loader_type=%s (후보=%s)",
                    pdf_type, candidate, candidates,
                )
                return pdf_type, candidate

        # routing_table 후보 중 사용 가능한 것이 없으면 available의 첫 번째 로더로 폴백
        if available:
            logger.warning(
                "pdf_type=%s 후보 %s 중 설치된 로더 없음 → '%s' 로 폴백",
                pdf_type, candidates, available[0],
            )
            return pdf_type, available[0]

        # available도 없으면 1순위 반환 (호출자에서 오류 처리)
        logger.warning("사용 가능한 로더가 전혀 없음 — '%s' 반환 (실패 예상)", candidates[0])
        return pdf_type, candidates[0]
