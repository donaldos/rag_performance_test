"""
임베딩 파이프라인 테스트 스크립트.

사용법:
    # 기본: 청킹 JSON 읽어 자동 라우팅 임베딩
    python -m src.test.test_embedding --input src/test/output/file_recursive_chunking.json

    # 특정 임베더 지정
    python -m src.test.test_embedding --input chunks.json --embedder openai_small
    python -m src.test.test_embedding --input chunks.json --embedder huggingface_ko

    # 설치된 모든 임베더 일괄 비교
    python -m src.test.test_embedding --input chunks.json --all

    # 임베딩 벡터 미리보기
    python -m src.test.test_embedding --input chunks.json --inspect
    python -m src.test.test_embedding --input chunks.json --inspect --chunk-index 2

    # 결과를 JSON으로 저장
    python -m src.test.test_embedding --input chunks.json --embedder openai_small --save
    python -m src.test.test_embedding --input chunks.json --embedder openai_small --save out/embedded.json

    # 사용 가능한 임베더 목록
    python -m src.test.test_embedding --list-embedders
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
import time
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.embedding.embedding_context import EmbeddingContext  # noqa: E402
from src.embedding.router import EmbeddingRouter              # noqa: E402
from src.test.io_utils import default_save_path, load_documents  # noqa: E402


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


# ─── EmbeddedChunk JSON 직렬화 ────────────────────────────────────────────────

def _save_embedded(
    embedded,
    path: str | Path,
    *,
    input_path: str = "",
    embedder: str = "",
) -> Path:
    """List[EmbeddedChunk]를 JSON 파일로 저장한다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "input_path": input_path,
        "embedder": embedder,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "chunk_count": len(embedded),
        "embedding_dim": embedded[0].embedding_dim if embedded else 0,
        "embedding_model": embedded[0].embedding_model if embedded else "",
        "chunks": [
            {
                "page_content": ec.document.page_content,
                "metadata": ec.document.metadata,
                "embedding": ec.embedding,
                "embedding_model": ec.embedding_model,
                "embedding_dim": ec.embedding_dim,
            }
            for ec in embedded
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _default_embed_save_path(input_path: str, embedder: str) -> Path:
    """저장 경로 자동 생성: src/test/output/{stem}_{embedder}_embedding.json"""
    stem = Path(input_path).stem if input_path else "unknown"
    return Path(__file__).parent / "output" / f"{stem}_{embedder}_embedding.json"


# ─── 개별 테스트 함수 ─────────────────────────────────────────────────────────

def test_list_embedders() -> None:
    _section("사용 가능한 임베딩 모델 목록")
    embedders = EmbeddingContext.available_embeddings()
    if embedders:
        for e in embedders:
            _ok(e)
    else:
        _fail("사용 가능한 임베더 없음. 의존성 및 API 키 확인 필요.")
    print()


def test_router(chunks) -> str | None:
    _section("① EmbeddingRouter — 언어 감지 및 자동 라우팅")
    try:
        router = EmbeddingRouter()
        language, embedding_type = router.route(chunks)
        _ok(f"감지 언어        : {language}")
        _ok(f"추천 embedding_type: {embedding_type}")
        print()
        return embedding_type
    except Exception as e:
        _fail(f"Router 오류: {e}")
        print()
        return None


def test_specific_embedder(
    chunks,
    embedding_type: str,
    save_path: str | None = None,
    input_path: str = "",
) -> bool:
    _section(f"② 임베딩 테스트 (embedding_type='{embedding_type}')")
    available = EmbeddingContext.available_embeddings()
    if embedding_type not in available:
        _fail(f"'{embedding_type}' 사용 불가. 사용 가능: {available}")
        print()
        return False
    try:
        t0 = time.perf_counter()
        embedded = EmbeddingContext.EmbeddingChunks(chunks, embedding_type=embedding_type)
        elapsed = time.perf_counter() - t0

        _ok(f"임베딩 성공 — {len(embedded)}개 EmbeddedChunk")
        _ok(f"소요 시간       : {elapsed * 1000:.1f}ms")
        if embedded:
            ec = embedded[0]
            _ok(f"임베딩 모델     : {ec.embedding_model}")
            _ok(f"벡터 차원       : {ec.embedding_dim}")
            _info("")
            _info("[ 첫 번째 EmbeddedChunk ]")
            _print_embedded_summary(ec)
        print()

        if save_path is not None:
            out = _save_embedded(
                embedded, save_path,
                input_path=input_path,
                embedder=embedding_type,
            )
            _ok(f"JSON 저장 완료 → {out}")
            print()
        return True
    except Exception as e:
        _fail(f"'{embedding_type}' 임베딩 오류: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False


def test_all_embedders(chunks, input_path: str = "") -> dict[str, bool]:
    _section("③ 전체 임베더 일괄 테스트")
    available = EmbeddingContext.available_embeddings()
    if not available:
        _fail("사용 가능한 임베더 없음.")
        print()
        return {}

    results: dict[str, bool] = {}
    for embedding_type in available:
        try:
            t0 = time.perf_counter()
            embedded = EmbeddingContext.EmbeddingChunks(chunks, embedding_type=embedding_type)
            elapsed = time.perf_counter() - t0
            dim = embedded[0].embedding_dim if embedded else 0
            model = embedded[0].embedding_model if embedded else "-"
            _ok(
                f"{embedding_type:<18} {len(embedded):>4}개 chunk"
                f" | dim {dim:>4}"
                f" | {elapsed * 1000:.0f}ms"
                f" | {model}"
            )
            results[embedding_type] = True
        except Exception as e:
            _fail(f"{embedding_type:<18} 오류: {e}")
            results[embedding_type] = False

    print()
    _hr()
    passed = sum(v for v in results.values())
    _info(f"결과: {passed}/{len(results)} 통과")
    _hr()
    print()
    return results


def inspect_embeddings(chunks, embedding_type: str | None, chunk_index: int | None) -> None:
    effective = embedding_type or "auto"
    _section(f"④ 임베딩 벡터 검사 — embedder: {effective}")
    try:
        embedded = EmbeddingContext.EmbeddingChunks(chunks, embedding_type=embedding_type)
    except Exception as e:
        _fail(f"임베딩 오류: {e}")
        return

    if not embedded:
        _fail("임베딩 결과 없음.")
        return

    _ok(f"총 {len(embedded)}개 EmbeddedChunk 생성됨")
    ec0 = embedded[0]
    _info(f"모델: {ec0.embedding_model}  차원: {ec0.embedding_dim}")
    print()

    targets = embedded
    if chunk_index is not None:
        if chunk_index >= len(embedded):
            _fail(f"chunk_index={chunk_index} 없음. 범위: 0~{len(embedded) - 1}")
            return
        targets = [embedded[chunk_index]]
        _info(f"chunk_index={chunk_index} 필터 적용")
        print()

    for i, ec in enumerate(targets):
        meta = ec.document.metadata
        _hr("─")
        print(
            f"  [Chunk {meta.get('chunk_index', i)}]"
            f"  embedder={ec.embedding_model}"
            f"  dim={ec.embedding_dim}"
            f"  chars={len(ec.document.page_content)}"
        )
        _hr("─")
        preview = ec.document.page_content.replace("\n", " ").strip()
        print(f"    content : {textwrap.shorten(preview, width=80, placeholder='...')}")
        vec_preview = ", ".join(f"{v:.4f}" for v in ec.embedding[:5])
        print(f"    vector  : [{vec_preview}, ...]  ({ec.embedding_dim}차원)")
        print()

    _hr("═")
    _info(f"{len(targets)}개 EmbeddedChunk 출력됨")
    _hr("═")
    print()


# ─── 출력 헬퍼 ────────────────────────────────────────────────────────────────

def _print_embedded_summary(ec) -> None:
    meta = ec.document.metadata
    _info(f"  embedding_model : {ec.embedding_model}")
    _info(f"  embedding_dim   : {ec.embedding_dim}")
    _info(f"  chunk_index     : {meta.get('chunk_index', '-')}")
    _info(f"  chunking_type   : {meta.get('chunking_type', '-')}")
    _info(f"  chars           : {len(ec.document.page_content)}")
    preview = ec.document.page_content.replace("\n", " ").strip()
    _info(f"  content         : {textwrap.shorten(preview, width=80, placeholder='...')}")
    vec_preview = ", ".join(f"{v:.4f}" for v in ec.embedding[:5])
    _info(f"  vector[:5]      : [{vec_preview}, ...]")


# ─── CLI 진입점 ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="임베딩 파이프라인 테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", "-i", help="청킹 결과 JSON 파일 경로 (test_chunking.py --save 출력)")
    parser.add_argument("--embedder", help="특정 embedding_type 지정 (예: openai_small, huggingface_ko)")
    parser.add_argument("--all", action="store_true", help="설치된 모든 임베더 일괄 테스트")
    parser.add_argument("--list-embedders", action="store_true", help="사용 가능한 임베더 목록 출력")
    parser.add_argument("--inspect", action="store_true", help="임베딩 벡터 미리보기 출력")
    parser.add_argument("--chunk-index", type=int, default=None, help="--inspect 시 특정 청크만 출력 (예: --chunk-index 0)")
    parser.add_argument(
        "--save", nargs="?", const="__auto__", default=None,
        metavar="PATH",
        help="결과를 JSON으로 저장. PATH 생략 시 src/test/output/ 자동 생성",
    )
    args = parser.parse_args()

    print()
    _hr("═")
    print("  Embedding Pipeline — 테스트")
    _hr("═")
    print()

    if args.list_embedders:
        test_list_embedders()
        return

    if not args.input:
        _fail("--input 옵션 필요. test_chunking.py --save 로 먼저 청킹 JSON을 생성하세요.")
        print()
        parser.print_help()
        sys.exit(1)

    input_path = args.input
    if not Path(input_path).exists():
        _fail(f"파일 없음: {input_path}")
        sys.exit(1)

    chunks, meta = load_documents(input_path)
    _info(f"입력 파일  : {input_path}")
    _info(f"원본 경로  : {meta.get('pdf_path', '-')}")
    _info(f"로더/청커  : {meta.get('loader_type', '-')}")
    _info(f"저장 일시  : {meta.get('created_at', '-')}")
    _info(f"Chunk 수   : {len(chunks)}개")
    print()

    # --save 경로 결정
    save_path: str | None = None
    if args.save is not None:
        embedder_key = args.embedder or "auto"
        save_path = (
            str(_default_embed_save_path(input_path, embedder_key))
            if args.save == "__auto__"
            else args.save
        )

    if args.inspect:
        inspect_embeddings(chunks, embedding_type=args.embedder, chunk_index=args.chunk_index)
        return

    if args.embedder:
        test_specific_embedder(chunks, args.embedder, save_path=save_path, input_path=input_path)
        return

    if args.all:
        test_router(chunks)
        test_all_embedders(chunks, input_path=input_path)
        return

    # 기본 흐름: Router → 자동 라우팅 → 추천 임베더 테스트
    test_list_embedders()
    recommended = test_router(chunks)
    if recommended:
        test_specific_embedder(chunks, recommended, save_path=save_path, input_path=input_path)


if __name__ == "__main__":
    main()
