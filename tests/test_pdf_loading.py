"""
PDF 로딩 테스트 스크립트.

사용법:
    # 자동 라우팅 + 전체 테스트
    python -m tests.test_pdf_loading path/to/file.pdf

    # 특정 로더만 테스트
    python -m tests.test_pdf_loading path/to/file.pdf --loader pymupdf

    # 결과를 JSON으로 저장 (test_chunking.py 입력용)
    python -m tests.test_pdf_loading path/to/file.pdf --loader pymupdf --save
    python -m tests.test_pdf_loading path/to/file.pdf --loader pymupdf --save out/docs.json

    # 로딩 결과 전체 내용 확인 (페이지별)
    python -m tests.test_pdf_loading path/to/file.pdf --inspect
    python -m tests.test_pdf_loading path/to/file.pdf --inspect --loader pdfplumber
    python -m tests.test_pdf_loading path/to/file.pdf --inspect --page 2

    # 사용 가능한 로더 목록 확인
    python -m tests.test_pdf_loading --list-loaders
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

from ragsystem.loading.pdf.loader_context import PDFLoaderContext  # noqa: E402
from ragsystem.loading.pdf.router import PDFTypeRouter            # noqa: E402
from ragsystem.test.io_utils import default_save_path, load_documents, save_documents  # noqa: E402


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

def test_list_loaders() -> None:
    _section("사용 가능한 로더 목록")
    loaders = PDFLoaderContext.available_loaders()
    if loaders:
        for loader in loaders:
            _ok(loader)
    else:
        _fail("사용 가능한 로더 없음. 의존성 설치 필요.")
    print()


def test_router(pdf_path: str) -> str | None:
    _section("① Router — PDF 유형 자동 감지")
    try:
        router = PDFTypeRouter()
        t0 = time.perf_counter()
        pdf_type, loader_type = router.route(pdf_path)
        elapsed = time.perf_counter() - t0
        _ok(f"감지된 pdf_type  : {pdf_type}")
        _ok(f"추천 loader_type : {loader_type}")
        _info(f"소요 시간        : {elapsed * 1000:.1f}ms")
        print()
        return loader_type
    except Exception as e:
        _fail(f"Router 오류: {e}")
        print()
        return None


def test_auto_routing(pdf_path: str) -> bool:
    _section("② 자동 라우팅 로딩 (loader_type=None)")
    try:
        t0 = time.perf_counter()
        docs = PDFLoaderContext.LoadingPDFDatas(pdf_path)
        elapsed = time.perf_counter() - t0
        _ok(f"로딩 성공 — {len(docs)}개 Document")
        _ok(f"소요 시간  : {elapsed * 1000:.1f}ms")
        if docs:
            _info("")
            _info("[ 첫 번째 Document ]")
            _print_doc_summary(docs[0])
        else:
            _fail("반환된 Document 없음 — 로더가 내용을 추출하지 못했습니다.")
        print()
        return True
    except Exception as e:
        _fail(f"자동 라우팅 오류: {e}")
        print()
        return False


def test_specific_loader(
    pdf_path: str,
    loader_type: str,
    save_path: str | None = None,
) -> bool:
    _section(f"③ 수동 Override 로딩 (loader_type='{loader_type}')")
    available = PDFLoaderContext.available_loaders()
    if loader_type not in available:
        _fail(f"'{loader_type}' 미설치. 사용 가능: {available}")
        print()
        return False
    try:
        t0 = time.perf_counter()
        docs = PDFLoaderContext.LoadingPDFDatas(pdf_path, loader_type=loader_type)
        elapsed = time.perf_counter() - t0
        _ok(f"로딩 성공 — {len(docs)}개 Document")
        _ok(f"소요 시간  : {elapsed * 1000:.1f}ms")
        if docs:
            _info("")
            _info("[ 첫 번째 Document ]")
            _print_doc_summary(docs[0])
        else:
            _fail("반환된 Document 없음 — 로더가 내용을 추출하지 못했습니다.")
        print()

        if save_path is not None:
            out = save_documents(docs, save_path, pdf_path=pdf_path, loader_type=loader_type)
            _ok(f"JSON 저장 완료 → {out}")
            print()
        return True
    except Exception as e:
        _fail(f"'{loader_type}' 로딩 오류: {e}")
        print()
        return False


def test_all_available_loaders(pdf_path: str) -> dict[str, bool]:
    _section("④ 전체 로더 일괄 테스트")
    available = PDFLoaderContext.available_loaders()
    results: dict[str, bool] = {}
    for loader_type in available:
        try:
            t0 = time.perf_counter()
            docs = PDFLoaderContext.LoadingPDFDatas(pdf_path, loader_type=loader_type)
            elapsed = time.perf_counter() - t0
            char_count = sum(len(d.page_content) for d in docs)
            _ok(f"{loader_type:<15} {len(docs):>3}개 doc | {char_count:>6}자 | {elapsed * 1000:.0f}ms")
            results[loader_type] = True
        except Exception as e:
            _fail(f"{loader_type:<15} 오류: {e}")
            results[loader_type] = False
    print()
    _hr()
    passed = sum(v for v in results.values())
    _info(f"결과: {passed}/{len(results)} 통과")
    _hr()
    print()
    return results


def inspect_docs(pdf_path: str, loader_type: str | None, page: int | None) -> None:
    effective_loader = loader_type or "auto"
    _section(f"⑤ 내용 검사 — loader: {effective_loader}")
    try:
        docs = PDFLoaderContext.LoadingPDFDatas(pdf_path, loader_type=loader_type)
    except Exception as e:
        _fail(f"로딩 오류: {e}")
        return
    _print_doc_list(docs, page)


def inspect_docs_from_json(json_path: str, page: int | None) -> None:
    """저장된 로딩 JSON 파일을 읽어 내용을 검사한다."""
    _section("⑤ 로딩 JSON 검사")
    if not Path(json_path).exists():
        _fail(f"파일 없음: {json_path}")
        return
    docs, meta = load_documents(json_path)
    _info(f"원본 PDF   : {meta.get('pdf_path', '-')}")
    _info(f"로더       : {meta.get('loader_type', '-')}")
    _info(f"저장 일시  : {meta.get('created_at', '-')}")
    print()
    _print_doc_list(docs, page)


def _print_doc_list(docs, page: int | None) -> None:
    if not docs:
        _fail("Document 없음.")
        return
    _ok(f"총 {len(docs)}개 Document")

    # 통계 요약
    char_counts = [len(d.page_content) for d in docs]
    total_chars = sum(char_counts)
    avg_chars = total_chars / len(docs) if docs else 0
    pages = sorted({d.metadata.get("page", "-") for d in docs})
    _info(f"총 문자 수   : {total_chars:,}자  (평균 {avg_chars:.0f}자/페이지)")
    _info(f"페이지 범위  : {pages[0]} ~ {pages[-1]}  ({len(pages)}페이지)")
    if docs:
        sample_meta = docs[0].metadata
        _info(f"loader_type  : {sample_meta.get('loader_type', '-')}")
        _info(f"pdf_type     : {sample_meta.get('pdf_type', '-')}")
        _info(f"auto_routed  : {sample_meta.get('auto_routed', '-')}")
    print()

    # 페이지 필터
    targets = docs
    if page is not None:
        targets = [d for d in docs if d.metadata.get("page") == page]
        if not targets:
            _fail(f"page={page} 없음. 존재하는 page: {pages}")
            return
        _info(f"page={page} 필터 적용 → {len(targets)}개 Document")
        print()

    for i, doc in enumerate(targets):
        meta = doc.metadata
        _hr("─")
        print(
            f"  [Doc {i + 1}/{len(targets)}]"
            f"  page={meta.get('page', '-')}"
            f"  loader={meta.get('loader_type', '-')}"
            f"  pdf_type={meta.get('pdf_type', '-')}"
            f"  chars={len(doc.page_content)}"
        )
        _hr("─")
        for line in doc.page_content.splitlines():
            print(f"    {line}")
        print()

    _hr("═")
    total_chars = sum(len(d.page_content) for d in targets)
    _info(f"총 {total_chars:,}자 / {len(targets)}개 Document 출력됨")
    _hr("═")
    print()


# ─── 출력 헬퍼 ────────────────────────────────────────────────────────────────

def _print_doc_summary(doc) -> None:
    meta = doc.metadata
    _info(f"  loader_type : {meta.get('loader_type', '-')}")
    _info(f"  pdf_type    : {meta.get('pdf_type', '-')}")
    _info(f"  auto_routed : {meta.get('auto_routed', '-')}")
    _info(f"  page        : {meta.get('page', '-')}")
    preview = doc.page_content.replace("\n", " ").strip()
    _info(f"  content     : {textwrap.shorten(preview, width=80, placeholder='...')}")


# ─── CLI 진입점 ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PDF 로딩 파이프라인 테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("pdf", nargs="?", help="테스트할 PDF 파일 경로")
    parser.add_argument("--input", "-i", help="저장된 로딩 JSON 파일 검사 (PDF 없이 결과 확인)")
    parser.add_argument("--loader", help="특정 loader_type 지정")
    parser.add_argument("--all", action="store_true", help="설치된 모든 로더 일괄 테스트")
    parser.add_argument("--list-loaders", action="store_true", help="사용 가능한 로더 목록 출력")
    parser.add_argument("--inspect", action="store_true", help="로딩 결과 전체 내용 출력")
    parser.add_argument("--page", type=int, default=None, help="--inspect 시 특정 페이지만 출력")
    parser.add_argument(
        "--save", nargs="?", const="__auto__", default=None,
        metavar="PATH",
        help="결과를 JSON으로 저장. PATH 생략 시 tests/output/ 자동 생성",
    )
    args = parser.parse_args()

    print()
    _hr("═")
    print("  PDF Loading Pipeline — 테스트")
    _hr("═")
    print()

    if args.list_loaders:
        test_list_loaders()
        return

    # JSON 파일 직접 검사 모드 (PDF 없이)
    if args.input:
        inspect_docs_from_json(args.input, page=args.page)
        return

    if not args.pdf:
        _fail("PDF 파일 경로 또는 --input JSON 경로 필요.")
        print()
        parser.print_help()
        sys.exit(1)

    pdf_path = args.pdf
    if not Path(pdf_path).exists():
        _fail(f"파일 없음: {pdf_path}")
        sys.exit(1)

    _info(f"대상 파일: {pdf_path}")
    print()

    if args.inspect:
        inspect_docs(pdf_path, loader_type=args.loader, page=args.page)
        return

    # --save 경로 결정
    save_path: str | None = None
    if args.save is not None:
        loader_key = args.loader or "auto"
        save_path = (
            str(default_save_path(pdf_path, loader_key))
            if args.save == "__auto__"
            else args.save
        )

    if args.loader:
        test_specific_loader(pdf_path, args.loader, save_path=save_path)
        return

    if args.all:
        test_router(pdf_path)
        test_all_available_loaders(pdf_path)
        return

    # 기본 흐름
    test_list_loaders()
    test_router(pdf_path)   # 이상적인 추천 표시 (정보용)
    test_auto_routing(pdf_path)

    # 저장 시: 설치된 로더 중 최적을 선택해 저장 (자동 폴백)
    _, best_available = PDFTypeRouter().route_available(
        pdf_path, PDFLoaderContext.available_loaders()
    )
    test_specific_loader(pdf_path, best_available, save_path=save_path)


if __name__ == "__main__":
    main()
