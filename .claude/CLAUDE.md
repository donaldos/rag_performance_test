# PDF RAG Pipeline — CLAUDE.md

## 프로젝트 개요

PDF 문서의 다양한 유형(텍스트 레이어, 표, 그래프/이미지, 스캔 OCR, 복합형)을 처리하여
VectorDB 기반 RAG 시스템을 구축하고 단계별 성능을 평가하는 파이프라인.

**구현 완료 단계**: Loading → Chunking → Embedding → VectorDB
**미구현 단계**: Evaluation (ragas, deepeval, mlflow 연동)

---

## 디렉터리 구조

```
src/
  loading/pdf/
    router.py              ← PDFTypeRouter (PDF 특성 감지 → loader_type 결정)
    loader_context.py      ← PDFLoaderContext (Router + Strategy 통합)
    strategies/            ← 9개 로더 구현체 (pymupdf, pdfplumber, camelot, tabula,
                                              unstructured, llamaparse, tesseract,
                                              textract, azure_di)
  chunking/
    router.py              ← ChunkingRouter (pdf_type → chunking_type 결정)
    chunking_context.py    ← ChunkingContext (Router + Strategy 통합)
    strategies/            ← 7개 청킹 전략 (recursive, token, sentence, semantic,
                                              page, markdown_header, parent_child)
  embedding/
    router.py              ← EmbeddingRouter (한글 비율 감지 → embedding_type 결정)
    embedding_context.py   ← EmbeddingContext (config/.env 자동 로드, Router + Strategy)
    strategies/            ← 3개 임베딩 모델 (openai_small, openai_large, huggingface_ko)
  vectordb/
    router.py              ← VectorDBRouter (청크 수 → vectordb_type 결정)
    vectordb_context.py    ← VectorDBContext (Router + Strategy 통합)
    strategies/            ← faiss_strategy.py, chroma_strategy.py
  evaluation/              ← (미구현)
  test/
    test_pdf_loading.py    ← Stage 1 단위 테스트
    test_chunking.py       ← Stage 2 단위 테스트 (--input JSON)
    test_embedding.py      ← Stage 3 단위 테스트 (--input JSON)
    test_vectordb.py       ← Stage 4 단위 테스트 (--input JSON, --query)
    io_utils.py            ← Document·EmbeddedChunk JSON 직렬화/역직렬화
    output/                ← 단계별 결과 JSON 저장
config/
  .env                     ← API 키 (커밋 금지, .gitignore 처리됨)
  .env.example             ← 키 템플릿
```

---

## 핵심 아키텍처 원칙

### Router + Strategy 통합 패턴 (전 단계 적용)

- **Router**: 입력 특성을 분석하여 최적 `*_type`을 자동 결정
- **Strategy**: `*_type`에 따라 구현체를 교체
- `*_type`을 명시하면 Router를 우회하고 해당 전략을 직접 사용 (Override)
- `*_type=None`이면 Router가 자동 결정

```
LoadingPDFDatas(path, loader_type=None)      → List[Document]
ChunkingDocs(docs, chunking_type=None)       → List[Document]
EmbeddingChunks(chunks, embedding_type=None) → List[EmbeddedChunk]
BuildVectorDB(embedded, vectordb_type=None)  → VectorDBStrategy
Search(store, query_embedding, k=5)          → List[SearchResult]
```

### 단계 간 데이터 타입

| 단계 | 입력 | 출력 |
|------|------|------|
| Loading | `str` (file path) | `List[Document]` |
| Chunking | `List[Document]` | `List[Document]` |
| Embedding | `List[Document]` | `List[EmbeddedChunk]` |
| VectorDB | `List[EmbeddedChunk]` | `VectorDBStrategy` (인스턴스) |

### 평가 시스템 (Ablation 방식)

```
PDF 유형 분류
  → 로더 평가 (CER ≤ 5%, TEDS ≥ 0.85)
  → 청킹 전략 평가 (Precision@5 ≥ 0.65)
  → 임베딩 모델 평가 (Recall@5 ≥ 0.70)
  → E2E RAG 검증 (RAGAS Faithfulness ≥ 0.80)
```

---

## 라우터별 결정 기준

### PDFTypeRouter (Loading)

