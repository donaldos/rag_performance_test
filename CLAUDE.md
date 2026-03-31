# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 상태

**Loading → Chunking → Embedding → VectorDB → RAG (Simple/Self/Adaptive) 5단계 구현 완료.**
FastAPI(`api/`) + Streamlit(`frontend/`) 웹 레이어는 스켈레톤 상태 (SKILL.md 기반 구현 예정).

---

## 개발 환경

```bash
# 가상환경 (Python 3.9)
source venv/bin/activate

# 패키지 설치 (editable mode)
pip install -e .
pip install -r requirements.txt

# API 키 설정
cp config/.env.example config/.env
# config/.env 열어 OPENAI_API_KEY 입력

# API 서버 실행
uvicorn api.main:app --reload --port 8000

# 프론트엔드 실행
streamlit run frontend/app.py --server.port 8501
```

---

## 디렉터리 구조

```
evalRAG/
├── ragsystem/         ← RAG 파이프라인 핵심 로직 (pip install -e . 로 패키지화)
│   ├── loading/pdf/   ← PDFLoaderContext + PDFTypeRouter + 9개 전략
│   ├── chunking/      ← ChunkingContext + ChunkingRouter + 7개 전략
│   ├── embedding/     ← EmbeddingContext + EmbeddingRouter + 3개 모델
│   ├── vectordb/      ← VectorDBContext + VectorDBRouter + FAISS/ChromaDB
│   ├── rag/           ← LangGraph RAG 워크플로우
│   │   ├── simple_rag/   ← retrieve → generate
│   │   ├── self_rag/     ← + grade, rewrite, hallucination check
│   │   ├── adaptive_rag/ ← + route_question, direct_generate
│   │   ├── rag_context.py← RAGContext.ask() 통합 진입점
│   │   └── state.py      ← GraphState TypedDict
│   └── utils/         ← logger
├── api/               ← FastAPI 서버 (스켈레톤)
│   ├── main.py
│   ├── routers/       ← upload.py, pipeline.py, rag.py
│   ├── models/        ← request/response Pydantic 모델
│   └── services/      ← session_service.py
├── frontend/          ← Streamlit UI (스켈레톤)
│   ├── app.py
│   ├── pages/         ← upload.py, pipeline.py, rag.py
│   └── components/    ← step_card.py, result_table.py, api_client.py
├── tests/             ← 단계별 테스트 스크립트
│   ├── test_pdf_loading.py
│   ├── test_chunking.py
│   ├── test_embedding.py
│   ├── test_vectordb.py
│   ├── test_rag.py
│   ├── io_utils.py
│   └── output/        ← 단계별 결과 JSON 저장
├── config/            ← .env, .env.example
├── data/              ← 테스트 PDF
└── pyproject.toml     ← 패키지 설정 (ragsystem, api, frontend)
```

---

## 아키텍처: Router + Strategy Pattern

```
ragsystem/
  loading/pdf/
    router.py          ← PDFTypeRouter: PDF 특성 분석 → loader_type 자동 결정
    loader_context.py  ← PDFLoaderContext: Router + Strategy 통합
    strategies/        ← base.py + *_strategy.py (9개 로더)
  chunking/
    router.py          ← ChunkingRouter: pdf_type 메타데이터 → chunking_type 결정
    chunking_context.py← ChunkingContext: Router + Strategy 통합
    strategies/        ← base.py + *_strategy.py (7개 전략)
  embedding/
    router.py          ← EmbeddingRouter: 한글 비율 감지 → embedding_type 결정
    embedding_context.py← EmbeddingContext: Router + Strategy 통합
    strategies/        ← base.py + *_strategy.py (3개 모델)
  vectordb/
    router.py          ← VectorDBRouter: 청크 수 → vectordb_type 결정
    vectordb_context.py← VectorDBContext: Router + Strategy 통합
    strategies/        ← base.py + faiss_strategy.py + chroma_strategy.py
  rag/
    rag_context.py     ← RAGContext.ask(store, question, rag_type, ...) 통합 진입점
    state.py           ← GraphState TypedDict (question, context, answer, retry_count, ...)
    simple_rag/graph.py← retrieve → generate → END
    self_rag/graph.py  ← retrieve → grade → (generate|rewrite) → hallucination → END
    adaptive_rag/graph.py← route → (direct_generate | self_rag 경로) → END
```

### 단계별 인터페이스

