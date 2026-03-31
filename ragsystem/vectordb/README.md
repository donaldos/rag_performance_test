# VectorDB Module

`List[EmbeddedChunk]`를 입력받아 **Router + Strategy 패턴**으로 벡터 인덱스를 구축하고
유사 문서 검색을 수행하는 모듈.

---

## 파일 구조

```
vectordb/
├── router.py              ← VectorDBRouter: 청크 수 → vectordb_type 결정
├── vectordb_context.py    ← VectorDBContext: Router + Strategy 통합 진입점
└── strategies/
    ├── base.py            ← VectorDBStrategy (ABC) + SearchResult
    ├── faiss_strategy.py  ← FAISS IndexFlatL2 (L2 거리)
    └── chroma_strategy.py ← ChromaDB cosine 유사도
```

---

## 환경 설정

```bash
pip install faiss-cpu chromadb
```

---

## 빠른 시작

```python
from ragsystem.vectordb.vectordb_context import VectorDBContext

# 자동 라우팅 — 청크 수로 최적 DB 선택
store = VectorDBContext.BuildVectorDB(embedded_chunks)

# 수동 지정
store = VectorDBContext.BuildVectorDB(embedded_chunks, vectordb_type="faiss")
store = VectorDBContext.BuildVectorDB(embedded_chunks, vectordb_type="chromadb")

# 영구 저장 (ChromaDB)
store = VectorDBContext.BuildVectorDB(
    embedded_chunks, vectordb_type="chromadb", persist_dir="data/chroma"
)

# 검색
results = VectorDBContext.Search(store, query_embedding, k=5)
for r in results:
    print(r.rank, r.score, r.document.page_content[:100])
```

---

## 라우팅 테이블

| size_type | 조건 | 1순위 | 2순위 |
|-----------|------|-------|-------|
| `small` | 청크 < 500 | `chromadb` | `faiss` |
| `large` | 청크 ≥ 500 | `faiss` | `chromadb` |

---

## 전략 비교

| vectordb_type | 거리 지표 | score 해석 | 저장 방식 | 특징 |
|---------------|----------|-----------|----------|------|
| `faiss` | L2 거리 | 낮을수록 유사 | 디렉터리 (index.faiss + documents.json) | 빠름, 순수 벡터 |
| `chromadb` | cosine → 유사도 변환 | 높을수록 유사 (0~1) | PersistentClient 디렉터리 | 메타데이터 필터링 |

---

## SearchResult 구조

```python
@dataclass
class SearchResult:
    document: Document   # 원본 청크 (metadata 포함)
    score: float         # FAISS: L2거리 / ChromaDB: 코사인 유사도(0~1)
    rank: int            # 검색 순위 (0부터)
    vectordb_type: str   # "faiss" | "chromadb"
```

---

## 저장 / 로드

```python
# FAISS 저장/로드
store.save("data/faiss_index")
store2 = FAISSVectorDBStrategy.load_from("data/faiss_index")

# ChromaDB는 persist_dir 지정 시 자동 저장
store = VectorDBContext.BuildVectorDB(
    embedded_chunks, vectordb_type="chromadb", persist_dir="data/chroma"
)
store3 = ChromaDBVectorDBStrategy.load_from("data/chroma")
```

---

## 파이프라인 연결 예시

```python
from ragsystem.loading.pdf.loader_context import PDFLoaderContext
from ragsystem.chunking.chunking_context import ChunkingContext
from ragsystem.embedding.embedding_context import EmbeddingContext
from ragsystem.vectordb.vectordb_context import VectorDBContext

docs     = PDFLoaderContext.LoadingPDFDatas("file.pdf")
chunks   = ChunkingContext.ChunkingDocs(docs)
embedded = EmbeddingContext.EmbeddingChunks(chunks)
store    = VectorDBContext.BuildVectorDB(embedded)

# 쿼리 임베딩 후 검색
query_vec = EmbeddingContext.EmbeddingChunks([Document(page_content="질문")],
                                              embedding_type="openai_small")[0].embedding
results = VectorDBContext.Search(store, query_vec, k=5)
```

---

## 새 VectorDB 추가

1. `strategies/{name}_strategy.py` — `VectorDBStrategy` 상속, `build()` / `search()` / `save()` / `load_from()` 구현
2. `vectordb_context.py` `_make_strategies()` 에 `try/except` 블록 추가
3. `router.py` `_routing_table` 적절한 size_type 리스트에 추가
