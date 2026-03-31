# Embedding Module

`List[Document]`(청크)를 입력받아 **Router + Strategy 패턴**으로 임베딩하여
`List[EmbeddedChunk]`를 반환하는 모듈.
파이프라인 3단계: Chunks → EmbeddedChunks.

---

## 파일 구조

```
embedding/
├── router.py              ← EmbeddingRouter: 언어 감지 → embedding_type 결정
├── embedding_context.py   ← EmbeddingContext: Router + Strategy 통합 진입점
└── strategies/
    ├── base.py                       ← EmbeddingStrategy (ABC) + EmbeddedChunk
    ├── openai_small_strategy.py      ← text-embedding-3-small (1536차원)
    ├── openai_large_strategy.py      ← text-embedding-3-large (3072차원)
    └── huggingface_ko_strategy.py    ← jhgan/ko-sroberta-multitask (768차원)
```

---

## 환경 설정

`config/.env` 파일에 API 키를 설정한다 (`config/.env.example` 참고):

```bash
cp config/.env.example config/.env
# config/.env 열어 OPENAI_API_KEY 입력
```

`EmbeddingContext`는 모듈 로드 시 `config/.env`를 **자동으로** 읽는다.

---

## 빠른 시작

```python
from ragsystem.embedding.embedding_context import EmbeddingContext

# 자동 라우팅 — 청크 언어를 감지하여 최적 모델 선택
embedded = EmbeddingContext.EmbeddingChunks(chunks)

# 수동 지정 — Router 우회
embedded = EmbeddingContext.EmbeddingChunks(chunks, embedding_type="openai_small")
embedded = EmbeddingContext.EmbeddingChunks(chunks, embedding_type="huggingface_ko")

# 사용 가능한 모델 확인
print(EmbeddingContext.available_embeddings())

# EmbeddedChunk 구조
ec = embedded[0]
ec.document        # 원본 Document (metadata["embedding_model"] 추가됨)
ec.embedding       # List[float] — 임베딩 벡터
ec.embedding_model # "text-embedding-3-small" 등
ec.embedding_dim   # 1536 / 3072 / 768
```

---

## 모델 비교

| embedding_type | 모델 | 차원 | 언어 | 비용/속도 |
|----------------|------|------|------|---------|
| `openai_small` | text-embedding-3-small | 1536 | 다국어 | $0.02/1M — 빠름 |
| `openai_large` | text-embedding-3-large | 3072 | 다국어 | $0.13/1M — 느림 |
| `huggingface_ko` | jhgan/ko-sroberta-multitask | 768 | **한국어 특화** | 무료 — 로컬 CPU |

---

## 라우팅 테이블

| language | 1순위 | 2순위 |
|----------|-------|-------|
| `ko` (한글 ≥ 20%) | `huggingface_ko` | `openai_small` |
| `en` (한글 < 5%) | `openai_small` | `openai_large` |
| `mixed` (한글 5~20%) | `openai_small` | `huggingface_ko` |

---

## 테스트

```bash
source venv/bin/activate

# 사용 가능한 임베더 확인
python -m tests.test_embedding --list-embedders

# 기본 테스트 (JSON 입력 — test_chunking.py --save 출력)
python -m tests.test_embedding --input tests/output/파일_recursive_chunking.json

# 특정 모델 지정
python -m tests.test_embedding --input 파일.json --embedder openai_small
python -m tests.test_embedding --input 파일.json --embedder huggingface_ko

# 전체 모델 일괄 비교
python -m tests.test_embedding --input 파일.json --all

# 벡터 미리보기
python -m tests.test_embedding --input 파일.json --inspect --chunk-index 0

# 결과 JSON 저장 (→ VectorDB 단계 입력으로 사용)
python -m tests.test_embedding --input 파일.json --embedder openai_small --save
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

print(f"{len(chunks)}개 청크 → {len(embedded)}개 EmbeddedChunk")
print(f"모델: {embedded[0].embedding_model}  차원: {embedded[0].embedding_dim}")
```

---

## HuggingFace 모델 교체

```python
from ragsystem.embedding.strategies.huggingface_ko_strategy import HuggingFaceKoEmbeddingStrategy
from ragsystem.embedding.embedding_context import EmbeddingContext

# 다른 HuggingFace 모델로 교체
EmbeddingContext.register(
    "huggingface_ko",
    HuggingFaceKoEmbeddingStrategy(model_name="intfloat/multilingual-e5-large")
)
```
