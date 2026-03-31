# Self-RAG — SKILL.md

검색 문서의 **관련성 평가**와 생성 답변의 **환각 검증**을 포함한 RAG 워크플로우.
Simple RAG 대비 LLM API 호출이 추가되지만 답변 신뢰도가 높다.

---

## 워크플로우

```
[사용자 질문]
     │
┌────▼──────────────────────┐
│  retrieve                  │  EmbeddingContext + VectorDBContext.Search(k)
└────┬──────────────────────┘
     │
┌────▼──────────────────────┐
│  grade_documents           │  LLM structured output (GradeDocuments)
│  각 문서 관련성 평가        │  → relevant 문서만 context에 유지
└────┬──────────┬────────────┘
     │          │
 relevant   irrelevant (retry_count < MAX_RETRY=2)
     │          │
     │    ┌─────▼──────────────────┐
     │    │  rewrite_query          │  LLM이 검색에 최적화된 질문으로 재작성
     │    └─────┬──────────────────┘
     │          │ (→ retrieve 재시도)
     │   ───────┘
     │
┌────▼──────────────────────┐
│  generate                  │  Context + 질문 → LLM 답변 생성
└────┬──────────────────────┘
     │
┌────▼──────────────────────┐
│  check_hallucination       │  LLM structured output (GradeHallucination)
│  답변이 문서에 근거하는가?  │  → grounded / hallucinated
└────┬──────────┬────────────┘
     │          │
 grounded   hallucinated (retry_count < MAX_RETRY=2)
     │          │ (→ generate 재시도)
     │   ───────┘
     │
[최종 답변]
```

---

## 파일 구조

```
self_rag/
├── __init__.py
├── graph.py     ← build_self_rag_graph() — StateGraph 정의 및 컴파일
├── nodes.py     ← 노드 팩토리 5개 + 엣지 조건 함수 2개
└── SKILL.md
```

---

## 노드 상세

### retrieve
Simple RAG와 동일. `VectorDBContext.Search()` → `state["context"]`.

### grade_documents
- 각 문서에 대해 `GradeDocuments` structured output으로 `relevant/irrelevant` 분류
- relevant 문서만 `state["context"]`에 유지
- 모두 irrelevant이면 `state["relevance"] = "irrelevant"` → rewrite_query로 분기

### rewrite_query
- LLM이 벡터 검색에 최적화된 질문으로 재작성
- `state["question"]` 교체, `state["retry_count"]` +1
- `MAX_RETRY(=2)` 초과 시 강제로 generate 진행

### generate
- relevant 문서들로 Context 구성 후 LLM 답변 생성
- `state["answer"]` 저장

### check_hallucination
- 생성된 답변이 Context 문서에 근거하는지 `GradeHallucination` structured output으로 평가
- `grounded` → END, `hallucinated` → generate 재시도

---

## 엣지 조건

| 함수 | 출발 노드 | 조건 | 다음 노드 |
|------|-----------|------|-----------|
| `decide_after_grade` | grade_documents | relevant | generate |
| | | irrelevant + retry < MAX | rewrite_query |
| | | irrelevant + retry ≥ MAX | generate (강제) |
| `decide_after_hallucination` | check_hallucination | grounded | END |
| | | hallucinated + retry < MAX | generate |
| | | hallucinated + retry ≥ MAX | END (현재 답변 반환) |

---

## 파라미터

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `store` | 필수 | 구축된 VectorDB 인스턴스 |
| `embedding_type` | `"openai_small"` | 쿼리 임베딩 모델 |
| `k` | `5` | 검색할 문서 수 |
| `llm_model` | `"gpt-4o-mini"` | 모든 LLM 노드에 적용 |
| `MAX_RETRY` | `2` | nodes.py 상수로 조정 |

---

## 사용 예시

```python
from src.rag.rag_context import RAGContext

result = RAGContext.ask(
    store=store,
    question="한국어 음성의 특징은?",
    rag_type="self",
    k=5,
    llm_model="gpt-4o-mini",
)
print(result["answer"])
print("관련성:", result["relevance"])
print("환각여부:", result["hallucination"])
print("재시도:", result["retry_count"])
```

---

## 특징

| 항목 | 내용 |
|------|------|
| 장점 | 관련성 필터 + 환각 검증으로 답변 품질 보장 |
| API 호출 수 | 최소 4회 (retrieve용 embed + grade + generate + hallucination) |
| RAGAS Faithfulness | ≥ 0.80 목표 달성에 적합 |
| 한계 | Simple RAG 대비 레이턴시 증가 |
