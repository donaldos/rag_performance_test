# src/test — 단계별 테스트 가이드

각 파이프라인 단계를 독립적으로 실행하고 결과를 JSON으로 저장·연결하는 테스트 스크립트 모음.

---

## 파일 구조

```
tests/
├── test_pdf_loading.py   ← ① PDF 로딩 테스트
├── test_chunking.py      ← ② 청킹 테스트
├── test_embedding.py     ← ③ 임베딩 테스트
├── test_vectordb.py      ← ④ VectorDB 구축·검색 테스트
├── test_rag.py           ← ⑤ LangGraph RAG 워크플로우 테스트
├── io_utils.py           ← JSON 직렬화/역직렬화 유틸
└── output/               ← 각 단계 저장 결과 (git 제외)
```

---

## 단계 간 데이터 흐름

```
PDF 파일
  │
  │  python -m tests.test_pdf_loading  --save
  ▼
output/{stem}_{loader}_loading.json          (List[Document])
  │
  │  python -m tests.test_chunking  --save
  ▼
output/{stem}_{chunker}_chunking.json        (List[Chunk])
  │
  │  python -m tests.test_embedding  --save
  ▼
output/{stem}_{chunker}_{embedder}_embedding.json   (List[EmbeddedChunk])
  │
  │  python -m tests.test_vectordb  --query "..."
  ▼
VectorDB (인메모리 또는 --save로 디스크 저장)
  │
  │  python -m tests.test_rag  --query "..."
  ▼
최종 LLM 답변
```

---

## ① test_pdf_loading.py

PDF를 로딩하여 `List[Document]`로 변환하고, 결과를 JSON으로 저장한다.

### 기본 옵션

| 옵션 | 설명 |
|------|------|
| `PDF_PATH` (위치 인자) | 로딩할 PDF 파일 경로 |
| `--loader` | 로더 지정 (`pymupdf`, `pdfplumber`, `camelot`, `tabula`, `unstructured`, `llamaparse`, `tesseract`, `textract`, `azure_di`) |
| `--save [PATH]` | 결과를 JSON으로 저장 (PATH 생략 시 자동 경로) |
| `--all` | 설치된 모든 로더 일괄 비교 |
| `--inspect` | 로딩된 문서 내용 페이지별 출력 |
| `--page N` | `--inspect` 시 특정 페이지만 출력 |
| `--input PATH` | 이전에 저장된 JSON으로 검사 (PDF 없이 재검사) |
| `--list-loaders` | 현재 사용 가능한 로더 목록 출력 |

### 명령어 예시

```bash
# 자동 라우팅으로 최적 로더 선택 후 저장
python -m tests.test_pdf_loading data/01.pdf --save

# 로더 직접 지정 + 저장
python -m tests.test_pdf_loading data/01.pdf --loader pymupdf --save

# 저장 경로 직접 지정
python -m tests.test_pdf_loading data/01.pdf --loader pdfplumber --save tests/output/01_pdfplumber_loading.json

# 설치된 모든 로더 일괄 비교 (속도·품질 비교용)
python -m tests.test_pdf_loading data/01.pdf --all

# 로딩 결과 내용 확인 (페이지별)
python -m tests.test_pdf_loading data/01.pdf --inspect
python -m tests.test_pdf_loading data/01.pdf --inspect --loader pdfplumber --page 2

# 이전에 저장한 JSON 재검사 (PDF 없이)
python -m tests.test_pdf_loading --input tests/output/01_pymupdf_loading.json --inspect

# 사용 가능한 로더 목록 확인
python -m tests.test_pdf_loading --list-loaders
```

### 출력 JSON 구조

```json
{
  "pdf_path": "data/01.pdf",
  "loader_type": "pymupdf",
  "created_at": "2026-03-31T12:00:00",
  "doc_count": 11,
  "documents": [
    {"page_content": "...", "metadata": {"page": 0, "loader_type": "pymupdf", ...}},
    ...
  ]
}
```

---

## ② test_chunking.py

`List[Document]` JSON을 입력받아 청킹하고 결과를 저장한다.

### 기본 옵션

| 옵션 | 설명 |
|------|------|
| `--input PATH` | 로딩 결과 JSON 경로 (필수) |
| `--chunker` | 청킹 전략 지정 (`recursive`, `token`, `sentence`, `page`, `markdown_header`, `parent_child`, `semantic`) |
| `--save [PATH]` | 결과를 JSON으로 저장 |
| `--all` | 설치된 모든 청킹 전략 일괄 비교 |
| `--inspect` | 청킹 결과 내용 출력 |
| `--chunk-index N` | `--inspect` 시 특정 청크만 출력 |
| `--list-chunkers` | 현재 사용 가능한 청킹 전략 목록 출력 |

