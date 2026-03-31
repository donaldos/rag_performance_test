"""
POST /upload — PDF 파일 업로드 및 세션 생성 (다중 파일 지원).
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File

from ragsystem.loading.pdf.router import PDFTypeRouter
from api.services.session import create_session

router = APIRouter()
_router = PDFTypeRouter()

UPLOAD_DIR = Path("data/uploads")


@router.post("")
async def upload_pdfs(files: List[UploadFile] = File(...)):
    # 확장자 검사
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"PDF 파일만 허용됩니다: {f.filename}")

    # 세션 생성
    state = create_session(pdf_paths=[])
    save_dir = UPLOAD_DIR / state.session_id
    save_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    pdf_paths = []
    for file in files:
        content = await file.read()
        pdf_path = str(save_dir / file.filename)
        with open(pdf_path, "wb") as fp:
            fp.write(content)

        pdf_type = _router.detect_pdf_type(pdf_path)
        pdf_paths.append(pdf_path)
        uploaded.append({
            "filename": file.filename,
            "file_size": len(content),
            "pdf_type": pdf_type,
        })

    state.pdf_paths = pdf_paths
    state.pdf_type = uploaded[0]["pdf_type"] if uploaded else ""

    return {
        "session_id": state.session_id,
        "file_count": len(uploaded),
        "files": uploaded,
        "pdf_type": state.pdf_type,   # 첫 번째 파일 기준 (대표값)
    }
