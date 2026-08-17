"""Rotas isoladas da Fase 2: observação, Event Store e métricas shadow."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException

from core import require_user
from mip.config import phase2_enabled
from mip.contracts import (
    Phase2Comparison,
    Phase2MetricsResponse,
    Phase2ObservationInput,
    Phase2ObservationResponse,
)
from mip.phase2_adaptive import recommend_shadow
from mip.phase2_store import (
    adaptive_history,
    append_event,
    cache_key_for,
    observe_cache,
    phase2_metrics,
    trace_exists,
)
from routes.admin import require_admin

router = APIRouter(prefix="/api/mip/phase2", tags=["mip-phase2"])


def _comparison_status(legacy_code: str | None, shadow_code: str) -> str:
    if legacy_code is None:
        return "not_compared"
    return "match" if legacy_code == shadow_code else "divergent"


@router.post("/observe", response_model=Phase2ObservationResponse)
async def observe_phase2(
    payload: Phase2ObservationInput,
    user: dict = Depends(require_user),
) -> Phase2ObservationResponse:
    """Mede hipótese de cache e adaptação; não chama IA nem muda resposta legada."""
    if not phase2_enabled():
        raise HTTPException(status_code=404, detail="Fase 2 do MIP não está habilitada")
    if not await trace_exists(payload.trace_id):
        raise HTTPException(status_code=400, detail="trace_id da Fase 1 não encontrado")
    started = time.perf_counter()
    cache = await observe_cache(payload)
    history = await adaptive_history(user["user_id"], cache_key_for(payload))
    history["total"] += 1
    if payload.learning_outcome == "incorrect":
        history["incorrect"] += 1
    if payload.learning_outcome == "completed":
        history["completed"] += 1
    recommendation = recommend_shadow(history)
    comparison_status = _comparison_status(
        payload.legacy_recommendation_code,
        recommendation.code,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    event_id, persisted, idempotent = await append_event(
        payload,
        user["user_id"],
        cache,
        recommendation.model_dump(),
        comparison_status,
        latency_ms,
    )
    return Phase2ObservationResponse(
        trace_id=payload.trace_id,
        event_id=event_id,
        persisted=persisted,
        idempotent=idempotent,
        cache=cache,
        shadow_recommendation=recommendation,
        comparison=Phase2Comparison(status=comparison_status),
    )


@router.get("/metrics", response_model=Phase2MetricsResponse)
async def metrics_phase2(_: dict = Depends(require_admin)) -> Phase2MetricsResponse:
    """Métricas administrativas da Fase 2, sem dados de aluno identificáveis."""
    if not phase2_enabled():
        raise HTTPException(status_code=404, detail="Fase 2 do MIP não está habilitada")
    return await phase2_metrics()