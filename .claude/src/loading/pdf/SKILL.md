---
name: pdf-loader
description: |
  PDF 파일을 Router + 전략 패턴으로 로딩하는 모듈.
  LoadingPDFDatas(pdffilepath, loader_type=None) 인터페이스로 호출하며,
  loader_type을 생략하면 PDFTypeRouter가 PDF 특성을 자동 분석하여 최적 로더를 선택한다.
  loader_type을 명시하면 Router를 우회하고 해당 전략을 직접 사용한다.
  PDF 로딩, 로더 선택, 로더 추가, 로더 평가 관련 작업에 반드시 사용한다.
---

# PDF Loader Skill

## 역할

PDF 특성을 자동 감지하거나 명시적 `loader_type`으로 적절한 로더를 선택하고
`List[Document]`를 반환한다. 상위 파이프라인(청킹, 임베딩)은 로더 구현을 알 필요 없다.

---

## 아키텍처: Router + Strategy 통합 패턴

```
LoadingPDFDatas(filepath, loader_type=None)
         │
         ▼
  loader_type 지정됨?
    ├── Yes → PDFLoaderContext._strategies[loader_type].load()   ← Strategy 직접 호출
    └── No  → PDFTypeRouter.route(filepath)
                    │
                    ▼
              detect_pdf_type()   ← pymupdf 사전 검사
                    │
              _routing_table[pdf_type][0]  ← 최적 loader_type 결정
                    │
                    ▼
             PDFLoaderContext._strategies[loader_type].load()
```

| 모드 | 호출 방법 | 설명 |
|------|----------|------|
| 자동 라우팅 | `LoadingPDFDatas(path)` | Router가 PDF 분석 후 최적 로더 선택 |
| 수동 Override | `LoadingPDFDatas(path, "camelot")` | 지정 로더 직접 사용 |

---

## 지원 loader_type 목록

| loader_type | 클래스 | 최적 PDF 유형 | 특징 |
|-------------|--------|-------------|------|
| `pymupdf` | `PyMuPDFLoaderStrategy` | 텍스트 레이어 | 가장 빠름, 범용 |
| `pdfplumber` | `PDFPlumberLoaderStrategy` | 표 + 텍스트 혼합 | 좌표 기반 표 추출 |
| `camelot` | `CamelotLoaderStrategy` | 표 중심 | lattice/stream 방식 선택 가능 |
| `tabula` | `TabulaLoaderStrategy` | 표 중심 | Java 기반, camelot 대안 |
| `unstructured` | `UnstructuredLoaderStrategy` | 복합형 | 유형 자동 분류, 느림 |
| `llamaparse` | `LlamaParseLoaderStrategy` | 그래프·이미지 포함 | API 기반, 멀티모달 |
| `tesseract` | `TesseractLoaderStrategy` | 스캔 OCR | 오픈소스, 무료 |
| `textract` | `TextractLoaderStrategy` | 스캔 OCR + 표 | AWS 클라우드 |
| `azure_di` | `AzureDILoaderStrategy` | 스캔 OCR + 레이아웃 | Azure 클라우드 |

---

## 라우팅 테이블 (pdf_type → loader_type 우선순위)

| pdf_type | 1순위 (기본) | 2순위 | 3순위 |
|----------|------------|-------|-------|
| `text` | `pymupdf` | `pdfplumber` | — |
| `table` | `camelot` | `pdfplumber` | `tabula` |
| `graph` | `llamaparse` | `unstructured` | — |
| `scan` | `azure_di` | `textract` | `tesseract` |
| `mixed` | `pymupdf` | `unstructured` | `llamaparse` |

Router는 기본적으로 1순위를 반환한다. 폴백(fallback) 이 필요하면 `route(filepath, rank=1)` 로 2순위를 지정한다.

---

## 인터페이스

```python
from src.loading.pdf.loader_context import PDFLoaderContext

# 자동 라우팅 — Router가 PDF를 분석하여 최적 로더 선택
docs = PDFLoaderContext.LoadingPDFDatas("path/to/file.pdf")

# 수동 Override — loader_type 명시 시 Router 우회
docs = PDFLoaderContext.LoadingPDFDatas("path/to/file.pdf", loader_type="camelot")

# 반환: List[Document]
# Document.page_content: str
# Document.metadata: {
#   "source": str,      # 파일 경로
#   "page": int,        # 페이지 번호
#   "loader_type": str, # 실제 사용된 로더
#   "pdf_type": str,    # 감지된 PDF 유형 (자동 라우팅 시에만)
#   "auto_routed": bool # 자동 라우팅 여부
# }
```

---

## 구현 코드

### 추상 인터페이스 (`strategies/base.py`)

```python
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
```

---

### Router (`router.py`)

