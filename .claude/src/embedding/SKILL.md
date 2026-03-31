---
name: embedding
description: |
  청크 리스트를 Router + 전략 패턴으로 임베딩하는 모듈.
  EmbeddingChunks(chunks, embedding_type=None) 인터페이스로 호출하며,
  embedding_type을 생략하면 EmbeddingRouter가 청크 언어(한국어 비율)를 분석하여 자동 결정한다.
  OpenAI API 키는 config/.env에서 자동 로드한다.
  임베딩 모델 선택, 추가, 평가 관련 작업에 반드시 사용한다.
---

# Embedding Skill

## 역할

Chunking 단계의 `List[Document]`를 받아 벡터 임베딩 후
`List[EmbeddedChunk]`를 반환한다. 결과는 VectorDB 단계로 전달된다.

---

## 아키텍처

```
EmbeddingChunks(chunks, embedding_type=None)
        │
        ▼
  embedding_type 지정됨?
    ├── Yes → Strategy 직접 호출
    └── No  → EmbeddingRouter.route(chunks)
                    │
              한글 비율 측정 (샘플 5개 × 500자)
                    │
              ≥20%  → "ko"    → huggingface_ko
              5~20% → "mixed" → openai_small
              <5%   → "en"    → openai_small
                    │
                    ▼
             Strategy.embed(chunks) → List[EmbeddedChunk]
```

---

## 환경 설정

```bash
# config/.env에 API 키 설정
cp config/.env.example config/.env
# OPENAI_API_KEY=sk-... 입력
```

`EmbeddingContext` 임포트 시 `config/.env`를 자동 로드한다.

---

## 지원 embedding_type

| embedding_type | 모델 | 차원 | 언어 | 필요 조건 |
|----------------|------|------|------|---------|
| `openai_small` | text-embedding-3-small | 1536 | 다국어 | `langchain-openai` + OPENAI_API_KEY |
| `openai_large` | text-embedding-3-large | 3072 | 다국어 | `langchain-openai` + OPENAI_API_KEY |
| `huggingface_ko` | jhgan/ko-sroberta-multitask | 768 | 한국어 특화 | `langchain-huggingface` |

---

## 인터페이스

```python
from src.embedding.embedding_context import EmbeddingContext

# 자동 라우팅
embedded = EmbeddingContext.EmbeddingChunks(chunks)

# 수동 Override
embedded = EmbeddingContext.EmbeddingChunks(chunks, embedding_type="openai_small")
embedded = EmbeddingContext.EmbeddingChunks(chunks, embedding_type="huggingface_ko")

# EmbeddedChunk 속성
ec.document        # 원본 Document
ec.embedding       # List[float]
ec.embedding_model # 모델명 문자열
ec.embedding_dim   # 벡터 차원 수
```

---

## 라우팅 테이블

| language | 1순위 | 2순위 |
|----------|-------|-------|
| `ko` | `huggingface_ko` | `openai_small` |
| `en` | `openai_small` | `openai_large` |
| `mixed` | `openai_small` | `huggingface_ko` |

---

## 새 모델 추가

1. `strategies/{name}_strategy.py` — `EmbeddingStrategy` 상속, `embed()` 구현
2. `embedding_context.py` `_make_strategies()` 에 `try/except` 블록 추가
3. `router.py` `_routing_table` 해당 language 리스트에 추가
4. 이 파일 지원 목록 표에 행 추가

---

## 관련 파일

- `.claude/CLAUDE.md` — 프로젝트 전체 설계 원칙
- `.claude/src/chunking/SKILL.md` — 이전 단계: 청킹 전략 가이드
- `.claude/src/vectordb/SKILL.md` — 다음 단계: VectorDB 가이드
- `config/.env` — API 키 (커밋 금지)
- `config/.env.example` — 키 템플릿
- `src/embedding/strategies/base.py` — EmbeddingStrategy + EmbeddedChunk
- `src/embedding/router.py` — EmbeddingRouter (언어 감지)
- `src/embedding/embedding_context.py` — EmbeddingContext (Router + Strategy 통합)
- `src/test/test_embedding.py` — 임베딩 테스트 스크립트
