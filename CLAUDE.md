# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 상태

**Loading → Chunking → Embedding → VectorDB 4단계 구현 완료.** 다음 단계는 Evaluation.

---

## 개발 환경

```bash
# 가상환경 (Python 3.9)
source venv/bin/activate

# 전체 의존성 설치
pip install -r requirements.txt

# 핵심 최소 설치 (Loading + Chunking + Embedding + VectorDB)
pip install PyMuPDF pdfplumber langchain langchain-core langchain-community
pip install langchain-text-splitters tiktoken sentence-transformers langchain-experimental
pip install python-dotenv langchain-openai langchain-huggingface
pip install faiss-cpu chromadb
```

API 키는 `config/.env`에 설정한다 (`config/.env.example` 참고).

---

## 아키텍처: Router + Strategy Pattern

파이프라인 전 단계에 **Router + Strategy 통합 패턴**을 적용한다.

```
src/
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
    embedding_context.py← EmbeddingContext: config/.env 자동 로드, Router + Strategy 통합
    strategies/        ← base.py + *_strategy.py (3개 모델)
  vectordb/
    router.py          ← VectorDBRouter: 청크 수 → vectordb_type 결정
    vectordb_context.py← VectorDBContext: Router + Strategy 통합
    strategies/        ← base.py + faiss_strategy.py + chroma_strategy.py
  evaluation/          ← (미구현)
  test/
    test_pdf_loading.py← PDF 로딩 단위 테스트
    test_chunking.py   ← 청킹 단위 테스트 (--input JSON)
    test_embedding.py  ← 임베딩 단위 테스트 (--input JSON)
    test_vectordb.py   ← VectorDB 단위 테스트 (--input JSON, --query)
    io_utils.py        ← save/load Document·EmbeddedChunk JSON 유틸
    output/            ← 단계별 결과 JSON 저장 디렉터리
```

### 단계별 인터페이스

| 단계 | 함수 시그니처 | 입력 | 출력 |
|------|------------|------|------|
| Loading | `LoadingPDFDatas(path, loader_type=None)` | `str` | `List[Document]` |
| Chunking | `ChunkingDocs(docs, chunking_type=None)` | `List[Document]` | `List[Document]` |
| Embedding | `EmbeddingChunks(chunks, embedding_type=None)` | `List[Document]` | `List[EmbeddedChunk]` |
| VectorDB | `BuildVectorDB(embedded, vectordb_type=None)` | `List[EmbeddedChunk]` | `VectorDBStrategy` |
| 검색 | `Search(store, query_embedding, k=5)` | `VectorDBStrategy` + `List[float]` | `List[SearchResult]` |

`*_type=None`이면 Router가 자동 결정, 명시하면 Override.

### 라우터 결정 기준

| 단계 | Router 입력 | 결정 기준 |
|------|------------|---------|
| Loading | PDF 파일 | 텍스트밀도, 이미지비율, 수평선밀도 |
| Chunking | `docs[0].metadata["pdf_type"]` | pdf_type → 전략 매핑 |
| Embedding | 청크 샘플 텍스트 | 한글 비율 (≥20%→ko, 5~20%→mixed, <5%→en) |
| VectorDB | 청크 수 | < 500 → chromadb, ≥ 500 → faiss |

---

## 단계별 테스트 명령어

```bash
# Stage 1: Loading → JSON 저장
python -m src.test.test_pdf_loading path/to/file.pdf --loader pymupdf --save

# Stage 2: Chunking (Loading JSON 입력)
python -m src.test.test_chunking \
  --input src/test/output/파일_pymupdf_loading.json \
  --chunker recursive --save

# Stage 3: Embedding (Chunking JSON 입력)
python -m src.test.test_embedding \
  --input src/test/output/파일_recursive_chunking.json \
  --embedder openai_small --save

# Stage 4: VectorDB (Embedding JSON 입력)
python -m src.test.test_vectordb \
  --input src/test/output/파일_openai_small_embedding.json \
  --db faiss --query "검색 쿼리"

# 각 단계 --all 옵션으로 전략 일괄 비교 가능
```

---

## 핵심 코딩 규칙

- 각 단계 구현체는 ABC를 상속하고 추상 메서드를 구현한다.
- 새 구현체 추가 시 `*Context` 클래스는 수정하지 않는다. `_make_strategies()` dict와 `_routing_table`에만 등록 (OCP).
- 모든 단계에서 `Document.metadata`에 단계별 메타데이터(`loader_type`, `pdf_type`, `chunking_type`, `embedding_model`, `auto_routed_*`)를 포함한다.
- 실험은 MLflow로 기록한다. 파라미터: `pdf_type`, `loader_type`, `auto_routed`, `chunk_size`, `overlap`, `embed_model`.
- lazy import 패턴: `_make_strategies()` 내 각 전략을 `try/except (ImportError, Exception)` 블록으로 감싸 미설치 의존성 자동 제외.

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
| [`.claude/src/loading/pdf/SKILL.md`](.claude/src/loading/pdf/SKILL.md) | PDF 로더 구현 가이드 (코드 포함) |
| [`.claude/src/chunking/SKILL.md`](.claude/src/chunking/SKILL.md) | 청킹 전략 가이드 |
| [`.claude/src/embedding/SKILL.md`](.claude/src/embedding/SKILL.md) | 임베딩 모델 가이드 |
| [`.claude/src/vectordb/SKILL.md`](.claude/src/vectordb/SKILL.md) | VectorDB 가이드 |
| [`src/loading/pdf/README.md`](src/loading/pdf/README.md) | PDF 로더 모듈 레퍼런스 |
| [`src/chunking/README.md`](src/chunking/README.md) | 청킹 모듈 레퍼런스 |
| [`src/embedding/README.md`](src/embedding/README.md) | 임베딩 모듈 레퍼런스 |
| [`src/vectordb/README.md`](src/vectordb/README.md) | VectorDB 모듈 레퍼런스 |
