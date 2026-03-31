"""
중앙 로거 설정 모듈.

각 모듈에서 아래와 같이 사용한다:
    from src.utils.logger import get_logger
    logger = get_logger(__name__)

로그 레벨 기준:
    DEBUG   : 파라미터 값, 내부 처리 흐름 (개발 시 확인용)
    INFO    : 정상 처리 완료, Router 결정, 전략 선택
    WARNING : 의존성 미설치로 전략 제외, 빈 결과 등 복구 가능한 상황
    ERROR   : 예외 발생, 처리 실패 (호출부에서 except로 잡힌 오류)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# 로그 파일 위치: 프로젝트 루트/logs/rag_pipeline.log
_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_LOG_FILE = _LOG_DIR / "rag_pipeline.log"

_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def _setup() -> None:
    global _initialized
    if _initialized:
        return

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("src")
    root.setLevel(logging.DEBUG)

    # 콘솔 핸들러 (INFO 이상)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))

    # 파일 핸들러 (DEBUG 이상 — 전체 기록)
    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))

    root.addHandler(console)
    root.addHandler(file_handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """모듈 전용 로거를 반환한다. name에는 __name__을 전달한다."""
    _setup()
    return logging.getLogger(name)
