"""
FastAPI 서버 진입점.

실행:
    uvicorn api.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import upload, pipeline, rag, vectordb

app = FastAPI(
    title="evalRAG API",
    description="PDF RAG Pipeline REST API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router,   prefix="/upload",   tags=["upload"])
app.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
app.include_router(rag.router,      prefix="/rag",      tags=["rag"])
app.include_router(vectordb.router, prefix="/vectordb", tags=["vectordb"])


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
