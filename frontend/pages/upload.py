"""
Tab 1 — PDF 업로드.
"""
from __future__ import annotations

import streamlit as st
from frontend.components import api_client

_PDF_TYPE_DESC = {
    "text":  "텍스트 레이어 PDF — 권장 로더: pymupdf, pdfplumber",
    "table": "표 중심 PDF — 권장 로더: camelot, pdfplumber",
    "graph": "그래프·이미지 포함 PDF — 권장 로더: llamaparse, unstructured",
    "scan":  "스캔 PDF (OCR 필요) — 권장 로더: azure_di, tesseract",
    "mixed": "복합형 PDF — 권장 로더: pymupdf, unstructured",
}


def render() -> None:
    st.header("Step 1 — PDF 업로드")

    uploaded = st.file_uploader("PDF 파일을 선택하거나 드래그하세요", type=["pdf"])

    if uploaded is None:
        st.info("PDF 파일을 업로드하면 자동으로 유형을 감지합니다.")
        return

    col1, col2 = st.columns(2)
    col1.metric("파일명", uploaded.name)
    col2.metric("파일 크기", f"{len(uploaded.getvalue()) / 1024:.1f} KB")

    if st.button("업로드 및 유형 감지", type="primary"):
        with st.spinner("업로드 중..."):
            try:
                res = api_client.upload_pdf(uploaded)
            except Exception as e:
                st.error(f"업로드 실패: {e}")
                return

        st.session_state["session_id"] = res["session_id"]
        st.session_state["pdf_type"]   = res["pdf_type"]
        st.session_state["completed_steps"] = []

        st.success(f"업로드 완료! Session ID: `{res['session_id']}`")

        pdf_type = res["pdf_type"]
        st.info(f"**감지된 PDF 유형:** `{pdf_type}`\n\n{_PDF_TYPE_DESC.get(pdf_type, '')}")
