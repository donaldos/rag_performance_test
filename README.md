# evalRAG — PDF RAG Pipeline

PDF 문서를 로딩부터 LLM 답변 생성까지 처리하고, 각 단계를 독립적으로 평가하는 RAG 파이프라인.

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
⑤ RAG       → 최종 답변             simple / self / adaptive  ← LangGraph
 │
 ▼
⑥ Evaluation (예정)                RAGAS / DeepEval / MLflow
```

① ~ ④ 각 단계는 **Router + Strategy 패턴**으로 구현되어 있다.
`*_type=None` 이면 Router가 입력 특성을 분석하여 최적 구현체를 자동 선택하고,
`*_type="명시"` 이면 Router를 우회한다.

⑤ RAG 단계는 **LangGraph** 기반 워크플로우로 `rag_type` 파라미터로 교체할 수 있다.

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

### 전체 파이프라인 (① ~ ⑤)

```python
from ragsystem.loading.pdf.loader_context import PDFLoaderContext
from ragsystem.chunking.chunking_context import ChunkingContext
from ragsystem.embedding.embedding_context import EmbeddingContext
from ragsystem.vectordb.vectordb_context import VectorDBContext
from ragsystem.rag.rag_context import RAGContext

# ① → ② → ③ → ④
docs     = PDFLoaderContext.LoadingPDFDatas("data/01.pdf")
chunks   = ChunkingContext.ChunkingDocs(docs)
embedded = EmbeddingContext.EmbeddingChunks(chunks)
store    = VectorDBContext.BuildVectorDB(embedded)

# ⑤ RAG 답변 생성 (rag_type: "simple" | "self" | "adaptive")
result = RAGContext.ask(store, question="질문 텍스트", rag_type="self")
print(result["answer"])
```

### 수동 지정 (Router 우회)

```python
from ragsystem.loading.pdf.loader_context import PDFLoaderContext
from ragsystem.chunking.chunking_context import ChunkingContext
from ragsystem.embedding.embedding_context import EmbeddingContext
from ragsystem.vectordb.vectordb_context import VectorDBContext
from ragsystem.rag.rag_context import RAGContext

docs     = PDFLoaderContext.LoadingPDFDatas("file.pdf", loader_type="pymupdf")
chunks   = ChunkingContext.ChunkingDocs(docs, chunking_type="recursive")
embedded = EmbeddingContext.EmbeddingChunks(chunks, embedding_type="openai_small")
store    = VectorDBContext.BuildVectorDB(embedded, vectordb_type="chromadb")
result   = RAGContext.ask(store, question="질문", rag_type="adaptive", llm_model="gpt-4o")
```

---

## 단계별 테스트

각 단계는 독립 실행 가능하다. 이전 단계 결과를 JSON으로 저장하면 다음 단계 입력으로 사용할 수 있다.

### ① Loading

```bash
# PDF 로딩 + JSON 저장
python -m tests.test_pdf_loading data/01.pdf --loader pymupdf --save

# 로딩 결과 내용 확인 (PDF 없이 JSON으로 검사)
python -m tests.test_pdf_loading --input tests/output/01_pymupdf_loading.json --inspect

# 모든 로더 일괄 비교
python -m tests.test_pdf_loading data/01.pdf --all
```

### ② Chunking

```bash
# 청킹 + JSON 저장
python -m tests.test_chunking --input tests/output/01_pymupdf_loading.json --chunker recursive --save

# 결과 확인
python -m tests.test_chunking --input tests/output/...json --inspect --chunk-index 0

# 전체 전략 비교
python -m tests.test_chunking --input tests/output/...json --all
```

### ③ Embedding

```bash
# 임베딩 + JSON 저장
python -m tests.test_embedding --input tests/output/..._chunking.json --embedder openai_small --save

# 벡터 미리보기
python -m tests.test_embedding --input tests/output/..._chunking.json --inspect --chunk-index 0
```

### ④ VectorDB

```bash
# 인덱스 구축 + 검색 테스트
python -m tests.test_vectordb --input tests/output/..._embedding.json --query "검색어"

# 특정 DB 지정
python -m tests.test_vectordb --input ...json --db faiss --query "검색어"
```

### ⑤ RAG (LangGraph)

```bash
# Self-RAG (기본)
python -m tests.test_rag \
    --input tests/output/..._embedding.json \
    --query "질문 텍스트"

# 세 가지 워크플로우 일괄 비교
python -m tests.test_rag \
    --input tests/output/..._embedding.json \
    --query "질문 텍스트" \
    --rag all

