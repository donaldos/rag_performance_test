"""
VectorDB 파이프라인 테스트 스크립트.

사용법:
    # 기본: 임베딩 JSON 읽어 자동 라우팅 → VectorDB 구축
    python -m src.test.test_vectordb --input src/test/output/file_openai_small_embedding.json

    # 특정 DB 지정
    python -m src.test.test_vectordb --input embedded.json --db faiss
    python -m src.test.test_vectordb --input embedded.json --db chromadb

    # 두 DB 모두 일괄 비교
    python -m src.test.test_vectordb --input embedded.json --all

    # 구축 후 쿼리 검색
    python -m src.test.test_vectordb --input embedded.json --db faiss --query "연구 방법론"
    python -m src.test.test_vectordb --input embedded.json --db faiss --query "연구 방법론" --k 3

    # 인덱스를 디스크에 저장
    python -m src.test.test_vectordb --input embedded.json --db faiss --save
    python -m src.test.test_vectordb --input embedded.json --db chromadb --save out/chroma_index

    # 사용 가능한 DB 목록
    python -m src.test.test_vectordb --list-dbs
"""

from __future__ import annotations

import argparse
import sys
import textwrap
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.embedding.embedding_context import EmbeddingContext  # noqa: E402
from src.vectordb.vectordb_context import VectorDBContext     # noqa: E402
from src.vectordb.router import VectorDBRouter                # noqa: E402
from src.test.io_utils import load_embedded_chunks            # noqa: E402


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


# ─── 쿼리 임베딩 ─────────────────────────────────────────────────────────────

def _embed_query(query: str, embedder: str) -> list[float]:
    """질의 텍스트를 임베딩 벡터로 변환한다."""
    from langchain_core.documents import Document
    tmp = [Document(page_content=query)]
    embedded = EmbeddingContext.EmbeddingChunks(tmp, embedding_type=embedder)
    return embedded[0].embedding


# ─── 개별 테스트 함수 ─────────────────────────────────────────────────────────

def test_list_dbs() -> None:
    _section("사용 가능한 VectorDB 목록")
    dbs = VectorDBContext.available_vectordbs()
    if dbs:
        for d in dbs:
            _ok(d)
    else:
        _fail("사용 가능한 VectorDB 없음. faiss-cpu / chromadb 설치 필요.")
    print()


def test_router(embedded_chunks) -> str | None:
    _section("① VectorDBRouter — 자동 라우팅")
    try:
        router = VectorDBRouter()
        size_type, vectordb_type = router.route(embedded_chunks)
        _ok(f"데이터셋 크기 유형: {size_type}  ({len(embedded_chunks)}개 청크)")
        _ok(f"추천 vectordb_type : {vectordb_type}")
        print()
        return vectordb_type
    except Exception as e:
        _fail(f"Router 오류: {e}")
        print()
        return None


def test_build(
    embedded_chunks,
    vectordb_type: str,
    save_path: str | None = None,
) -> object | None:
    _section(f"② VectorDB 구축 (vectordb_type='{vectordb_type}')")
    available = VectorDBContext.available_vectordbs()
    if vectordb_type not in available:
        _fail(f"'{vectordb_type}' 사용 불가. 사용 가능: {available}")
        print()
        return None
    try:
        persist_dir = save_path if vectordb_type == "chromadb" and save_path else None

        t0 = time.perf_counter()
        store = VectorDBContext.BuildVectorDB(
            embedded_chunks,
            vectordb_type=vectordb_type,
            persist_dir=persist_dir,
        )
        elapsed = time.perf_counter() - t0

        _ok(f"인덱스 구축 완료 — {len(store)}개 벡터")
        _ok(f"소요 시간 : {elapsed * 1000:.1f}ms")
        print()

        if save_path and vectordb_type != "chromadb":
            out = store.save(save_path)
            _ok(f"인덱스 저장 완료 → {out}")
            print()
        elif save_path and vectordb_type == "chromadb":
            _ok(f"ChromaDB 영구 저장 완료 → {persist_dir}")
            print()

        return store
    except Exception as e:
        _fail(f"'{vectordb_type}' 구축 오류: {e}")
        import traceback
        traceback.print_exc()
        print()
        return None


def test_search(store, query: str, embedder: str, k: int = 5) -> None:
    _section(f"③ 검색 쿼리: \"{query}\"  (k={k})")
    try:
        t0 = time.perf_counter()
        query_vec = _embed_query(query, embedder)
        embed_elapsed = time.perf_counter() - t0

        t1 = time.perf_counter()
        results = VectorDBContext.Search(store, query_vec, k=k)
        search_elapsed = time.perf_counter() - t1

        _ok(f"쿼리 임베딩 : {embed_elapsed * 1000:.1f}ms")
        _ok(f"벡터 검색   : {search_elapsed * 1000:.1f}ms")
        _ok(f"검색 결과   : {len(results)}개")
        print()

        for res in results:
            meta = res.document.metadata
            _hr("─")
            score_label = "similarity" if store.vectordb_name == "chromadb" else "L2 dist"
            print(
                f"  [Rank {res.rank + 1}]"
                f"  {score_label}={res.score:.4f}"
                f"  page={meta.get('page', '-')}"
                f"  chunker={meta.get('chunking_type', '-')}"
                f"  chars={len(res.document.page_content)}"
            )
            _hr("─")
            preview = res.document.page_content.replace("\n", " ").strip()
            print(f"    {textwrap.shorten(preview, width=100, placeholder='...')}")
            print()

    except Exception as e:
        _fail(f"검색 오류: {e}")
        import traceback
        traceback.print_exc()
        print()


