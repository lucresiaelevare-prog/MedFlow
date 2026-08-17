"""Rota isolada para avaliar a fundação MIP/PIE sem alterar fluxos legados."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core import require_user
from mip.config import phase1_enabled
from mip.contracts import Phase1AssessInput, Phase1AssessResponse
from mip.safety_gateway import assess_post_generation, assess_pre_generation
from mip.trace_store import create_trace, persist_shadow_trace


router = APIRouter(prefix="/api/mip/phase1", tags=["mip-phase1"])


@router.post("/assess", response_model=Phase1AssessResponse)
async def assess_phase1(
    payload: Phase1AssessInput,
    _: dict = Depends(require_user),
) -> Phase1AssessResponse:
    """Avalia segurança e trace sem chamar LLM ou modificar uma rota existente."""
    if not phase1_enabled():
        raise HTTPException(status_code=404, detail="Fase 1 do MIP não está habilitada")
    safety_pre = assess_pre_generation(payload.text)
    safety_post = None
    if payload.generated_text is not None:
        safety_post = assess_post_generation(payload.generated_text)
    trace = create_trace(payload.text, safety_pre, safety_post)
    persisted = await persist_shadow_trace(trace)
    return Phase1AssessResponse(trace=trace, persisted=persisted)