| pdf_type | 판별 기준 | 1순위 로더 |
|----------|---------|---------|
| `text` | 텍스트 밀도 충분, 이미지/표 적음 | `pymupdf` |
| `table` | 수평선 밀도 > 5개/페이지 | `camelot` |
| `graph` | 이미지 면적 비율 ≥ 30% | `llamaparse` |
| `scan` | 텍스트 밀도 < 50자/페이지 | `azure_di` |
| `mixed` | 이미지 + 표 혼합 | `pymupdf` |

### ChunkingRouter (Chunking)

| pdf_type | 1순위 | 2순위 |
|----------|-------|-------|
| `text` | `recursive` | `semantic` |
| `table` | `page` | `markdown_header` |
| `graph` | `page` | — |
| `scan` | `sentence` | `recursive` |
| `mixed` | `recursive` | `semantic` |

### EmbeddingRouter (Embedding)

| language | 판별 기준 | 1순위 모델 |
|----------|---------|---------|
| `ko` | 한글 비율 ≥ 20% | `huggingface_ko` |
| `mixed` | 한글 비율 5~20% | `openai_small` |
| `en` | 한글 비율 < 5% | `openai_small` |

### VectorDBRouter (VectorDB)

| size_type | 판별 기준 | 1순위 DB |
|-----------|---------|---------|
| `small` | 청크 수 < 500 | `chromadb` |
| `large` | 청크 수 ≥ 500 | `faiss` |

---

## PDF 유형 분류

| 유형 코드 | 설명 | 권장 로더 |
|-----------|------|----------|
| `text` | 네이티브 텍스트 레이어 PDF | pymupdf, pdfplumber |
| `table` | 표 중심 PDF | camelot, tabula |
| `graph` | 그래프·이미지 포함 PDF | llamaparse, unstructured |
| `scan` | 스캔 PDF (OCR 필요) | tesseract, textract, azure_di |
| `mixed` | 복합형 | pymupdf, unstructured |

---

## 평가 데이터셋

| 평가 대상 | 데이터셋 | 비고 |
|----------|---------|------|
| 로더 파싱 품질 | OmniDocBench (CVPR 2025) | 텍스트·표·수식·읽기순서 GT 포함 |
| 재무 문서 RAG E2E | FinanceBench (150개 공개) | 표+텍스트 혼합 PDF |
| 일반 RAG E2E | RAGBench (100K) | 텍스트 문서 중심 |
| 한국어 도메인 | RAGAS TestsetGenerator 자체 구축 | Silver → 전문가 검수 → Gold |

---

## 코딩 규칙

- 모든 전략 구현체는 ABC를 상속하고 추상 메서드를 반드시 구현한다.
- 새 전략 추가 시 `strategies/` 하위에 파일 추가 후 `_make_strategies()` dict와 `_routing_table`에만 등록. 상위 코드(`*Context`)는 수정하지 않는다 (OCP).
- lazy import 패턴: `_make_strategies()` 내 각 전략을 `try/except (ImportError, Exception)` 블록으로 감싸 미설치 의존성 자동 제외.
- `Document.metadata`에 단계별 메타데이터 누적: `loader_type`, `pdf_type`, `auto_routed`, `chunking_type`, `chunk_index`, `embedding_model`, `embedding_dim` 등.
- 모든 실험 결과는 MLflow로 기록한다. 파라미터: `pdf_type`, `loader_type`, `auto_routed`, `chunk_size`, `overlap`, `embed_model`. 지표: `precision@5`, `recall@5`, `mrr`, `faithfulness`.
- Gold Dataset은 `data/gold/{pdf_type}/questions.json` 형식으로 관리한다.

---

## 의존성 (주요)

```
# Loading
PyMuPDF, pdfplumber, camelot-py, tabula-py
unstructured[all-docs], llama-parse
pytesseract, pdf2image, boto3, azure-ai-formrecognizer

# Chunking
langchain, langchain-community, langchain-core
langchain-text-splitters, tiktoken, sentence-transformers, langchain-experimental

# Embedding
python-dotenv, langchain-openai, langchain-huggingface

# VectorDB
faiss-cpu, chromadb

# Evaluation
ragas, deepeval, mlflow
```

---

## 관련 SKILL 문서

| 문서 | 내용 |
|------|------|
| `.claude/src/loading/pdf/SKILL.md` | PDF 로더 구현 가이드 (코드 포함) |
| `.claude/src/chunking/SKILL.md` | 청킹 전략 가이드 |
| `.claude/src/embedding/SKILL.md` | 임베딩 모델 가이드 |
| `.claude/src/vectordb/SKILL.md` | VectorDB 가이드 |
