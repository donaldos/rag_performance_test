---
name: chunking
description: |
  Document 리스트를 Router + 전략 패턴으로 청킹하는 모듈.
  ChunkingDocs(docs, chunking_type=None) 인터페이스로 호출하며,
  chunking_type을 생략하면 ChunkingRouter가 docs의 pdf_type 메타데이터를 읽어 최적 전략을 선택한다.
  semantic 전략 사용 시 set_embeddings()로 임베딩 모델을 먼저 주입해야 한다.
  청킹 전략 선택, 추가, 평가 관련 작업에 반드시 사용한다.
---

# Chunking Skill

## 역할

Loading 단계의 `List[Document]`를 받아 RAG 검색에 최적화된 크기로 분할하고
`List[Document]` (청크)를 반환한다.

---

## 아키텍처: Router + Strategy 통합 패턴

```
ChunkingDocs(docs, chunking_type=None)
        │
        ▼
  chunking_type 지정됨?
    ├── Yes → ChunkingContext._strategies[chunking_type].chunk()
    └── No  → ChunkingRouter.route(docs)
                    │
              docs[0].metadata["pdf_type"] 읽기
                    │
              _routing_table[pdf_type][0]
                    │
                    ▼
             Strategy.chunk(docs)  →  List[Document]
```

---

## 지원 chunking_type 목록

| chunking_type | 클래스 | 의미 경계 | 필요 조건 |
|---------------|--------|---------|---------|
| `recursive` | `RecursiveChunkingStrategy` | 단락/문장/단어 재귀 | `langchain-text-splitters` |
| `token` | `TokenChunkingStrategy` | LLM 토큰 수 | `tiktoken` |
| `sentence` | `SentenceChunkingStrategy` | 문장 | `sentence-transformers` |
| `semantic` | `SemanticChunkingStrategy` | 임베딩 유사도 | `langchain-experimental` + 임베딩 모델 |
| `page` | `PageChunkingStrategy` | 페이지 단위 | 없음 |
| `markdown_header` | `MarkdownHeaderChunkingStrategy` | `#`/`##`/`###` 헤더 | `langchain-text-splitters` |
| `parent_child` | `ParentChildChunkingStrategy` | 부모+자식 이중 청크 | `langchain-text-splitters` |

---

## 라우팅 테이블 (pdf_type → chunking_type 우선순위)

| pdf_type | 1순위 | 2순위 | 3순위 |
|----------|-------|-------|-------|
| `text` | `recursive` | `semantic` | `token` |
| `table` | `page` | `markdown_header` | — |
| `graph` | `page` | — | — |
| `scan` | `sentence` | `recursive` | — |
| `mixed` | `recursive` | `semantic` | — |

---

## 인터페이스

```python
from src.chunking.chunking_context import ChunkingContext

# 자동 라우팅
chunks = ChunkingContext.ChunkingDocs(docs)

# 수동 Override
chunks = ChunkingContext.ChunkingDocs(docs, chunking_type="recursive")

# semantic — 임베딩 모델 주입 필수
from langchain_openai import OpenAIEmbeddings
ChunkingContext.set_embeddings(OpenAIEmbeddings())
chunks = ChunkingContext.ChunkingDocs(docs, chunking_type="semantic")

# 사용 가능 목록
ChunkingContext.available_chunkers()
```

---

## 구현 코드 요약

### 추상 인터페이스 (`strategies/base.py`)

```python
class ChunkingStrategy(ABC):
    @abstractmethod
    def chunk(self, docs: list[Document]) -> list[Document]: ...

    def _add_metadata(self, chunks, chunking_type) -> list[Document]:
        # chunking_type, chunk_index 추가
```

### Semantic 전략 핵심 (`strategies/semantic_strategy.py`)

```python
from langchain_experimental.text_splitter import SemanticChunker

class SemanticChunkingStrategy(ChunkingStrategy):
    def __init__(self, embeddings, breakpoint_threshold_type="percentile",
                 breakpoint_threshold_amount=95.0): ...

    def chunk(self, docs):
        splitter = SemanticChunker(embeddings=self.embeddings, ...)
        return self._add_metadata(splitter.split_documents(docs), "semantic")
```

### Parent-Child 전략 핵심 (`strategies/parent_child_strategy.py`)

```python
# 부모(2000자) → 자식(400자) 이중 생성
# child.metadata["parent_id"] 로 부모 추적
```

### Router (`router.py`)

```python
class ChunkingRouter:
    _routing_table = {
        "text":  ["recursive", "semantic", "token"],
        "table": ["page", "markdown_header"],
        ...
    }
    def route(self, docs, rank=0) -> tuple[str, str]:
        pdf_type = docs[0].metadata.get("pdf_type", "text")
        ...
```

### Context (`chunking_context.py`)

```python
class ChunkingContext:
    @classmethod
    def set_embeddings(cls, embeddings): ...      # semantic 활성화
    @classmethod
    def available_chunkers(cls) -> list[str]: ...
    @classmethod
    def ChunkingDocs(cls, docs, chunking_type=None) -> list[Document]: ...
    @classmethod
    def register(cls, chunking_type, strategy): ... # OCP 준수
```

---

## 평가 루프 연동

```python
import mlflow
from src.loading.pdf.loader_context import PDFLoaderContext
from src.chunking.chunking_context import ChunkingContext

PDF_PATH = "data/sample/mixed.pdf"
CHUNKERS = ["recursive", "semantic", "page"]

docs = PDFLoaderContext.LoadingPDFDatas(PDF_PATH)

with mlflow.start_run(run_name="chunking_eval"):
    for chunking_type in CHUNKERS:
        chunks = ChunkingContext.ChunkingDocs(docs, chunking_type=chunking_type)

        mlflow.log_params({
            "pdf_type": docs[0].metadata.get("pdf_type"),
            "chunking_type": chunking_type,
            "chunk_count": len(chunks),
            "avg_chunk_size": sum(len(c.page_content) for c in chunks) / len(chunks),
        })
```

---

## 새 전략 추가

1. `strategies/{name}_strategy.py` — `ChunkingStrategy` 상속, `chunk()` 구현
2. `chunking_context.py` `_make_strategies()` 에 `try/except ImportError` 블록 추가
3. `router.py` `_routing_table` 해당 pdf_type 리스트에 추가
4. 이 파일 지원 목록 표에 행 추가

---

## 관련 파일

- `.claude/CLAUDE.md` — 프로젝트 전체 설계 원칙
- `.claude/src/loading/pdf/SKILL.md` — 이전 단계: PDF 로더 가이드
- `.claude/src/embedding/SKILL.md` — 다음 단계: 임베딩 모델 가이드
- `.claude/src/vectordb/SKILL.md` — VectorDB 가이드
- `src/chunking/strategies/base.py` — ChunkingStrategy 추상 클래스
- `src/chunking/router.py` — ChunkingRouter
- `src/chunking/chunking_context.py` — ChunkingContext (Router + Strategy 통합)
- `src/test/test_chunking.py` — 청킹 테스트 스크립트