### 명령어 예시

```bash
# 자동 라우팅 (pdf_type에 따라 최적 전략 선택)
python -m tests.test_chunking --input tests/output/01_pymupdf_loading.json

# 특정 전략 지정 + 저장
python -m tests.test_chunking \
    --input tests/output/01_pymupdf_loading.json \
    --chunker recursive \
    --save

# 모든 전략 성능 비교 (청크 수·평균 크기·소요 시간)
python -m tests.test_chunking \
    --input tests/output/01_pymupdf_loading.json \
    --all

# 청킹 결과 내용 확인
python -m tests.test_chunking \
    --input tests/output/01_pymupdf_loading.json \
    --inspect --chunk-index 0

# 사용 가능한 전략 목록
python -m tests.test_chunking --list-chunkers
```

### `--all` 비교 출력 예시

```
  recursive     : 44개 chunk | avg  874자 | 1ms   ← Router 추천
  token         : 52개 chunk | avg  682자 | 85ms
  sentence      : FAIL (sentence-transformers 미설치)
  page          : 11개 chunk | avg 2970자 | 0ms
  markdown_header: 11개 chunk | avg 2901자 | 2ms
  parent_child  : 123개 chunk | avg  551자 | 3ms
  결과: 5/6 통과
```

---

## ③ test_embedding.py

청킹 결과 JSON을 입력받아 임베딩하고 벡터를 저장한다.

### 기본 옵션

| 옵션 | 설명 |
|------|------|
| `--input PATH` | 청킹 결과 JSON 경로 (필수) |
| `--embedder` | 임베딩 모델 지정 (`openai_small`, `openai_large`, `huggingface_ko`) |
| `--save [PATH]` | 임베딩 벡터 포함 JSON 저장 |
| `--all` | 설치된 모든 임베더 일괄 비교 |
| `--inspect` | 벡터 미리보기 (첫 5개 값) |
| `--chunk-index N` | `--inspect` 시 특정 청크만 출력 |
| `--list-embedders` | 현재 사용 가능한 임베더 목록 출력 |

### 명령어 예시

```bash
# 자동 라우팅 (언어 감지: 한글 비율로 모델 선택)
python -m tests.test_embedding \
    --input tests/output/01_recursive_chunking.json

# 특정 임베더 지정 + 저장
python -m tests.test_embedding \
    --input tests/output/01_recursive_chunking.json \
    --embedder openai_small \
    --save

# 모든 임베더 비교 (차원·속도)
python -m tests.test_embedding \
    --input tests/output/01_recursive_chunking.json \
    --all

# 벡터 미리보기
python -m tests.test_embedding \
    --input tests/output/01_recursive_chunking.json \
    --inspect --chunk-index 0

# 사용 가능한 임베더 목록
python -m tests.test_embedding --list-embedders
```

### `--all` 비교 출력 예시

```
  openai_small    44개 chunk | dim 1536 | 3185ms | text-embedding-3-small
  openai_large    44개 chunk | dim 3072 | 2348ms | text-embedding-3-large
  huggingface_ko  FAIL (langchain-huggingface 미설치)
  결과: 2/3 통과
```

---

## ④ test_vectordb.py

임베딩 결과 JSON을 입력받아 VectorDB를 구축하고 검색을 테스트한다.

### 기본 옵션

| 옵션 | 설명 |
|------|------|
| `--input PATH` | 임베딩 결과 JSON 경로 (필수) |
| `--db` | VectorDB 지정 (`faiss`, `chromadb`) |
| `--query TEXT` | 검색 쿼리 텍스트 |
| `--k N` | 검색 결과 수 (기본: 5) |
| `--save [PATH]` | 인덱스를 디스크에 저장 |
| `--all` | faiss/chromadb 모두 비교 |
| `--list-dbs` | 현재 사용 가능한 VectorDB 목록 출력 |

### 명령어 예시

```bash
# 자동 라우팅 (청크 수 < 500 → chromadb, ≥ 500 → faiss)
python -m tests.test_vectordb \
    --input tests/output/01_recursive_chunking_openai_small_embedding.json

# 특정 DB 지정 + 검색
python -m tests.test_vectordb \
    --input tests/output/01_recursive_chunking_openai_small_embedding.json \
    --db faiss \
    --query "연구 방법론"

# 검색 결과 수 조정
python -m tests.test_vectordb \
    --input ...json \
    --db chromadb \
    --query "질문" \
    --k 10

# 인덱스 저장
python -m tests.test_vectordb \
    --input ...json \
    --db faiss \
    --save

# faiss / chromadb 일괄 비교
python -m tests.test_vectordb \
    --input ...json \
    --query "검색어" \
    --all

# 사용 가능한 DB 목록
python -m tests.test_vectordb --list-dbs
```

