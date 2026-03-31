"""
Streamlit 프론트엔드 진입점.

실행:
    streamlit run frontend/app.py --server.port 8501
"""

import streamlit as st

st.set_page_config(
    page_title="evalRAG — PDF RAG Pipeline",
    page_icon="📄",
    layout="wide",
)

st.title("📄 evalRAG — PDF RAG Pipeline")
st.caption("PDF 업로드 → Loading → Chunking → Embedding → VectorDB → RAG 질의")

st.info("🚧 구현 예정 — .claude/frontend/SKILL.md 를 참고하여 구현하세요.")

# 구현 시 아래 페이지 모듈을 import하여 사용
# from frontend.pages import upload, pipeline, rag
