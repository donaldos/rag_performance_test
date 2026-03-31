"""
Tab 1 — PDF 업로드 (다중 파일 지원).
"""
from __future__ import annotations

import streamlit as st
from frontend.components.api_client import upload_pdfs

_PDF_TYPE_DESC = {
    "text":  "텍스트 레이어 PDF — 권장 로더: pymupdf, pdfplumber",
    "table": "표 중심 PDF — 권장 로더: camelot, pdfplumber",
    "graph": "그래프·이미지 포함 PDF — 권장 로더: llamaparse, unstructured",
    "scan":  "스캔 PDF (OCR 필요) — 권장 로더: azure_di, tesseract",
    "mixed": "복합형 PDF — 권장 로더: pymupdf, unstructured",
}


def render() -> None:
    st.header("Step 1 — PDF 업로드")

    uploaded_files = st.file_uploader(
        "PDF 파일을 선택하거나 드래그하세요 (여러 파일 가능)",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("PDF 파일을 하나 이상 업로드하면 자동으로 유형을 감지합니다.")
        return

    # 업로드 예정 파일 목록 표시
    st.write(f"**{len(uploaded_files)}개 파일 선택됨**")
    rows = [
        {"파일명": f.name, "크기": f"{len(f.getvalue()) / 1024:.1f} KB"}
        for f in uploaded_files
    ]
    st.table(rows)

    if st.button("업로드 및 유형 감지", type="primary"):
        with st.spinner(f"{len(uploaded_files)}개 파일 업로드 중..."):
            try:
                res = upload_pdfs(uploaded_files)
            except Exception as e:
                st.error(f"업로드 실패: {e}")
                return

        st.session_state["session_id"]      = res["session_id"]
        st.session_state["pdf_type"]        = res["pdf_type"]
        st.session_state["completed_steps"] = []

        st.success(f"업로드 완료! Session ID: `{res['session_id']}`  ({res['file_count']}개 파일)")

        # 파일별 감지 유형 표시
        st.subheader("파일별 PDF 유형 감지 결과")
        for info in res.get("files", []):
            t = info["pdf_type"]
            st.markdown(
                f"- **{info['filename']}** ({info['file_size']//1024} KB) &nbsp;→&nbsp; "
                f"`{t}` — {_PDF_TYPE_DESC.get(t, '')}"
            )
