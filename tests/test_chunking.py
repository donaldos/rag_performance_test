"""
청킹 파이프라인 테스트 스크립트.

사용법:
    # JSON 파일 입력 (test_pdf_loading.py --save 결과)
    python -m tests.test_chunking --input tests/output/file_pymupdf_loading.json

    # 특정 전략만 테스트
    python -m tests.test_chunking --input docs.json --chunker recursive

    # 전체 전략 일괄 비교
    python -m tests.test_chunking --input docs.json --all

    # 청킹 결과 전체 내용 확인
    python -m tests.test_chunking --input docs.json --inspect
    python -m tests.test_chunking --input docs.json --inspect --chunker semantic
    python -m tests.test_chunking --input docs.json --inspect --chunk-index 0

    # 결과를 JSON으로 저장
    python -m tests.test_chunking --input docs.json --chunker recursive --save
    python -m tests.test_chunking --input docs.json --chunker recursive --save out/chunks.json

    # 사용 가능한 전략 목록
    python -m tests.test_chunking --list-chunkers
"""

from __future__ import annotations

import argparse
import sys
import textwrap
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ragsystem.chunking.chunking_context import ChunkingContext  # noqa: E402
from ragsystem.chunking.router import ChunkingRouter             # noqa: E402
from ragsystem.test.io_utils import (                            # noqa: E402
    default_save_path,
    load_documents,
    save_documents,
)


# ─── 출력 헬퍼 ────────────────────────────────────────────────────────────────

def _hr(char: str = "─", width: int = 60) -> None:
    print(char * width)


def _section(title: str) -> None:
    _hr("═")
    print(f"  {title}")
    _hr("═")


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"  {msg}")


# ─── 개별 테스트 함수 ─────────────────────────────────────────────────────────

def test_list_chunkers() -> None:
    _section("사용 가능한 청킹 전략 목록")
    chunkers = ChunkingContext.available_chunkers()
    if chunkers:
        for c in chunkers:
            _ok(c)
    else:
        _fail("사용 가능한 청커 없음. 의존성 설치 필요.")
    print()


def test_router(docs) -> str | None:
    _section("① ChunkingRouter — 전략 자동 결정")
    try:
        router = ChunkingRouter()
        pdf_type, chunking_type = router.route(docs)
        _ok(f"docs의 pdf_type   : {pdf_type}")
        _ok(f"추천 chunking_type: {chunking_type}")
        print()
        return chunking_type
    except Exception as e:
        _fail(f"Router 오류: {e}")
        print()
        return None


def test_specific_chunker(
    docs,
    chunking_type: str,
    save_path: str | None = None,
    input_path: str = "",
) -> bool:
    _section(f"② 청킹 테스트 (chunking_type='{chunking_type}')")
    available = ChunkingContext.available_chunkers()
    if chunking_type not in available:
        _fail(f"'{chunking_type}' 사용 불가. 사용 가능: {available}")
        print()
        return False
    try:
        t0 = time.perf_counter()
        chunks = ChunkingContext.ChunkingDocs(docs, chunking_type=chunking_type)
        elapsed = time.perf_counter() - t0

        char_counts = [len(c.page_content) for c in chunks]
        avg = sum(char_counts) / len(char_counts) if char_counts else 0
        _ok(f"청킹 성공 — {len(chunks)}개 Chunk")
        _ok(f"소요 시간  : {elapsed * 1000:.1f}ms")
        _info(f"평균 청크 크기 : {avg:.0f}자  (최소 {min(char_counts)}자 / 최대 {max(char_counts)}자)")
        _info("")
        _info("[ 첫 번째 Chunk ]")
        _print_chunk_summary(chunks[0])
        print()

        if save_path is not None:
            loader_type = docs[0].metadata.get("loader_type", "unknown") if docs else "unknown"
            out = save_documents(
                chunks, save_path,
                pdf_path=input_path,
                loader_type=f"{loader_type}+{chunking_type}",
            )
            _ok(f"JSON 저장 완료 → {out}")
            print()
        return True
    except Exception as e:
        _fail(f"'{chunking_type}' 청킹 오류: {e}")
        print()
        return False


def test_all_chunkers(docs, input_path: str = "") -> dict[str, bool]:
    _section("③ 전체 전략 일괄 테스트")
    available = ChunkingContext.available_chunkers()
    results: dict[str, bool] = {}
    for chunking_type in available:
        try:
            t0 = time.perf_counter()
            chunks = ChunkingContext.ChunkingDocs(docs, chunking_type=chunking_type)
            elapsed = time.perf_counter() - t0
            char_counts = [len(c.page_content) for c in chunks]
            avg = sum(char_counts) / len(char_counts) if char_counts else 0
            _ok(
                f"{chunking_type:<18} {len(chunks):>4}개 chunk"
                f" | avg {avg:>5.0f}자"
                f" | {elapsed * 1000:.0f}ms"
            )
            results[chunking_type] = True
        except Exception as e:
            _fail(f"{chunking_type:<18} 오류: {e}")
            results[chunking_type] = False
    print()
    _hr()
    passed = sum(v for v in results.values())
    _info(f"결과: {passed}/{len(results)} 통과")
    _hr()
    print()
    return results


