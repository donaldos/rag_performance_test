# evalRAG — PDF RAG Pipeline

PDF 문서를 로딩부터 VectorDB 구축까지 처리하고, 각 단계를 독립적으로 평가하는 RAG 파이프라인.

---

## 파이프라인 개요

```
PDF
 │
 ▼
① Loading   → List[Document]       pymupdf / pdfplumber / unstructured / ...
 │
 ▼
② Chunking  → List[Document]       recursive / sentence / token / semantic / ...
 │
 ▼
③ Embedding → List[EmbeddedChunk]  openai_small / openai_large / huggingface_ko
 │
 ▼
④ VectorDB  → VectorStore          faiss / chromadb
 │
 ▼
⑤ Evaluation (예정)                RAGAS / DeepEval / MLflow
```

각 단계는 **Router + Strategy 패턴**으로 구현되어 있다.
`*_type=None` 이면 Router가 입력 특성을 분석하여 최적 구현체를 자동 선택하고,
`*_type="명시"` 이면 Router를 우회한다.

---

## 개발 환경

**Python 3.9 / macOS**

```bash
# 가상환경 활성화
source venv/bin/activate

# 전체 의존성 설치
pip install -r requirements.txt

# API 키 설정
cp config/.env.example config/.env
# config/.env 열어 OPENAI_API_KEY 입력
```

### 시스템 의존성 (macOS)

| 패키지 | 필요 로더 | 설치 |
|--------|---------|------|
| ghostscript | camelot (표 PDF) | `brew install ghostscript` |
| Java | tabula (표 PDF) | `brew install openjdk` |
| tesseract | tesseract OCR (스캔 PDF) | `brew install tesseract tesseract-lang` |
| poppler | pdf2image (OCR 전처리) | `brew install poppler` |

---

## 빠른 시작

### 전체 파이프라인

```python
from src.loading.pdf.loader_context import PDFLoaderContext
from src.chunking.chunking_context import ChunkingContext
from src.embedding.embedding_context import EmbeddingContext
from src.vectordb.vectordb_context import VectorDBContext
from langchain_core.documents import Document

# ① → ② → ③ → ④
docs     = PDFLoaderContext.LoadingPDFDatas("data/01.pdf")
chunks   = ChunkingContext.ChunkingDocs(docs)
embedded = EmbeddingContext.EmbeddingChunks(chunks)
store    = VectorDBContext.BuildVectorDB(embedded)

# 검색
query_vec = EmbeddingContext.EmbeddingChunks(
    [Document(page_content="질문 텍스트")]
)[0].embedding
results = VectorDBContext.Search(store, query_vec, k=5)
for r in results:
    print(r.rank, r.score, r.document.page_content[:80])
```

### 수동 지정 (Router 우회)

```python
docs     = PDFLoaderContext.LoadingPDFDatas("file.pdf", loader_type="pymupdf")
chunks   = ChunkingContext.ChunkingDocs(docs, chunking_type="recursive")
embedded = EmbeddingContext.EmbeddingChunks(chunks, embedding_type="openai_small")
store    = VectorDBContext.BuildVectorDB(embedded, vectordb_type="chromadb")
```

---

## 단계별 테스트

각 단계는 독립 실행 가능하다. 이전 단계 결과를 JSON으로 저장하면 다음 단계 입력으로 사용할 수 있다.

### ① Loading

```bash
# PDF 로딩 + JSON 저장
python -m src.test.test_pdf_loading data/01.pdf --loader pymupdf --save

# 로딩 결과 내용 확인 (PDF 없이 JSON으로 검사)
python -m src.test.test_pdf_loading --input src/test/output/01_pymupdf_loading.json --inspect

# 모든 로더 일괄 비교
python -m src.test.test_pdf_loading data/01.pdf --all
```

### ② Chunking

```bash
# 청킹 + JSON 저장
python -m src.test.test_chunking --input src/test/output/01_pymupdf_loading.json --chunker recursive --save

# 결과 확인
python -m src.test.test_chunking --input src/test/output/...json --inspect --chunk-index 0

# 전체 전략 비교
python -m src.test.test_chunking --input src/test/output/...json --all
```