```python
import fitz  # pymupdf — 사전 검사용 (의존성 최소화)
from langchain_core.documents import Document


class PDFTypeRouter:
    """
    PDF 특성을 분석하여 최적 loader_type을 결정하는 라우터.

    detect_pdf_type() → pdf_type 문자열 반환
    route()           → pdf_type에 매핑된 loader_type 반환
    """

    # pdf_type → 우선순위 정렬된 loader_type 목록 (0번이 기본값)
    _routing_table: dict[str, list[str]] = {
        "text":  ["pymupdf", "pdfplumber"],
        "table": ["camelot", "pdfplumber", "tabula"],
        "graph": ["llamaparse", "unstructured"],
        "scan":  ["azure_di", "textract", "tesseract"],
        "mixed": ["pymupdf", "unstructured", "llamaparse"],
    }

    # 이미지 비율 기준: 페이지 면적 대비 이미지 면적이 이 값 이상이면 graph/scan 후보
    _IMAGE_AREA_RATIO = 0.30
    # 텍스트 밀도 기준: 페이지당 문자 수가 이 값 미만이면 스캔 후보
    _SCAN_CHAR_THRESHOLD = 50

    def detect_pdf_type(self, filepath: str) -> str:
        """
        pymupdf로 PDF를 빠르게 사전 검사하여 pdf_type을 반환한다.

        검사 순서:
        1. 텍스트 레이어 유무 → 없으면 'scan'
        2. 이미지 면적 비율 → 높으면 'graph'
        3. 표 특성 (수평선 밀도) → 높으면 'table'
        4. 나머지 → 'text'
        """
        doc = fitz.open(filepath)
        total_pages = len(doc)

        text_chars = 0
        image_area_ratio_sum = 0.0
        hline_count = 0

        for page in doc:
            page_area = page.rect.width * page.rect.height

            # 텍스트 밀도
            text = page.get_text("text")
            text_chars += len(text.strip())

            # 이미지 면적 비율
            for img in page.get_image_info():
                img_w = img.get("width", 0)
                img_h = img.get("height", 0)
                image_area_ratio_sum += (img_w * img_h) / (page_area or 1)

            # 수평선 밀도 (표 특성)
            paths = page.get_drawings()
            hline_count += sum(
                1 for p in paths
                if p["type"] == "l" and abs(p["rect"].height) < 2
            )

        doc.close()

        avg_chars = text_chars / (total_pages or 1)
        avg_img_ratio = image_area_ratio_sum / (total_pages or 1)
        avg_hlines = hline_count / (total_pages or 1)

        # 판별 로직
        if avg_chars < self._SCAN_CHAR_THRESHOLD:
            return "scan"
        if avg_img_ratio >= self._IMAGE_AREA_RATIO:
            if avg_hlines > 5:
                return "mixed"
            return "graph"
        if avg_hlines > 5:
            return "table"
        if avg_img_ratio > 0.05:
            return "mixed"
        return "text"

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
        return pdf_type, loader_type
```

---

### 구현체 예시

#### PyMuPDF (`strategies/pymupdf_strategy.py`)

```python
from langchain_community.document_loaders import PyMuPDFLoader
from .base import PDFLoaderStrategy

class PyMuPDFLoaderStrategy(PDFLoaderStrategy):
    def load(self, filepath: str):
        docs = PyMuPDFLoader(filepath).load()
        return self._add_metadata(docs, "pymupdf")
```

#### Camelot — 표 중심 (`strategies/camelot_strategy.py`)

```python
import camelot
from langchain_core.documents import Document
from .base import PDFLoaderStrategy

class CamelotLoaderStrategy(PDFLoaderStrategy):
    def __init__(self, flavor: str = "lattice"):
        self.flavor = flavor

    def load(self, filepath: str):
        tables = camelot.read_pdf(filepath, pages="all", flavor=self.flavor)
        docs = []
        for i, table in enumerate(tables):
            content = table.df.to_markdown(index=False)
            docs.append(Document(
                page_content=content,
                metadata={"source": filepath, "table_index": i}
            ))
        return self._add_metadata(docs, "camelot")
```

#### Tesseract — 스캔 OCR (`strategies/tesseract_strategy.py`)

```python
import pytesseract
from pdf2image import convert_from_path
from langchain_core.documents import Document
from .base import PDFLoaderStrategy

class TesseractLoaderStrategy(PDFLoaderStrategy):
    def __init__(self, lang: str = "kor+eng"):
        self.lang = lang

    def load(self, filepath: str):
        images = convert_from_path(filepath, dpi=300)
        docs = []
        for i, img in enumerate(images):
            text = pytesseract.image_to_string(img, lang=self.lang)
            docs.append(Document(
                page_content=text,
                metadata={"source": filepath, "page": i + 1}
            ))
        return self._add_metadata(docs, "tesseract")
```

