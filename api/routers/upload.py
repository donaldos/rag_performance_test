"""
POST /upload — PDF 파일 업로드 및 세션 생성.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File

from ragsystem.loading.pdf.router import PDFTypeRouter
from api.services.session import create_session

router = APIRouter()
_router = PDFTypeRouter()

UPLOAD_DIR = Path("data/uploads")


@router.post("")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 허용됩니다.")

    # 세션 생성 → 업로드 디렉터리 결정
    state = create_session(pdf_path="")
    save_dir = UPLOAD_DIR / state.session_id
    save_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = str(save_dir / file.filename)

    # 파일 저장
    content = await file.read()
    with open(pdf_path, "wb") as f:
        f.write(content)

    # PDF 유형 감지
    pdf_type = _router.detect_pdf_type(pdf_path)
    state.pdf_path = pdf_path
    state.pdf_type = pdf_type

    return {
        "session_id": state.session_id,
        "filename": file.filename,
        "file_size": len(content),
        "pdf_type": pdf_type,
    }
