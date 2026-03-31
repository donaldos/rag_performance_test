# PDF Loader Module

PDF 파일을 **Router + Strategy 패턴**으로 로딩하여 `List[Document]`를 반환하는 모듈.
파이프라인 1단계: PDF → Documents.

---

## 파일 구조

```
pdf/
├── router.py           ← PDFTypeRouter: PDF 특성 분석 → loader_type 자동 결정
├── loader_context.py   ← PDFLoaderContext: Router + Strategy 통합 진입점
└── strategies/
    ├── base.py                  ← PDFLoaderStrategy (ABC)
    ├── pymupdf_strategy.py      ← 텍스트 레이어 PDF (기본, 가장 빠름)
    ├── pdfplumber_strategy.py   ← 텍스트 + 표 혼합
    ├── camelot_strategy.py      ← 표 중심 (lattice/stream)
    ├── tabula_strategy.py       ← 표 중심 (Java 기반)
    ├── unstructured_strategy.py ← 복합형 자동 분류
    ├── llamaparse_strategy.py   ← 그래프·이미지 (API)
    ├── tesseract_strategy.py    ← 스캔 OCR (오픈소스)
    ├── textract_strategy.py     ← 스캔 OCR (AWS)
    └── azure_di_strategy.py     ← 스캔 OCR + 레이아웃 (Azure)
```

---

## 빠른 시작

```python
from ragsystem.loading.pdf.loader_context import PDFLoaderContext

# 자동 라우팅 — Router가 PDF 분석 후 최적 로더 선택
docs = PDFLoaderContext.LoadingPDFDatas("path/to/file.pdf")

# 수동 지정 — Router 우회
docs = PDFLoaderContext.LoadingPDFDatas("path/to/file.pdf", loader_type="pymupdf")

# 사용 가능한 로더 목록 확인
print(PDFLoaderContext.available_loaders())
```

반환값 `List[Document]` 각 항목의 metadata:

| 키 | 타입 | 설명 |
|----|------|------|
| `source` | str | PDF 파일 경로 |
| `page` | int | 페이지 번호 |
| `loader_type` | str | 실제 사용된 로더 |
| `pdf_type` | str | 감지된 PDF 유형 (자동 라우팅 시) |
| `auto_routed` | bool | 자동 라우팅 여부 |

---

## 아키텍처

```
LoadingPDFDatas(filepath, loader_type=None)
        │
        ├── loader_type 지정 → Strategy 직접 호출
        │
        └── loader_type=None
                │
                ▼
          PDFTypeRouter.route(filepath)
                │
          detect_pdf_type()     ← pymupdf로 빠른 사전 검사
          · 텍스트 밀도 < 50자/페이지  → scan
          · 이미지 면적 비율 ≥ 30%    → graph / mixed
          · 수평선 밀도 > 5개/페이지  → table
          · 나머지                    → text
                │
          _routing_table[pdf_type][0]  ← 1순위 loader_type 반환
                │
                ▼
          Strategy.load(filepath)  →  List[Document]
```

### 라우팅 테이블

| pdf_type | 1순위 | 2순위 | 3순위 |
|----------|-------|-------|-------|
| `text` | `pymupdf` | `pdfplumber` | — |
| `table` | `camelot` | `pdfplumber` | `tabula` |
| `graph` | `llamaparse` | `unstructured` | — |
| `scan` | `azure_di` | `textract` | `tesseract` |
| `mixed` | `pymupdf` | `unstructured` | `llamaparse` |

폴백이 필요하면 `rank` 파라미터로 2순위 지정:
```python
pdf_type, loader_type = PDFTypeRouter().route("file.pdf", rank=1)
```

---

## 지원 로더

| loader_type | 최적 유형 | 필요 조건 |
|-------------|----------|---------|
| `pymupdf` | text, mixed | `pip install PyMuPDF` |
| `pdfplumber` | text, table | `pip install pdfplumber` |
| `camelot` | table | `pip install camelot-py[cv]` + ghostscript |
| `tabula` | table | `pip install tabula-py` + Java |
| `unstructured` | mixed | `pip install unstructured` |
| `llamaparse` | graph | `pip install llama-parse` + `LLAMA_CLOUD_API_KEY` |
| `tesseract` | scan | `pip install pytesseract pdf2image` + tesseract, poppler |
| `textract` | scan | `pip install boto3` + AWS 자격증명 |
| `azure_di` | scan | `pip install azure-ai-formrecognizer` + Azure 자격증명 |

> lazy import 사용 — 미설치 로더는 자동 제외.

---

## 테스트

```bash
source venv/bin/activate

# 사용 가능한 로더 확인
python -m tests.test_pdf_loading --list-loaders

# 기본 테스트 (Router + 자동 라우팅)
python -m tests.test_pdf_loading path/to/file.pdf

# 전체 로더 일괄 비교
python -m tests.test_pdf_loading path/to/file.pdf --all

# 로딩 결과 내용 확인
python -m tests.test_pdf_loading path/to/file.pdf --inspect --page 1

# 결과 JSON 저장 (→ 청킹 단계 입력으로 사용)
python -m tests.test_pdf_loading path/to/file.pdf --loader pymupdf --save
```

---

## 파이프라인 연결

```python
from ragsystem.loading.pdf.loader_context import PDFLoaderContext
from ragsystem.chunking.chunking_context import ChunkingContext

docs   = PDFLoaderContext.LoadingPDFDatas("file.pdf")
chunks = ChunkingContext.ChunkingDocs(docs)
```

---

## 새 로더 추가

1. `strategies/{name}_strategy.py` 생성 — `PDFLoaderStrategy` 상속 후 `load()` 구현
2. `loader_context.py`의 `_make_strategies()` 에 `try/except` 블록 추가
3. `router.py`의 `_routing_table` 해당 pdf_type 리스트에 추가
4. 이 README 및 `.claude/src/loading/pdf/SKILL.md` 표 업데이트

상위 코드(`LoadingPDFDatas` 호출부)는 수정하지 않는다 (OCP).