---

### Context — Router + Strategy 통합 (`loader_context.py`)

```python
from langchain_core.documents import Document

from .router import PDFTypeRouter
from .strategies.pymupdf_strategy     import PyMuPDFLoaderStrategy
from .strategies.pdfplumber_strategy  import PDFPlumberLoaderStrategy
from .strategies.camelot_strategy     import CamelotLoaderStrategy
from .strategies.tabula_strategy      import TabulaLoaderStrategy
from .strategies.unstructured_strategy import UnstructuredLoaderStrategy
from .strategies.llamaparse_strategy  import LlamaParseLoaderStrategy
from .strategies.tesseract_strategy   import TesseractLoaderStrategy
from .strategies.textract_strategy    import TextractLoaderStrategy
from .strategies.azure_di_strategy    import AzureDILoaderStrategy


class PDFLoaderContext:
    """
    Router + Strategy Pattern Context.

    - loader_type=None  → PDFTypeRouter가 PDF를 분석하여 최적 로더 자동 선택
    - loader_type 명시  → Router 우회, 해당 전략 직접 사용 (Override)

    상위 파이프라인은 이 클래스만 알면 된다.
    """

    _strategies = {
        "pymupdf":      PyMuPDFLoaderStrategy(),
        "pdfplumber":   PDFPlumberLoaderStrategy(),
        "camelot":      CamelotLoaderStrategy(flavor="lattice"),
        "tabula":       TabulaLoaderStrategy(),
        "unstructured": UnstructuredLoaderStrategy(),
        "llamaparse":   LlamaParseLoaderStrategy(),
        "tesseract":    TesseractLoaderStrategy(lang="kor+eng"),
        "textract":     TextractLoaderStrategy(),
        "azure_di":     AzureDILoaderStrategy(),
    }

    _router = PDFTypeRouter()

    @classmethod
    def LoadingPDFDatas(
        cls,
        pdffilepath: str,
        loader_type: str | None = None,
    ) -> list[Document]:
        """
        PDF를 로딩하여 List[Document]를 반환한다.

        Args:
            pdffilepath: PDF 파일 경로
            loader_type: 사용할 로더 키. None이면 PDFTypeRouter가 자동 결정.

        Returns:
            List[Document]: 공통 포맷의 문서 리스트
              - metadata["loader_type"]: 실제 사용된 로더
              - metadata["pdf_type"]: 감지된 PDF 유형 (자동 라우팅 시)
              - metadata["auto_routed"]: 자동 라우팅 여부

        Raises:
            ValueError: 지원하지 않는 loader_type 명시 시
        """
        auto_routed = loader_type is None
        detected_pdf_type: str | None = None

        if auto_routed:
            detected_pdf_type, loader_type = cls._router.route(pdffilepath)

        if loader_type not in cls._strategies:
            raise ValueError(
                f"지원하지 않는 loader_type: '{loader_type}'. "
                f"지원 목록: {list(cls._strategies.keys())}"
            )

        docs = cls._strategies[loader_type].load(pdffilepath)

        # 라우팅 메타데이터 추가
        for doc in docs:
            doc.metadata["auto_routed"] = auto_routed
            if detected_pdf_type:
                doc.metadata["pdf_type"] = detected_pdf_type

        return docs

    @classmethod
    def register(cls, loader_type: str, strategy) -> None:
        """새 로더 전략을 런타임에 등록한다 (OCP 준수)."""
        cls._strategies[loader_type] = strategy
```

---

## 평가 루프 연동

```python
import mlflow
from src.loading.pdf.loader_context import PDFLoaderContext
from src.evaluation.retrieval import eval_extraction

PDF_TYPE = "scan"   # text | table | graph | scan | mixed
LOADERS  = ["tesseract", "textract", "azure_di"]   # 유형별 유효 로더만

with mlflow.start_run(run_name=f"loader_eval_{PDF_TYPE}"):
    # 1) 자동 라우팅으로 베이스라인 측정
    docs_auto = PDFLoaderContext.LoadingPDFDatas(
        pdffilepath=f"data/sample/{PDF_TYPE}.pdf"
    )
    auto_loader = docs_auto[0].metadata["loader_type"]
    score_auto  = eval_extraction(docs_auto, gold_path=f"data/gold/{PDF_TYPE}/")

    mlflow.log_params({"pdf_type": PDF_TYPE, "loader_type": auto_loader, "auto_routed": True})
    mlflow.log_metrics({"cer": score_auto["cer"], "table": score_auto["table"]})

    # 2) 수동 Override로 개별 로더 비교
    for loader_type in LOADERS:
        docs = PDFLoaderContext.LoadingPDFDatas(
            pdffilepath=f"data/sample/{PDF_TYPE}.pdf",
            loader_type=loader_type
        )
        score = eval_extraction(docs, gold_path=f"data/gold/{PDF_TYPE}/")

        mlflow.log_params({"pdf_type": PDF_TYPE, "loader_type": loader_type, "auto_routed": False})
        mlflow.log_metrics({
            "char_error_rate": score["cer"],
            "table_structure_score": score["table"],
            "reading_order_score": score["order"],
        })

        if score["cer"] > 0.05:
            print(f"[SKIP] {loader_type}: CER {score['cer']:.2%} — 게이트 미통과")
            continue

        print(f"[PASS] {loader_type}: CER {score['cer']:.2%}")
```

