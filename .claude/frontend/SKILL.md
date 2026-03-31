# Frontend — SKILL.md

Streamlit 기반 웹 UI. FastAPI(`api/`)에 HTTP 요청을 보내고 결과를 화면에 표시한다.

---

## 실행

```bash
# Streamlit 개발 서버
streamlit run frontend/app.py --server.port 8501

# API 서버와 함께 실행 (별도 터미널)
uvicorn api.main:app --reload --port 8000
streamlit run frontend/app.py --server.port 8501
```

---

## 파일 구조

```
frontend/
├── __init__.py
├── app.py               ← Streamlit 진입점 (st.set_page_config, 탭 구성)
├── pages/               ← 각 단계별 페이지 컴포넌트
│   ├── __init__.py
│   ├── upload.py        ← Step 1: PDF 드래그앤드롭 업로드
│   ├── pipeline.py      ← Step 2~5: 단계별 옵션 선택 + 실행 + 결과 표시
│   └── rag.py           ← Step 6: RAG 워크플로우 선택 + 질의 + 답변
└── components/          ← 재사용 UI 컴포넌트
    ├── __init__.py
    ├── step_card.py     ← 단계 카드 (상태 뱃지 + 요약 정보)
    ├── result_table.py  ← 검색 결과 테이블 (rank/score/page/내용)
    └── api_client.py    ← requests 래퍼 (API 호출 함수 모음)
```

---

## 화면 구성 (탭 방식)

```
┌─────────────────────────────────────────────────────────┐
│  📄 evalRAG — PDF RAG Pipeline                           │
├──────┬──────────┬────────────┬─────────────┬────────────┤
│ 업로드│ 파이프라인│  VectorDB  │   RAG 질의  │   결과 비교 │
└──────┴──────────┴────────────┴─────────────┴────────────┘
```

---

## Tab 1: PDF 업로드 (`pages/upload.py`)

```python
# 구현 포인트
uploaded = st.file_uploader("PDF 파일을 업로드하세요", type=["pdf"])
if uploaded:
    # POST /upload 호출
    res = api_client.upload_pdf(uploaded)
    st.session_state["session_id"] = res["session_id"]
    st.success(f"업로드 완료 — PDF 유형: {res['pdf_type']}")
```

**표시 정보:**
- 파일명, 파일 크기
- 감지된 PDF 유형 (`text` / `table` / `graph` / `scan` / `mixed`)
- 유형별 권장 로더 안내

---

## Tab 2: 파이프라인 실행 (`pages/pipeline.py`)

4개 단계를 순서대로 실행. 각 단계는 완료 후 다음 단계 버튼이 활성화된다.

### Step 2 — Loading

```python
loader_type = st.selectbox("로더 선택", ["자동 감지", "pymupdf", "pdfplumber", ...])
if st.button("Loading 실행"):
    with st.spinner("Loading 중..."):
        res = api_client.run_step(session_id, "loading", {"loader_type": loader_type})
    st.metric("문서 수", res["summary"]["doc_count"])
    st.metric("소요 시간", f"{res['summary']['elapsed_ms']}ms")
```

### Step 3 — Chunking

```python
chunking_type = st.selectbox("청킹 전략", ["자동 선택", "recursive", "token", ...])
chunk_size    = st.slider("청크 크기", 200, 2000, 500)
overlap       = st.slider("오버랩", 0, 200, 50)
```

**표시 정보:** 청크 수, 평균 크기(자), 최소/최대 크기

### Step 4 — Embedding

```python
embedding_type = st.selectbox("임베딩 모델", ["자동 감지", "openai_small", "openai_large", "huggingface_ko"])
```

**표시 정보:** 벡터 수, 차원, 모델명, 소요 시간, 감지 언어

### Step 5 — VectorDB

```python
vectordb_type = st.selectbox("VectorDB", ["자동 선택", "chromadb", "faiss"])
```

**표시 정보:** 인덱스 크기, DB 종류, 구축 시간

---

## Tab 3: RAG 질의 (`pages/rag.py`)

```python
rag_type  = st.radio("워크플로우", ["simple", "self", "adaptive"], horizontal=True)
llm_model = st.selectbox("LLM 모델", ["gpt-4o-mini", "gpt-4o"])
k         = st.slider("검색 문서 수 (k)", 1, 20, 5)
question  = st.text_area("질문을 입력하세요")

if st.button("질의"):
    with st.spinner("RAG 실행 중..."):
        res = api_client.ask_rag(session_id, question, rag_type, llm_model, k)

    # 답변 표시
    st.subheader("답변")
    st.write(res["answer"])

    # 메타 정보
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("소요 시간", f"{res['elapsed_ms']}ms")
    col2.metric("재시도", res["retry_count"])
    col3.metric("관련성", res.get("relevance", "-"))
    col4.metric("환각", res.get("hallucination", "-"))

    # 참조 문서
    st.subheader("참조 문서")
    for ctx in res["context"]:
        with st.expander(f"[Rank {ctx['rank']}] page:{ctx['page']}  similarity:{ctx['score']:.4f}"):
            st.text(ctx["content"])
```

---

## Tab 4: 결과 비교 (선택 구현)

동일 질문으로 `simple` / `self` / `adaptive` 세 가지를 동시 실행하고 나란히 비교한다.

```python
cols = st.columns(3)
for col, rag_type in zip(cols, ["simple", "self", "adaptive"]):
    with col:
        st.subheader(f"{rag_type.upper()} RAG")
        res = api_client.ask_rag(session_id, question, rag_type, ...)
        st.write(res["answer"])
        st.caption(f"소요: {res['elapsed_ms']}ms | 환각: {res.get('hallucination','-')}")
```

---

## api_client.py 인터페이스

```python
API_BASE = "http://localhost:8000"

def upload_pdf(file) -> dict:
    """POST /upload → { session_id, filename, pdf_type }"""

def run_step(session_id: str, step: str, options: dict) -> dict:
    """POST /pipeline/run → { status, summary }"""

def get_status(session_id: str) -> dict:
    """GET /pipeline/status/{session_id} → { completed_steps, summary }"""

def ask_rag(session_id: str, question: str, rag_type: str,
            llm_model: str = "gpt-4o-mini", k: int = 5) -> dict:
    """POST /rag/ask → { answer, context, relevance, hallucination, ... }"""
```

---

## 세션 상태 관리 (`st.session_state`)

```python
st.session_state["session_id"]      # API 세션 ID
st.session_state["pdf_type"]        # 감지된 PDF 유형
st.session_state["completed_steps"] # ["loading", "chunking", ...]
st.session_state["last_answer"]     # 마지막 RAG 답변
```

---

## 의존성 추가 (requirements.txt)

```
streamlit>=1.35
requests>=2.32         # API 호출
```