# 파라미터 조정
python -m tests.test_rag \
    --input ...json \
    --query "질문" \
    --rag adaptive \
    --llm gpt-4o \
    --k 10 \
    --db faiss
```

---

## RAG 워크플로우

### 워크플로우 비교

| rag_type | 구성 노드 | 특징 |
|----------|-----------|------|
| `simple` | retrieve → generate | 빠름, 환각 검증 없음 |
| `self` | retrieve → grade → generate → hallucination check | 관련성 필터 + 환각 검증 |
| `adaptive` | route → (direct_generate \| self 경로) | 일반 질문은 VectorDB 검색 생략 |

### Self-RAG 흐름

```
retrieve → grade_documents ──(relevant)──→ generate → check_hallucination → END
                │                                              │
           (irrelevant)                               (hallucinated)
                │                                              │
          rewrite_query ──→ retrieve (재시도, 최대 2회)    generate (재시도)
```

### Adaptive RAG 흐름

```
route_question ──(general)──→ direct_generate → END
      │
  (vectorstore)
      │
   (Self-RAG 동일 경로)
```

### `--rag all` 비교 출력 예시

```
  rag_type      소요(ms)   답변(자)  retry  관련성      환각        route
  simple          2,855        83      0
  self            9,132        83      0    relevant   grounded
  adaptive        7,918       427      0               grounded    general
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

### VectorDB 자동 선택

| 조건 | 1순위 |
|------|-------|
| 청크 수 < 500 | `chromadb` |
| 청크 수 ≥ 500 | `faiss` |

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
├── ragsystem/         ← RAG 파이프라인 핵심 로직 (pip install -e . 로 패키지화)
│   ├── loading/pdf/   ← PDF 로더 (Router + 9개 전략)
│   ├── chunking/      ← 청킹 (Router + 7개 전략)
│   ├── embedding/     ← 임베딩 (Router + 3개 전략)
│   ├── vectordb/      ← VectorDB (Router + FAISS/ChromaDB)
│   ├── rag/           ← LangGraph RAG 워크플로우
│   │   ├── simple_rag/    ← retrieve → generate
│   │   ├── self_rag/      ← + grade, rewrite, hallucination check
│   │   ├── adaptive_rag/  ← + route_question, direct_generate
│   │   ├── rag_context.py ← 통합 진입점 (rag_type 파라미터)
│   │   └── state.py       ← 공통 GraphState
│   └── utils/         ← 공통 유틸 (logger)
├── api/               ← FastAPI 서버 (스켈레톤)
│   ├── main.py
│   ├── routers/       ← upload.py, pipeline.py, rag.py
│   ├── models/        ← Pydantic 요청/응답 모델
│   └── services/      ← session_service.py
├── frontend/          ← Streamlit UI (스켈레톤)
│   ├── app.py
│   ├── pages/         ← upload.py, pipeline.py, rag.py
│   └── components/    ← step_card.py, result_table.py, api_client.py
├── tests/             ← 단계별 테스트 스크립트 + io_utils
│   └── output/        ← 단계별 결과 JSON 저장
├── config/
│   ├── .env.example   ← API 키 템플릿
│   └── .env           ← 실제 키 (git 제외)
├── data/              ← 테스트용 PDF 파일
├── logs/
│   └── rag_pipeline.log ← 파이프라인 실행 로그 (DEBUG+)
├── pyproject.toml     ← 패키지 설정
├── requirements.txt
└── CLAUDE.md
```

### 각 모듈 상세

- [ragsystem/loading/pdf/README.md](ragsystem/loading/pdf/README.md) — PDF 로더 가이드
- [ragsystem/chunking/README.md](ragsystem/chunking/README.md) — 청킹 전략 가이드
- [ragsystem/embedding/README.md](ragsystem/embedding/README.md) — 임베딩 모델 가이드
- [ragsystem/vectordb/README.md](ragsystem/vectordb/README.md) — VectorDB 구축·검색 가이드
- [ragsystem/rag/simple_rag/SKILL.md](ragsystem/rag/simple_rag/SKILL.md) — Simple RAG 가이드
- [ragsystem/rag/self_rag/SKILL.md](ragsystem/rag/self_rag/SKILL.md) — Self-RAG 가이드
- [ragsystem/rag/adaptive_rag/SKILL.md](ragsystem/rag/adaptive_rag/SKILL.md) — Adaptive RAG 가이드
- [tests/README.md](tests/README.md) — 테스트 스크립트 사용 가이드

---

## 로그 확인

```bash
# 실시간 로그 확인
tail -f logs/rag_pipeline.log

# WARNING 이상만 필터
grep -E "WARNING|ERROR" logs/rag_pipeline.log
```