---

## 새 로더 추가 방법

1. `strategies/` 하위에 `{name}_strategy.py` 파일 생성
2. `PDFLoaderStrategy`를 상속하고 `load()` 메서드 구현
3. `loader_context.py`의 `_strategies` 딕셔너리에 키:인스턴스 추가
4. `router.py`의 `_routing_table` 해당 `pdf_type` 리스트에 추가
5. 이 파일(`SKILL.md`)의 지원 목록 표 및 라우팅 테이블에 행 추가

상위 파이프라인 코드(`LoadingPDFDatas` 호출부)는 수정하지 않는다.

---

## 품질 평가 기준 (OmniDocBench 기준)

| 지표 | 통과 기준 | 측정 방법 |
|------|----------|----------|
| CER (문자 오류율) | ≤ 5% | `jiwer.cer(reference, hypothesis)` |
| 표 구조 보존율 | ≥ 0.85 (TEDS) | Tree-Edit-Distance-based Similarity |
| 읽기 순서 정확도 | ≥ 0.90 | Normalized Edit Distance |

---

---

## 테스트

### 테스트 파일 위치

```
src/test/test_pdf_loading.py
```

### 실행 방법

```bash
# 프로젝트 루트에서 실행 (venv 활성화 후)
source venv/bin/activate

# 1) 사용 가능한 로더 목록 확인 (의존성 설치 여부 체크)
python -m src.test.test_pdf_loading --list-loaders

# 2) 기본 테스트: Router 감지 → 자동 라우팅 → 추천 로더 개별 비교
python -m src.test.test_pdf_loading path/to/file.pdf

# 3) 특정 로더만 테스트
python -m src.test.test_pdf_loading path/to/file.pdf --loader pymupdf
python -m src.test.test_pdf_loading path/to/file.pdf --loader camelot

# 4) 설치된 모든 로더 일괄 테스트 (속도·문자 수 비교)
python -m src.test.test_pdf_loading path/to/file.pdf --all
```

### 테스트 항목

| 테스트 | 내용 |
|--------|------|
| `--list-loaders` | 설치된 의존성 기준 사용 가능한 로더 목록 출력 |
| ① Router 감지 | `PDFTypeRouter.route()` — pdf_type·loader_type 및 소요 시간 |
| ② 자동 라우팅 | `LoadingPDFDatas(path)` — doc 수, 소요 시간, 첫 Document 미리보기 |
| ③ 수동 Override | `LoadingPDFDatas(path, loader_type="...")` — 특정 로더 단독 검증 |
| ④ 일괄 비교 (`--all`) | 설치된 모든 로더 실행 → doc 수 / 문자 수 / 소요 시간 비교표 |

### 의존성 미설치 처리

`PDFLoaderContext`는 lazy import를 사용한다. 설치되지 않은 라이브러리의 전략은
자동으로 제외되며, 해당 `loader_type`을 명시하면 `ValueError`가 발생한다.

```
[PASS] pymupdf        ← 설치됨
[FAIL] camelot        오류: 'camelot' 미설치. 사용 가능: ['pymupdf', 'pdfplumber']
```

### 최소 설치 (Router + pymupdf만 테스트)

```bash
pip install pymupdf langchain-community langchain-core
python -m src.test.test_pdf_loading path/to/file.pdf --loader pymupdf
```

---

## 관련 파일

- `.claude/CLAUDE.md` — 프로젝트 전체 구조 및 설계 원칙
- `.claude/src/chunking/SKILL.md` — 다음 단계: 청킹 전략 가이드
- `.claude/src/embedding/SKILL.md` — 임베딩 모델 가이드
- `.claude/src/vectordb/SKILL.md` — VectorDB 가이드
- `src/loading/pdf/strategies/base.py` — PDFLoaderStrategy 추상 클래스
- `src/loading/pdf/router.py` — PDFTypeRouter
- `src/loading/pdf/loader_context.py` — PDFLoaderContext (lazy import)
- `src/test/test_pdf_loading.py` — PDF 로딩 테스트 스크립트
