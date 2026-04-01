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

from frontend.pages import upload, pipeline, rag, vectordb_search

tab1, tab2, tab3, tab4 = st.tabs(["📁 업로드", "⚙️ 파이프라인", "💬 RAG 질의", "🔍 VectorDB 검색"])

with tab1:
    upload.render()

with tab2:
    pipeline.render()

with tab3:
    rag.render()

with tab4:
    vectordb_search.render()
