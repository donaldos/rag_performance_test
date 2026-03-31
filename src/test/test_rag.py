"""
RAG 워크플로우 테스트 스크립트.

사용법:
    python -m src.test.test_rag \\
        --input  src/test/output/<..._embedding.json> \\
        --query  "질문 텍스트" \\
        [--rag    simple | self | adaptive | all]  ← 기본: self
        [--llm    gpt-4o-mini | gpt-4o]            ← 기본: gpt-4o-mini
        [--k      5]                               ← 검색 문서 수
        [--db     faiss | chromadb]                ← 기본: 자동 라우팅
        [--embed  openai_small | openai_large]     ← 기본: openai_small

예시:
    # Self-RAG (기본)
    python -m src.test.test_rag \\
        --input src/test/output/04_recursive_chunking_openai_small_embedding.json \\
        --query "한국어 음성 발음 오류의 유형은 무엇인가요?"

    # 세 가지 워크플로우 일괄 비교
    python -m src.test.test_rag \\
        --input src/test/output/04_recursive_chunking_openai_small_embedding.json \\
        --query "한국어 음성 발음 오류의 유형은 무엇인가요?" \\
        --rag all

    # Adaptive RAG + gpt-4o
    python -m src.test.test_rag \\
        --input src/test/output/04_recursive_chunking_openai_small_embedding.json \\
        --query "RAG란 무엇인가요?" \\
        --rag adaptive --llm gpt-4o
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from dotenv import load_dotenv

load_dotenv("config/.env")

from src.test.io_utils import load_embedded_chunks
from src.utils import get_logger
from src.vectordb.vectordb_context import VectorDBContext
from src.rag.rag_context import RAGContext

logger = get_logger(__name__)

_DIVIDER = "═" * 64
_THIN    = "─" * 64


def _print_header(title: str) -> None:
    print(f"\n{_DIVIDER}")
    print(f"  {title}")
    print(_DIVIDER)


def _print_result(result: dict, elapsed_ms: float) -> None:
    """RAGContext.ask() 결과를 출력한다."""
    rag_type = result.get("rag_type", "?")
    answer   = result.get("answer", "")
    context  = result.get("context", [])
    retry    = result.get("retry_count", 0)
    relevance     = result.get("relevance", "")
    hallucination = result.get("hallucination", "")
    route         = result.get("route", "")

    print(f"\n  [PASS] rag_type     : {rag_type}")
    print(f"  [PASS] 소요 시간    : {elapsed_ms:.1f}ms")
    print(f"  [PASS] 사용 문서    : {len(context)}개")
    print(f"  [PASS] 재시도 횟수  : {retry}")
    if relevance:
        print(f"  [PASS] 관련성 평가  : {relevance}")
    if hallucination:
        marker = "[PASS]" if hallucination == "grounded" else "[WARN]"
        print(f"  {marker} 환각 검증    : {hallucination}")
    if route:
        print(f"  [PASS] 라우팅 결과  : {route}")

    print(f"\n{_THIN}")
    print("  [ 최종 답변 ]")
    print(_THIN)
    # 답변을 80자 단위로 출력
    for i in range(0, len(answer), 80):
        print(f"  {answer[i:i+80]}")

    if context:
        print(f"\n{_THIN}")
        print("  [ 참조 문서 (Rank 1) ]")
        print(_THIN)
        first = context[0]
        meta = first.metadata
        print(f"  page    : {meta.get('page', '?')}")
        print(f"  chunker : {meta.get('chunking_type', '?')}")
        print(f"  content : {first.page_content[:120]}...")


def run_single(
    store,
    question: str,
    rag_type: str,
    embedding_type: str,
    k: int,
    llm_model: str,
) -> dict:
    """단일 RAG 워크플로우를 실행하고 결과를 반환한다."""
    _print_header(f"RAG 테스트 — rag_type='{rag_type}'")
    print(f"  질문 : {question}")
    print(f"  LLM  : {llm_model}  |  k={k}  |  embed={embedding_type}")

    start = time.time()
    result = RAGContext.ask(
        store=store,
        question=question,
        rag_type=rag_type,
        embedding_type=embedding_type,
        k=k,
        llm_model=llm_model,
    )
    elapsed_ms = (time.time() - start) * 1000

    _print_result(result, elapsed_ms)
    return result


def run_all(
    store,
    question: str,
    embedding_type: str,
    k: int,
    llm_model: str,
) -> None:
    """simple / self / adaptive 세 가지 워크플로우를 순서대로 실행하고 비교한다."""
    _print_header("RAG 일괄 비교 (simple | self | adaptive)")
    print(f"  질문 : {question}")
    print(f"  LLM  : {llm_model}  |  k={k}  |  embed={embedding_type}")

    summary = []
    for rag_type in ("simple", "self", "adaptive"):
        print(f"\n{'─'*64}")
        print(f"  ▶ {rag_type.upper()} RAG 실행 중...")
        start = time.time()
        try:
            result = RAGContext.ask(
                store=store,
                question=question,
                rag_type=rag_type,
                embedding_type=embedding_type,
                k=k,
                llm_model=llm_model,
            )
            elapsed_ms = (time.time() - start) * 1000
            summary.append({
                "rag_type":      rag_type,
                "elapsed_ms":    round(elapsed_ms, 1),
                "answer_len":    len(result.get("answer", "")),
                "retry_count":   result.get("retry_count", 0),
                "relevance":     result.get("relevance", ""),
                "hallucination": result.get("hallucination", ""),
                "route":         result.get("route", ""),
                "answer":        result.get("answer", ""),
            })
            status = "[PASS]"
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            logger.error("%s RAG 실패: %s", rag_type, e, exc_info=True)
            summary.append({
                "rag_type": rag_type, "elapsed_ms": round(elapsed_ms, 1),
                "error": str(e),
            })
            status = "[FAIL]"
        print(f"  {status} {rag_type}: {elapsed_ms:.0f}ms")

    # 비교 테이블 출력
    print(f"\n{_DIVIDER}")
    print("  비교 결과")
    print(_DIVIDER)
    print(f"  {'rag_type':<12} {'소요(ms)':>10} {'답변(자)':>10} {'retry':>6} {'관련성':<12} {'환각':<12} {'route':<14}")
    print(f"  {'─'*12} {'─'*10} {'─'*10} {'─'*6} {'─'*12} {'─'*12} {'─'*14}")
    for s in summary:
        if "error" in s:
            print(f"  {s['rag_type']:<12} {'FAIL':>10}")
        else:
            print(
                f"  {s['rag_type']:<12} {s['elapsed_ms']:>10.1f} "
                f"{s['answer_len']:>10} {s['retry_count']:>6} "
                f"{s.get('relevance',''):<12} {s.get('hallucination',''):<12} "
                f"{s.get('route',''):<14}"
            )

    # 답변 상세 출력
    for s in summary:
        if "answer" in s:
            print(f"\n{_THIN}")
            print(f"  [ {s['rag_type'].upper()} RAG 답변 ]")
            print(_THIN)
            answer = s["answer"]
            for i in range(0, min(len(answer), 400), 80):
                print(f"  {answer[i:i+80]}")
            if len(answer) > 400:
                print(f"  ... (총 {len(answer)}자)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG 워크플로우 테스트 (simple / self / adaptive)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input",  required=True,
                        help="임베딩 JSON 파일 경로 (*_embedding.json)")
    parser.add_argument("--query",  required=True,
                        help="질문 텍스트")
    parser.add_argument("--rag",    default="self",
                        choices=["simple", "self", "adaptive", "all"],
                        help="실행할 RAG 워크플로우 (기본: self)")
    parser.add_argument("--llm",    default="gpt-4o-mini",
                        help="LLM 모델명 (기본: gpt-4o-mini)")
    parser.add_argument("--k",      type=int, default=5,
                        help="검색 문서 수 (기본: 5)")
    parser.add_argument("--db",     default=None,
                        choices=["faiss", "chromadb", None],
                        help="VectorDB 종류 (기본: 자동 라우팅)")
    parser.add_argument("--embed",  default="openai_small",
                        help="쿼리 임베딩 모델 (기본: openai_small)")
    args = parser.parse_args()

    # ── 임베딩 JSON 로드 ──────────────────────────────────────────────────────
    _print_header("입력 파일 로드")
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"  [FAIL] 파일 없음: {input_path}")
        sys.exit(1)

    embedded_chunks, meta = load_embedded_chunks(str(input_path))

    print(f"  입력 파일     : {input_path}")
    print(f"  EmbeddedChunk : {len(embedded_chunks)}개")
    if embedded_chunks:
        ec = embedded_chunks[0]
        print(f"  임베딩 모델   : {ec.embedding_model}")
        print(f"  벡터 차원     : {ec.embedding_dim}")

    # ── VectorDB 구축 ─────────────────────────────────────────────────────────
    _print_header("VectorDB 구축")
    store = VectorDBContext.BuildVectorDB(embedded_chunks, vectordb_type=args.db)
    print(f"  [PASS] VectorDB 구축 완료")

    # ── RAG 실행 ──────────────────────────────────────────────────────────────
    if args.rag == "all":
        run_all(
            store=store,
            question=args.query,
            embedding_type=args.embed,
            k=args.k,
            llm_model=args.llm,
        )
    else:
        run_single(
            store=store,
            question=args.query,
            rag_type=args.rag,
            embedding_type=args.embed,
            k=args.k,
            llm_model=args.llm,
        )


if __name__ == "__main__":
    main()
