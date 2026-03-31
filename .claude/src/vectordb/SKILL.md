---
name: vectordb
description: |
  EmbeddedChunk 리스트를 Router + 전략 패턴으로 VectorDB에 인덱싱하는 모듈.
  BuildVectorDB(embedded_chunks, vectordb_type=None) 인터페이스로 호출하며,
  vectordb_type을 생략하면 VectorDBRouter가 청크 수(< 500 → chromadb, ≥ 500 → faiss)로 자동 결정한다.
  VectorDB 선택, 추가, 검색, 저장 관련 작업에 반드시 사용한다.
---

# VectorDB Skill

## 역할

Embedding 단계의 `List[EmbeddedChunk]`를 받아 벡터 인덱스를 구축하고
`Search(store, query_embedding, k)` 로 유사 문서를 검색한다.

---

## 아키텍처

```
BuildVectorDB(embedded_chunks, vectordb_type=None)
        │
        ▼
  vectordb_type 지정됨?
    ├── Yes → Strategy 직접 호출
    └── No  → VectorDBRouter.route(embedded_chunks)
                    │
              청크 수 측정
                    │
              < 500  → "small" → chromadb
              ≥ 500  → "large" → faiss
                    │
                    ▼
             Strategy.build(embedded_chunks) → VectorDBStrategy 인스턴스
```

---

## 인터페이스

```python
from src.vectordb.vectordb_context import VectorDBContext

# 자동 라우팅
store = VectorDBContext.BuildVectorDB(embedded_chunks)

# 수동 Override
store = VectorDBContext.BuildVectorDB(embedded_chunks, vectordb_type="faiss")
store = VectorDBContext.BuildVectorDB(embedded_chunks, vectordb_type="chromadb",
                                      persist_dir="data/chroma")

# 검색
results = VectorDBContext.Search(store, query_embedding, k=5)

# SearchResult 속성
r.document      # 원본 Document (metadata 포함)
r.score         # FAISS: L2거리(낮을수록 유사) / ChromaDB: 코사인유사도(높을수록 유사)
r.rank          # 검색 순위 (0부터)
r.vectordb_type # "faiss" | "chromadb"
```

---

## 지원 vectordb_type

| vectordb_type | 거리 지표 | 저장 | 필요 조건 |
|---------------|----------|------|---------|
| `faiss` | L2 거리 | index.faiss + documents.json | `faiss-cpu` |
| `chromadb` | cosine 유사도 | PersistentClient 디렉터리 | `chromadb` |

---

## 라우팅 테이블

| size_type | 조건 | 1순위 | 2순위 |
|-----------|------|-------|-------|
| `small` | 청크 < 500 | `chromadb` | `faiss` |
| `large` | 청크 ≥ 500 | `faiss` | `chromadb` |

---

## 새 VectorDB 추가

1. `strategies/{name}_strategy.py` — `VectorDBStrategy` 상속, `build()` / `search()` / `save()` / `load_from()` 구현
2. `vectordb_context.py` `_make_strategies()` 에 `try/except` 블록 추가
3. `router.py` `_routing_table` 해당 size_type 리스트에 추가
4. 이 파일 지원 목록 표에 행 추가

---

## 관련 파일

- `.claude/CLAUDE.md` — 프로젝트 전체 설계 원칙
- `.claude/src/embedding/SKILL.md` — 이전 단계: 임베딩 모델 가이드
- `src/vectordb/strategies/base.py` — VectorDBStrategy + SearchResult
- `src/vectordb/router.py` — VectorDBRouter (청크 수 감지)
- `src/vectordb/vectordb_context.py` — VectorDBContext (Router + Strategy 통합)
- `src/test/test_vectordb.py` — VectorDB 테스트 스크립트