### ③ Embedding

```bash
# 임베딩 + JSON 저장
python -m src.test.test_embedding --input src/test/output/..._chunking.json --embedder openai_small --save

# 벡터 미리보기
python -m src.test.test_embedding --input src/test/output/..._chunking.json --inspect --chunk-index 0
```

### ④ VectorDB

```bash
# 인덱스 구축 + 검색 테스트
python -m src.test.test_vectordb --input src/test/output/..._embedding.json --query "검색어"

# 특정 DB 지정
python -m src.test.test_vectordb --input ...json --db faiss --query "검색어"
```

---

## 라우팅 동작

### PDF 유형 자동 감지 (Loading Router)

| pdf_type | 감지 조건 | 1순위 로더 | 2순위 |
|----------|---------|-----------|-------|
| `text` | 텍스트 밀도 ≥ 50자/페이지, 이미지 낮음 | `pymupdf` | `pdfplumber` |
| `table` | 수평선 밀도 > 5개/페이지 | `camelot` | `pdfplumber` |
| `graph` | 이미지 면적 비율 ≥ 30% | `llamaparse` | `unstructured` |
| `scan` | 텍스트 밀도 < 50자/페이지 | `azure_di` | `textract` |
| `mixed` | 이미지 있음 + 텍스트 있음 | `pymupdf` | `unstructured` |

미설치 로더는 자동으로 다음 순위로 폴백한다.

### 청킹 전략 자동 선택

| pdf_type | 1순위 | 2순위 |
|----------|-------|-------|
| `text` | `recursive` | `semantic` |
| `table` | `page` | `markdown_header` |
| `scan` | `sentence` | `recursive` |
| `mixed` | `recursive` | `semantic` |

### 임베딩 모델 자동 선택 (언어 감지)

| 언어 | 조건 | 1순위 |
|------|------|-------|
| `ko` | 한글 비율 ≥ 20% | `huggingface_ko` |
| `en` | 한글 비율 < 5% | `openai_small` |
| `mixed` | 한글 비율 5~20% | `openai_small` |

---

## 평가 품질 게이트

| 단계 | 지표 | 기준 |
|------|------|------|
| Loading | CER (문자 오류율) | ≤ 5% |
| Loading | TEDS (표 구조) | ≥ 0.85 |
| Chunking | Precision@5 | ≥ 0.65 |
| Embedding | Recall@5 | ≥ 0.70 |
| E2E | RAGAS Faithfulness | ≥ 0.80 |

---

## 디렉터리 구조

```
evalRAG/
├── config/
│   ├── .env.example        ← API 키 템플릿
│   └── .env                ← 실제 키 (git 제외)
├── data/                   ← 테스트용 PDF 파일
├── logs/
│   └── rag_pipeline.log    ← 파이프라인 실행 로그 (DEBUG+)
├── src/
│   ├── loading/pdf/        ← PDF 로더 (Router + 9개 전략)
│   ├── chunking/           ← 청킹 (Router + 7개 전략)
│   ├── embedding/          ← 임베딩 (Router + 3개 전략)
│   ├── vectordb/           ← VectorDB (Router + FAISS/ChromaDB)
│   ├── utils/              ← 공통 유틸 (logger)
│   └── test/               ← 단계별 테스트 스크립트 + io_utils
├── requirements.txt
└── CLAUDE.md
```

### 각 모듈 상세

- [src/loading/pdf/README.md](src/loading/pdf/README.md) — PDF 로더 가이드
- [src/chunking/README.md](src/chunking/README.md) — 청킹 전략 가이드
- [src/embedding/README.md](src/embedding/README.md) — 임베딩 모델 가이드
- [src/vectordb/README.md](src/vectordb/README.md) — VectorDB 구축·검색 가이드

---

## 로그 확인

```bash
# 실시간 로그 확인
tail -f logs/rag_pipeline.log

# WARNING 이상만 필터
grep -E "WARNING|ERROR" logs/rag_pipeline.log
```