def test_all_dbs(embedded_chunks, query: str | None = None, embedder: str = "") -> dict[str, bool]:
    _section("④ 전체 VectorDB 일괄 테스트")
    available = VectorDBContext.available_vectordbs()
    if not available:
        _fail("사용 가능한 VectorDB 없음.")
        print()
        return {}

    results: dict[str, bool] = {}
    for vectordb_type in available:
        try:
            t0 = time.perf_counter()
            store = VectorDBContext.BuildVectorDB(embedded_chunks, vectordb_type=vectordb_type)
            elapsed = time.perf_counter() - t0
            _ok(
                f"{vectordb_type:<12} {len(store):>4}개 벡터"
                f" | {elapsed * 1000:.0f}ms"
            )
            results[vectordb_type] = True
        except Exception as e:
            _fail(f"{vectordb_type:<12} 구축 오류: {e}")
            results[vectordb_type] = False

    print()
    _hr()
    passed = sum(v for v in results.values())
    _info(f"결과: {passed}/{len(results)} 통과")
    _hr()
    print()

    # 쿼리가 있으면 각 DB에서 검색 비교
    if query and embedder:
        _section("⑤ DB별 검색 결과 비교")
        try:
            query_vec = _embed_query(query, embedder)
            for vectordb_type in [k for k, v in results.items() if v]:
                store = VectorDBContext.BuildVectorDB(embedded_chunks, vectordb_type=vectordb_type)
                res_list = VectorDBContext.Search(store, query_vec, k=1)
                if res_list:
                    r = res_list[0]
                    score_label = "sim" if vectordb_type == "chromadb" else "L2"
                    preview = r.document.page_content.replace("\n", " ").strip()
                    _info(f"[{vectordb_type}] {score_label}={r.score:.4f}")
                    _info(f"  → {textwrap.shorten(preview, width=90, placeholder='...')}")
                    print()
        except Exception as e:
            _fail(f"비교 검색 오류: {e}")
        print()

    return results


def _default_save_path(input_path: str, vectordb_type: str) -> str:
    stem = Path(input_path).stem if input_path else "unknown"
    base = Path(__file__).parent / "output" / f"{stem}_{vectordb_type}_index"
    return str(base)


# ─── CLI 진입점 ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="VectorDB 파이프라인 테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", "-i", help="임베딩 결과 JSON (test_embedding.py --save 출력)")
    parser.add_argument("--db", help="특정 vectordb_type 지정 (faiss | chromadb)")
    parser.add_argument("--all", action="store_true", help="모든 VectorDB 일괄 테스트")
    parser.add_argument("--list-dbs", action="store_true", help="사용 가능한 DB 목록 출력")
    parser.add_argument("--query", "-q", help="구축 후 검색할 텍스트 쿼리")
    parser.add_argument("--k", type=int, default=5, help="검색 결과 수 (기본: 5)")
    parser.add_argument(
        "--save", nargs="?", const="__auto__", default=None,
        metavar="PATH",
        help="인덱스를 디스크에 저장. PATH 생략 시 src/test/output/ 자동 생성",
    )
    args = parser.parse_args()

    print()
    _hr("═")
    print("  VectorDB Pipeline — 테스트")
    _hr("═")
    print()

    if args.list_dbs:
        test_list_dbs()
        return

    if not args.input:
        _fail("--input 옵션 필요. test_embedding.py --save 로 먼저 임베딩 JSON을 생성하세요.")
        print()
        parser.print_help()
        sys.exit(1)

    input_path = args.input
    if not Path(input_path).exists():
        _fail(f"파일 없음: {input_path}")
        sys.exit(1)

    embedded_chunks, meta = load_embedded_chunks(input_path)
    embedder = meta.get("embedder", "")

    _info(f"입력 파일     : {input_path}")
    _info(f"임베딩 모델   : {meta.get('embedding_model', '-')}")
    _info(f"임베더 키     : {embedder}")
    _info(f"저장 일시     : {meta.get('created_at', '-')}")
    _info(f"EmbeddedChunk : {len(embedded_chunks)}개  (dim={meta.get('embedding_dim', '-')})")
    print()

    # --save 경로 결정
    save_path: str | None = None
    if args.save is not None:
        db_key = args.db or "auto"
        save_path = (
            _default_save_path(input_path, db_key)
            if args.save == "__auto__"
            else args.save
        )

    if args.all:
        test_router(embedded_chunks)
        test_all_dbs(embedded_chunks, query=args.query, embedder=embedder)
        return

    if args.db:
        store = test_build(embedded_chunks, args.db, save_path=save_path)
        if store and args.query and embedder:
            test_search(store, args.query, embedder=embedder, k=args.k)
        return

    # 기본 흐름: Router → 자동 라우팅 → 구축 → 쿼리(있으면)
    test_list_dbs()
    recommended = test_router(embedded_chunks)
    if recommended:
        store = test_build(embedded_chunks, recommended, save_path=save_path)
        if store and args.query and embedder:
            test_search(store, args.query, embedder=embedder, k=args.k)


if __name__ == "__main__":
    main()
