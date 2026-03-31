"""
POST /pipeline/run  — 지정한 단계 실행
GET  /pipeline/status/{session_id} — 완료 단계 + 요약 반환
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models.pipeline import (
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineStatusResponse,
    StepSummary,
)
from api.services import session as session_svc
from api.services import pipeline as pipeline_svc

router = APIRouter()

_STEP_HANDLERS = {
    "loading":   pipeline_svc.run_loading,
    "chunking":  pipeline_svc.run_chunking,
    "embedding": pipeline_svc.run_embedding,
    "vectordb":  pipeline_svc.run_vectordb,
}

_STEP_PREREQS = {
    "loading":   [],
    "chunking":  ["loading"],
    "embedding": ["loading", "chunking"],
    "vectordb":  ["loading", "chunking", "embedding"],
}


@router.post("/run")
def run_step(req: PipelineRunRequest):
    state = session_svc.get_session(req.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    if req.step not in _STEP_HANDLERS:
        raise HTTPException(status_code=400, detail=f"알 수 없는 단계: {req.step}")

    # 선행 단계 완료 여부 확인
    for prereq in _STEP_PREREQS[req.step]:
        if prereq not in state.completed_steps:
            raise HTTPException(
                status_code=400,
                detail=f"'{prereq}' 단계를 먼저 실행하세요.",
            )

    try:
        summary = _STEP_HANDLERS[req.step](state, req.options)
        return PipelineRunResponse(
            session_id=req.session_id,
            step=req.step,
            status="success",
            summary=summary,
        )
    except Exception as e:
        return PipelineRunResponse(
            session_id=req.session_id,
            step=req.step,
            status="error",
            summary=StepSummary(),
            error=str(e),
        )


@router.get("/status/{session_id}")
def get_status(session_id: str):
    state = session_svc.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    return PipelineStatusResponse(
        session_id=session_id,
        completed_steps=state.completed_steps,
        summary=state.summary,
    )
