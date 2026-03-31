# Adaptive RAG — SKILL.md

질문 유형을 먼저 분류하여 **불필요한 VectorDB 검색을 건너뛰는** RAG 워크플로우.
Self-RAG의 모든 노드를 재사용하고 `route_question` + `direct_generate` 노드만 추가한다.

---

## 워크플로우

```
[사용자 질문]
     │
┌────▼──────────────────────┐
│  route_question            │  LLM structured output (RouteQuestion)
│  "문서 검색이 필요한가?"    │  → vectorstore / general
└────┬──────────┬────────────┘
     │          │
vectorstore   general
     │          │
     │    ┌─────▼──────────────────┐
     │    │  direct_generate        │  VectorDB 없이 LLM 단독 답변
     │    └─────┬──────────────────┘
     │          │ → END
     │
┌────▼──────────────────────┐
│  retrieve                  │  EmbeddingContext + VectorDBContext.Search(k)
└────┬──────────────────────┘
     │
┌────▼──────────────────────┐
│  grade_documents           │  LLM structured output (GradeDocuments)
└────┬──────────┬────────────┘
     │          │
 relevant   irrelevant
     │          │
     │    ┌─────▼──────────────────┐
     │    │  rewrite_query          │  LLM이 질문 재작성 → retrieve 재시도
     │    └────────────────────────┘  (최대 MAX_RETRY=2)
     │
┌────▼──────────────────────┐
│  generate                  │  Context + 질문 → LLM 답변
└────┬──────────────────────┘
     │
┌────▼──────────────────────┐
│  check_hallucination       │  LLM structured output (GradeHallucination)
└────┬──────────┬────────────┘
     │          │
 grounded   hallucinated → generate 재시도 (최대 MAX_RETRY=2)
     │
[최종 답변]
```

---

## 파일 구조

```
adaptive_rag/
├── __init__.py
├── graph.py     ← build_adaptive_rag_graph() — StateGraph 정의 및 컴파일
├── nodes.py     ← route_question, direct_generate 팩토리
│                  (나머지는 self_rag.nodes에서 re-export)
└── SKILL.md
```

---

## Self-RAG와의 차이

| 항목 | Self-RAG | Adaptive RAG |
|------|----------|--------------|
| 진입 노드 | retrieve | route_question |
| 일반 질문 처리 | VectorDB 검색 후 답변 | direct_generate (검색 생략) |
| 추가 노드 | — | route_question, direct_generate |
| LLM 호출 (일반 질문) | 4~6회 | 2회 (route + direct_generate) |
| LLM 호출 (문서 질문) | Self-RAG와 동일 | Self-RAG와 동일 |

---

## 노드 상세

### route_question (신규)
- `RouteQuestion` structured output으로 `vectorstore / general` 분류
- 문서 내용·수치·논문 관련 → `vectorstore`
- 일반 상식·개념 설명 → `general`

### direct_generate (신규)
- 문서 검색 없이 LLM 단독으로 답변
- `state["hallucination"] = "grounded"` 로 설정 (환각 체크 불필요)
- 직접 END로 이동

### retrieve ~ check_hallucination
Self-RAG와 완전히 동일. `self_rag.nodes`에서 re-export.

---

## 파라미터

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `store` | 필수 | 구축된 VectorDB 인스턴스 |
| `embedding_type` | `"openai_small"` | 쿼리 임베딩 모델 |
| `k` | `5` | 검색할 문서 수 |
| `llm_model` | `"gpt-4o-mini"` | 모든 LLM 노드에 적용 |

---

## 사용 예시

```python
from ragsystem.rag.rag_context import RAGContext

# 문서 관련 질문 → vectorstore 경로
result = RAGContext.ask(
    store=store,
    question="논문에서 한국어 발음 오류 유형은 어떻게 분류하나요?",
    rag_type="adaptive",
)
print(result["route"])        # "vectorstore"
print(result["answer"])

# 일반 질문 → direct_generate 경로
result = RAGContext.ask(
    store=store,
    question="RAG가 무엇인가요?",
    rag_type="adaptive",
)
print(result["route"])        # "general"
print(result["answer"])
```

---

## 특징

| 항목 | 내용 |
|------|------|
| 장점 | 일반 질문에 불필요한 VectorDB 검색 없이 빠른 응답 |
| 장점 | 문서 질문에는 Self-RAG 수준의 품질 보장 |
| API 호출 | 일반 질문: 2회 / 문서 질문: Self-RAG와 동일 |
| 적합한 경우 | 문서 관련/일반 질문이 혼합된 챗봇 인터페이스 |