---

## ⑤ test_rag.py

임베딩 JSON → VectorDB 구축 → LangGraph RAG 워크플로우 실행을 한 번에 처리한다.

### 기본 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--input PATH` | 필수 | 임베딩 결과 JSON 경로 |
| `--query TEXT` | 필수 | 사용자 질문 |
| `--rag` | `self` | 워크플로우 (`simple` \| `self` \| `adaptive` \| `all`) |
| `--llm` | `gpt-4o-mini` | LLM 모델명 (`gpt-4o-mini`, `gpt-4o` 등) |
| `--k` | `5` | VectorDB 검색 결과 수 |
| `--db` | 자동 | VectorDB 종류 (`faiss` \| `chromadb`) |
| `--embed` | `openai_small` | 쿼리 임베딩 모델 |

### 워크플로우 종류

| rag_type | 구성 | 특징 |
|----------|------|------|
| `simple` | retrieve → generate | 빠름 (LLM 1회) |
| `self` | retrieve → grade → generate → hallucination_check | 관련성·환각 검증 (LLM 4~6회) |
| `adaptive` | route → (direct_generate \| self 경로) | 일반 질문 시 VectorDB 생략 |
| `all` | simple + self + adaptive 순서대로 비교 | 성능 비교용 |

### 명령어 예시

```bash
# Self-RAG (기본)
python -m tests.test_rag \
    --input tests/output/01_recursive_chunking_openai_small_embedding.json \
    --query "한국어 음성 발달에 영향을 미치는 요인은?"

# Simple RAG (빠른 확인용)
python -m tests.test_rag \
    --input ...json \
    --query "질문" \
    --rag simple

# Adaptive RAG (일반/문서 질문 혼합)
python -m tests.test_rag \
    --input ...json \
    --query "RAG란 무엇인가요?" \
    --rag adaptive

# 세 가지 워크플로우 일괄 비교
python -m tests.test_rag \
    --input ...json \
    --query "질문" \
    --rag all

# 파라미터 조정
python -m tests.test_rag \
    --input ...json \
    --query "질문" \
    --rag self \
    --llm gpt-4o \
    --k 10 \
    --db faiss
```

### `--rag all` 비교 출력 예시

```
  rag_type      소요(ms)   답변(자)  retry  관련성      환각        route
  simple          2,855        83      0
  self            9,132        83      0    relevant   grounded
  adaptive        7,918       427      0               grounded    general
```

---

## 전체 파이프라인 순차 실행 예시

```bash
PDF=data/01.pdf

# ① Loading
python -m tests.test_pdf_loading $PDF --loader pymupdf --save

# ② Chunking
python -m tests.test_chunking \
    --input tests/output/01_pymupdf_loading.json \
    --chunker recursive --save

# ③ Embedding
python -m tests.test_embedding \
    --input tests/output/01_recursive_chunking.json \
    --embedder openai_small --save

# ④ VectorDB 검색 확인
python -m tests.test_vectordb \
    --input tests/output/01_recursive_chunking_openai_small_embedding.json \
    --query "핵심 키워드"

# ⑤ RAG 답변 생성
python -m tests.test_rag \
    --input tests/output/01_recursive_chunking_openai_small_embedding.json \
    --query "질문 텍스트" \
    --rag self
```

---

## 전략별 비교 (`--all`) 활용 가이드

각 단계에서 `--all` 옵션으로 최적 전략을 선별한 뒤 다음 단계로 이어가는 것을 권장한다.

```
test_pdf_loading --all   → 가장 많은 텍스트를 추출하는 로더 선택
test_chunking    --all   → Router 추천 전략 또는 avg 청크 크기 균형 잡힌 전략 선택
test_embedding   --all   → 언어에 맞는 모델 선택 (한국어 → huggingface_ko)
test_vectordb    --all   → 검색 속도·유사도 점수 확인
test_rag         --all   → 답변 품질·소요 시간·환각 여부 비교
```

---

## io_utils.py — JSON 직렬화 유틸

| 함수 | 입출력 | 설명 |
|------|--------|------|
| `save_documents(docs, path)` | `List[Document]` → JSON | Loading/Chunking 결과 저장 |
| `load_documents(path)` | JSON → `(List[Document], meta)` | Loading/Chunking 결과 복원 |
| `load_embedded_chunks(path)` | JSON → `(List[EmbeddedChunk], meta)` | Embedding 결과 복원 |
| `default_save_path(pdf_path, loader_type, stage)` | → `Path` | 자동 저장 경로 생성 |
