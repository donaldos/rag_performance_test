# Simple RAG — SKILL.md

가장 단순한 RAG 워크플로우. **retrieve → generate** 두 노드로 구성된다.

---

## 워크플로우

```
[사용자 질문]
     │
┌────▼──────────────────────┐
│  retrieve                  │
│  질문 임베딩 → VectorDB     │  EmbeddingContext + VectorDBContext.Search
│  Top-K 청크 반환            │
└────┬──────────────────────┘
     │
┌────▼──────────────────────┐
│  generate                  │
│  Context + 질문 → LLM      │  ChatOpenAI (gpt-4o-mini)
│  → 최종 답변                │
└────┬──────────────────────┘
     │
[최종 답변]
```

---

## 파일 구조

```
simple_rag/
├── __init__.py
├── graph.py     ← build_simple_rag_graph() — StateGraph 정의 및 컴파일
├── nodes.py     ← make_retrieve_node(), make_generate_node() 팩토리
└── SKILL.md
```

---

## 노드 상세

### retrieve
- 질문 텍스트를 `EmbeddingContext.EmbeddingChunks()`로 임베딩
- `VectorDBContext.Search(store, query_vec, k=k)`로 Top-K 문서 검색
- `state["context"]`에 `List[Document]` 저장

### generate
- `state["context"]`의 문서를 `\n\n---\n\n`으로 연결하여 Context 구성
- `ChatPromptTemplate`(system: 문서 기반 답변 지시, human: 질문)으로 LLM 호출
- `state["answer"]`에 답변 저장

---

## 파라미터

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `store` | 필수 | VectorDBContext.BuildVectorDB() 반환값 |
| `embedding_type` | `"openai_small"` | 쿼리 임베딩 모델 |
| `k` | `5` | 검색할 문서 수 |
| `llm_model` | `"gpt-4o-mini"` | 답변 생성 LLM |

---

## 사용 예시

```python
from ragsystem.rag.rag_context import RAGContext

result = RAGContext.ask(
    store=store,
    question="한국어 음성의 특징은?",
    rag_type="simple",
    k=5,
    llm_model="gpt-4o-mini",
)
print(result["answer"])
```

---

## 특징 및 한계

| 항목 | 내용 |
|------|------|
| 장점 | 구조 단순, 빠른 응답, API 호출 최소화 |
| 한계 | 검색 문서 관련성 검증 없음, 환각 체크 없음 |
| 적합한 경우 | 검색 품질이 이미 높거나 빠른 프로토타이핑 |