def inspect_chunks(docs, chunking_type: str | None, chunk_index: int | None) -> None:
    effective = chunking_type or "auto"
    _section(f"④ 청크 내용 검사 — chunker: {effective}")
    try:
        chunks = ChunkingContext.ChunkingDocs(docs, chunking_type=chunking_type)
    except Exception as e:
        _fail(f"청킹 오류: {e}")
        return
    if not chunks:
        _fail("청크 없음.")
        return
    _ok(f"총 {len(chunks)}개 Chunk 생성됨")
    print()

    targets = chunks
    if chunk_index is not None:
        if chunk_index >= len(chunks):
            _fail(f"chunk_index={chunk_index} 없음. 범위: 0~{len(chunks) - 1}")
            return
        targets = [chunks[chunk_index]]
        _info(f"chunk_index={chunk_index} 필터 적용")
        print()

    for i, chunk in enumerate(targets):
        meta = chunk.metadata
        _hr("─")
        print(
            f"  [Chunk {meta.get('chunk_index', i)}]"
            f"  chunker={meta.get('chunking_type', '-')}"
            f"  page={meta.get('page', '-')}"
            f"  chars={len(chunk.page_content)}"
            + (f"  role={meta['chunk_role']}" if "chunk_role" in meta else "")
        )
        _hr("─")
        for line in chunk.page_content.splitlines():
            print(f"    {line}")
        print()

    _hr("═")
    total_chars = sum(len(c.page_content) for c in targets)
    _info(f"총 {total_chars}자 / {len(targets)}개 Chunk 출력됨")
    _hr("═")
    print()


# ─── 출력 헬퍼 ────────────────────────────────────────────────────────────────

def _print_chunk_summary(chunk) -> None:
    meta = chunk.metadata
    _info(f"  chunking_type : {meta.get('chunking_type', '-')}")
    _info(f"  chunk_index   : {meta.get('chunk_index', '-')}")
    _info(f"  page          : {meta.get('page', '-')}")
    _info(f"  chars         : {len(chunk.page_content)}")
    if "chunk_role" in meta:
        _info(f"  chunk_role    : {meta['chunk_role']}")
    preview = chunk.page_content.replace("\n", " ").strip()
    _info(f"  content       : {textwrap.shorten(preview, width=80, placeholder='...')}")


# ─── CLI 진입점 ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="청킹 파이프라인 테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", "-i", help="로딩 결과 JSON 파일 경로 (test_pdf_loading --save 출력)")
    parser.add_argument("--chunker", help="특정 chunking_type 지정")
    parser.add_argument("--all", action="store_true", help="설치된 모든 전략 일괄 테스트")
    parser.add_argument("--list-chunkers", action="store_true", help="사용 가능한 전략 목록 출력")
    parser.add_argument("--inspect", action="store_true", help="청킹 결과 전체 내용 출력")
    parser.add_argument("--chunk-index", type=int, default=None, help="--inspect 시 특정 청크만 출력 (예: --chunk-index 0)")
    parser.add_argument(
        "--save", nargs="?", const="__auto__", default=None,
        metavar="PATH",
        help="결과를 JSON으로 저장. PATH 생략 시 tests/output/ 자동 생성",
    )
    args = parser.parse_args()

    print()
    _hr("═")
    print("  Chunking Pipeline — 테스트")
    _hr("═")
    print()

    if args.list_chunkers:
        test_list_chunkers()
        return

    if not args.input:
        _fail("--input 옵션 필요. test_pdf_loading.py --save 로 먼저 JSON을 생성하세요.")
        print()
        parser.print_help()
        sys.exit(1)

    input_path = args.input
    if not Path(input_path).exists():
        _fail(f"파일 없음: {input_path}")
        sys.exit(1)

    docs, meta = load_documents(input_path)
    _info(f"입력 파일  : {input_path}")
    _info(f"원본 PDF   : {meta.get('pdf_path', '-')}")
    _info(f"로더       : {meta.get('loader_type', '-')}")
    _info(f"저장 일시  : {meta.get('created_at', '-')}")
    _info(f"Document 수: {len(docs)}개")
    print()

    # --save 경로 결정
    save_path: str | None = None
    if args.save is not None:
        chunker_key = args.chunker or "auto"
        save_path = (
            str(default_save_path(meta.get("pdf_path", input_path), chunker_key, "chunking"))
            if args.save == "__auto__"
            else args.save
        )

    if args.inspect:
        inspect_chunks(docs, chunking_type=args.chunker, chunk_index=args.chunk_index)
        return

    if args.chunker:
        test_specific_chunker(docs, args.chunker, save_path=save_path, input_path=input_path)
        return

    if args.all:
        test_router(docs)
        test_all_chunkers(docs, input_path=input_path)
        return

    # 기본 흐름: Router → 자동 라우팅 → 추천 전략 개별 테스트
    test_list_chunkers()
    recommended = test_router(docs)
    if recommended:
        test_specific_chunker(docs, recommended, save_path=save_path, input_path=input_path)


if __name__ == "__main__":
    main()