| 단계 | 함수 시그니처 | 입력 | 출력 |
|------|------------|------|------|
| Loading | `LoadingPDFDatas(path, loader_type=None)` | `str` | `List[Document]` |
| Chunking | `ChunkingDocs(docs, chunking_type=None)` | `List[Document]` | `List[Document]` |
| Embedding | `EmbeddingChunks(chunks, embedding_type=None)` | `List[Document]` | `List[EmbeddedChunk]` |
| VectorDB | `BuildVectorDB(embedded, vectordb_type=None)` | `List[EmbeddedChunk]` | `VectorDBStrategy` |
| 검색 | `Search(store, query_embedding, k=5)` | `VectorDBStrategy` + `List[float]` | `List[SearchResult]` |
| RAG | `RAGContext.ask(store, question, rag_type, ...)` | `VectorDBStrategy` + `str` | `dict` |

`*_type=None`이면 Router가 자동 결정, 명시하면 Override.

### RAG 워크플로우 (`rag_type` 파라미터)

| rag_type | 구성 | 특징 |
|----------|------|------|
| `simple` | retrieve → generate | 빠름, 환각 검증 없음 |
| `self` | retrieve → grade → generate → hallucination check | 관련성 필터 + 환각 검증 |
| `adaptive` | route → (direct_generate \| self 경로) | 일반 질문은 VectorDB 검색 생략 |

---

## 단계별 테스트 명령어

```bash
# Stage 1: Loading → JSON 저장
python -m tests.test_pdf_loading path/to/file.pdf --loader pymupdf --save

# Stage 2: Chunking (Loading JSON 입력)
python -m tests.test_chunking \
  --input tests/output/파일_pymupdf_loading.json \
  --chunker recursive --save

# Stage 3: Embedding (Chunking JSON 입력)
python -m tests.test_embedding \
  --input tests/output/파일_recursive_chunking.json \
  --embedder openai_small --save

# Stage 4: VectorDB (Embedding JSON 입력)
python -m tests.test_vectordb \
  --input tests/output/파일_openai_small_embedding.json \
  --db faiss --query "검색 쿼리"

# Stage 5: RAG (Embedding JSON 입력)
python -m tests.test_rag \
  --input tests/output/파일_openai_small_embedding.json \
  --query "질문 텍스트" --rag self

# 세 워크플로우 일괄 비교
python -m tests.test_rag \
  --input tests/output/파일_openai_small_embedding.json \
  --query "질문 텍스트" --rag all
```

---

## 핵심 코딩 규칙

- 각 단계 구현체는 ABC를 상속하고 추상 메서드를 구현한다.
- 새 구현체 추가 시 `*Context` 클래스는 수정하지 않는다. `_make_strategies()` dict와 `_routing_table`에만 등록 (OCP).
- 모든 단계에서 `Document.metadata`에 단계별 메타데이터(`loader_type`, `pdf_type`, `chunking_type`, `embedding_model`, `auto_routed_*`)를 포함한다.
- lazy import 패턴: `_make_strategies()` 내 각 전략을 `try/except (ImportError, Exception)` 블록으로 감싸 미설치 의존성 자동 제외.
- 실험은 MLflow로 기록한다.

---

## 평가 품질 게이트

| 단계 | 지표 | 통과 기준 |
|------|------|---------|
| 로더 | CER | ≤ 5% |
| 로더 | TEDS (표 구조) | ≥ 0.85 |
| 청킹 | Precision@5 | ≥ 0.65 |
| 임베딩 | Recall@5 | ≥ 0.70 |
| E2E | RAGAS Faithfulness | ≥ 0.80 |

Gold Dataset: `data/gold/{pdf_type}/questions.json`

---

## 상세 문서

| 파일 | 내용 |
|------|------|
| [`.claude/CLAUDE.md`](.claude/CLAUDE.md) | 전체 설계 원칙, 평가 데이터셋 |
| [`.claude/src/loading/pdf/SKILL.md`](.claude/src/loading/pdf/SKILL.md) | PDF 로더 구현 가이드 |
| [`.claude/src/chunking/SKILL.md`](.claude/src/chunking/SKILL.md) | 청킹 전략 가이드 |
| [`.claude/src/embedding/SKILL.md`](.claude/src/embedding/SKILL.md) | 임베딩 모델 가이드 |
| [`.claude/src/vectordb/SKILL.md`](.claude/src/vectordb/SKILL.md) | VectorDB 가이드 |
| [`.claude/api/SKILL.md`](.claude/api/SKILL.md) | FastAPI 엔드포인트 설계 가이드 |
| [`.claude/frontend/SKILL.md`](.claude/frontend/SKILL.md) | Streamlit UI 구현 가이드 |
| [`tests/README.md`](tests/README.md) | 테스트 스크립트 사용 가이드 |
