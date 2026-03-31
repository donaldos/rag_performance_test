# API — SKILL.md

FastAPI 기반 REST API 서버. `ragsystem` 파이프라인을 HTTP 엔드포인트로 노출한다.

---

## 실행

```bash
# 개발 서버 (auto-reload)
uvicorn api.main:app --reload --port 8000

# 프로덕션
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 파일 구조

```
api/
├── __init__.py
├── main.py              ← FastAPI 앱 생성, 미들웨어, 라우터 등록
├── routers/             ← 엔드포인트 모음
│   ├── __init__.py
│   ├── upload.py        ← POST /upload          — PDF 업로드
│   ├── pipeline.py      ← POST /pipeline/run    — 단계 실행
│   │                      GET  /pipeline/status — 진행 상태 (SSE)
│   └── rag.py           ← POST /rag/ask         — RAG 질의
├── models/              ← Pydantic 요청/응답 스키마
│   ├── __init__.py
│   ├── pipeline.py      ← PipelineRequest, StepResult
│   └── rag.py           ← RagRequest, RagResponse
└── services/            ← 비즈니스 로직 (ragsystem 호출 래퍼)
    ├── __init__.py
    ├── session.py       ← 세션별 파이프라인 상태 관리 (in-memory dict)
    └── pipeline.py      ← 각 단계 실행 함수
```

---

## 엔드포인트 설계

### POST /upload
PDF 파일을 업로드하고 `session_id`를 반환한다.

```
Request : multipart/form-data  { file: PDF }
Response: { session_id: str, filename: str, pdf_type: str }
```

- 업로드된 파일은 `data/uploads/{session_id}/` 에 저장
- `PDFTypeRouter.detect_pdf_type()`으로 PDF 유형 자동 감지 후 반환

---

### POST /pipeline/run
지정한 단계를 실행하고 결과를 반환한다.

```
Request:
{
  "session_id": "abc123",
  "step": "loading" | "chunking" | "embedding" | "vectordb",
  "options": {
    "loader_type":    "pymupdf" | null,     // loading 옵션
    "chunking_type":  "recursive" | null,   // chunking 옵션
    "embedding_type": "openai_small" | null,// embedding 옵션
    "vectordb_type":  "chromadb" | null     // vectordb 옵션
  }
}

Response:
{
  "session_id": "abc123",
  "step": "loading",
  "status": "success" | "error",
  "summary": {
    "doc_count": 11,
    "loader_type": "pymupdf",
    "pdf_type": "text",
    "elapsed_ms": 342
  }
}
```

- 각 단계 결과는 세션 메모리에 보존 → 다음 단계 입력으로 자동 연결
- `options` 값이 `null`이면 Router가 자동 선택

---

### GET /pipeline/status/{session_id}
현재 세션의 파이프라인 완료 단계와 요약을 반환한다.

```
Response:
{
  "session_id": "abc123",
  "completed_steps": ["loading", "chunking", "embedding", "vectordb"],
  "summary": {
    "loading":   { "doc_count": 11,  "loader_type": "pymupdf" },
    "chunking":  { "chunk_count": 44, "chunking_type": "recursive" },
    "embedding": { "vector_count": 44, "dim": 1536, "model": "text-embedding-3-small" },
    "vectordb":  { "db_type": "chromadb", "index_size": 44 }
  }
}
```

---

### POST /rag/ask
구축된 VectorDB에 질문하고 LLM 답변을 반환한다.

```
Request:
{
  "session_id": "abc123",
  "question": "질문 텍스트",
  "rag_type": "simple" | "self" | "adaptive",
  "llm_model": "gpt-4o-mini",
  "k": 5
}

Response:
{
  "answer": "LLM 생성 답변",
  "rag_type": "self",
  "retry_count": 0,
  "relevance": "relevant",
  "hallucination": "grounded",
  "route": "",
  "context": [
    { "rank": 1, "score": 0.71, "page": 3, "content": "..." },
    ...
  ],
  "elapsed_ms": 4200
}
```

---

## 세션 관리 (`api/services/session.py`)

```python
# in-memory 세션 저장소 구조
sessions: dict[str, SessionState] = {}

@dataclass
class SessionState:
    session_id: str
    pdf_path: str
    pdf_type: str
    docs: List[Document]         # loading 결과
    chunks: List[Document]       # chunking 결과
    embedded: List[EmbeddedChunk] # embedding 결과
    store: VectorDBStrategy      # vectordb 결과
    completed_steps: List[str]
    created_at: datetime
```

- 세션 TTL: 1시간 (비활성 세션 자동 만료)
- 멀티 사용자 지원: `session_id`로 완전 분리

---

## 구현 순서 (권장)

1. `api/models/pipeline.py` — Pydantic 스키마 정의
2. `api/services/session.py` — 세션 상태 관리
3. `api/services/pipeline.py` — ragsystem 단계별 호출 래퍼
4. `api/routers/upload.py` — PDF 업로드 엔드포인트
5. `api/routers/pipeline.py` — 단계 실행 + 상태 조회
6. `api/routers/rag.py` — RAG 질의
7. `api/main.py` — 라우터 등록

---

## 의존성 추가 (requirements.txt)

```
fastapi>=0.110
uvicorn[standard]>=0.29
python-multipart>=0.0.9    # 파일 업로드
```
