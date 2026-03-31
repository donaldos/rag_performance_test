# Chunking Module

`List[Document]`를 입력받아 **Router + Strategy 패턴**으로 청킹하여 `List[Document]`를 반환하는 모듈.
파이프라인 2단계: Documents → Chunks.

---

## 파일 구조

```
chunking/
├── router.py             ← ChunkingRouter: pdf_type 메타데이터 → chunking_type 결정
├── chunking_context.py   ← ChunkingContext: Router + Strategy 통합 진입점
└── strategies/
    ├── base.py                      ← ChunkingStrategy (ABC)
    ├── recursive_strategy.py        ← 범용 재귀 분할 (기본값)
    ├── token_strategy.py            ← 토큰 수 기준 분할
    ├── sentence_strategy.py         ← 문장 경계 보존 분할
    ├── semantic_strategy.py         ← 임베딩 유사도 기반 의미 분할
    ├── page_strategy.py             ← 페이지 단위 그대로 사용
    ├── markdown_header_strategy.py  ← 헤더(#/##/###) 기준 섹션 분할
    └── parent_child_strategy.py     ← 부모(컨텍스트) + 자식(검색) 이중 청크
```

---

## 빠른 시작

```python
from src.chunking.chunking_context import ChunkingContext

# 자동 라우팅 — docs의 pdf_type 메타데이터로 최적 전략 선택
chunks = ChunkingContext.ChunkingDocs(docs)

# 수동 지정 — Router 우회
chunks = ChunkingContext.ChunkingDocs(docs, chunking_type="recursive")

# semantic 사용 시 — 임베딩 모델 주입 필요
from langchain_openai import OpenAIEmbeddings
ChunkingContext.set_embeddings(OpenAIEmbeddings())
chunks = ChunkingContext.ChunkingDocs(docs, chunking_type="semantic")

# 사용 가능한 전략 확인
print(ChunkingContext.available_chunkers())
```

반환값 `List[Document]` 각 청크의 추가 metadata:

| 키 | 타입 | 설명 |
|----|------|------|
| `chunking_type` | str | 실제 사용된 전략 |
| `chunk_index` | int | 전체 청크 순번 |
| `auto_routed_chunking` | bool | 자동 라우팅 여부 |
| `chunk_role` | str | `"parent"` / `"child"` (parent_child 전략 시) |
| `parent_id` | int | 부모 청크 인덱스 (parent_child 전략 시) |

---

## 전략 비교

| chunking_type | 특징 | 적합 pdf_type | 필요 조건 |
|---------------|------|-------------|---------|
| `recursive` | 단락→문장→단어 재귀 분할, 범용 | text, mixed | `langchain-text-splitters` |
| `token` | LLM 토크나이저 기준, 컨텍스트 윈도우 제어 | text | `tiktoken` |
| `sentence` | 문장 경계 보존 | scan | `sentence-transformers` |
| `semantic` | 임베딩 유사도로 의미 경계 감지 | text, mixed | `langchain-experimental` + 임베딩 모델 |
| `page` | 페이지 단위 그대로 | table, graph | 없음 |
| `markdown_header` | `#`/`##`/`###` 헤더 기준 섹션 분할 | table | `langchain-text-splitters` |
| `parent_child` | 큰 부모(2000자) + 작은 자식(400자) 이중 생성 | text, mixed | `langchain-text-splitters` |

---

## 라우팅 테이블

| pdf_type | 1순위 | 2순위 | 3순위 |
|----------|-------|-------|-------|
| `text` | `recursive` | `semantic` | `token` |
| `table` | `page` | `markdown_header` | — |
| `graph` | `page` | — | — |
| `scan` | `sentence` | `recursive` | — |
| `mixed` | `recursive` | `semantic` | — |

---

## 테스트

```bash
source venv/bin/activate

# 사용 가능한 전략 확인
python -m src.test.test_chunking --list-chunkers

# 기본 테스트 (JSON 입력 — test_pdf_loading.py --save 출력)
python -m src.test.test_chunking --input src/test/output/파일_pymupdf_loading.json

# 특정 전략 지정
python -m src.test.test_chunking --input 파일.json --chunker recursive

# 전체 전략 일괄 비교
python -m src.test.test_chunking --input 파일.json --all

# 결과 내용 확인
python -m src.test.test_chunking --input 파일.json --inspect --chunk-index 0

# 결과 JSON 저장 (→ 임베딩 단계 입력으로 사용)
python -m src.test.test_chunking --input 파일.json --chunker recursive --save
```

---

## 파이프라인 연결

```python
from src.loading.pdf.loader_context import PDFLoaderContext
from src.chunking.chunking_context import ChunkingContext
from src.embedding.embedding_context import EmbeddingContext

docs     = PDFLoaderContext.LoadingPDFDatas("file.pdf")
chunks   = ChunkingContext.ChunkingDocs(docs)
embedded = EmbeddingContext.EmbeddingChunks(chunks)
```

---

## 새 전략 추가

1. `strategies/{name}_strategy.py` 생성 — `ChunkingStrategy` 상속 후 `chunk()` 구현
2. `chunking_context.py`의 `_make_strategies()` 에 `try/except` 블록 추가
3. `router.py`의 `_routing_table` 해당 pdf_type 리스트에 추가
4. 이 README 및 `.claude/src/chunking/SKILL.md` 표 업데이트
