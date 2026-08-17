"""MedFlow — endpoints do ciclo de vida da recomendação (P0.2.1.2).

Fluxo:
    /home/today → devolve `recommendation` com `id`.
    Frontend, ao renderizar:
        POST /api/recommendations/{id}/shown
    Frontend, ao aluno clicar "Começar":
        POST /api/recommendations/{id}/started
    Frontend, ao concluir Pomodoro/atividade:
        POST /api/recommendations/{id}/completed {duration_actual_min}
    Frontend, ao abandonar (fechou/parou antes):
        POST /api/recommendations/{id}/abandoned {abandoned_after_min}

Endpoints administrativos / debug:
    GET /api/recommendations/me/history?days=30
    GET /api/recommendations/me/efficacy?rule=<slug>
    GET /api/recommendations/me/profile
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core import db, require_user
import efficacy

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


class CompletedIn(BaseModel):
    duration_actual_min: int | None = Field(default=None, ge=0, le=600)


class AbandonedIn(BaseModel):
    abandoned_after_min: int | None = Field(default=None, ge=0, le=600)


@router.post("/{rec_id}/shown", status_code=202)
async def rec_shown(rec_id: str, user: dict = Depends(require_user)) -> dict:
    ok = await efficacy.mark_shown(rec_id, user["user_id"])
    return {"ok": ok}


@router.post("/{rec_id}/why-expanded", status_code=202)
async def rec_why_expanded(rec_id: str, user: dict = Depends(require_user)) -> dict:
    """Telemetria de transparência: não altera plano, prioridade ou conteúdo."""
    ok = await efficacy.mark_why_expanded(rec_id, user["user_id"])
    return {"ok": ok, "applied_to_recommendations": False}


@router.post("/{rec_id}/started", status_code=202)
async def rec_started(rec_id: str, user: dict = Depends(require_user)) -> dict:
    ok = await efficacy.mark_started(rec_id, user["user_id"])
    return {"ok": ok}


@router.post("/{rec_id}/completed", status_code=202)
async def rec_completed(
    rec_id: str, body: CompletedIn, user: dict = Depends(require_user)
) -> dict:
    ok = await efficacy.mark_completed(rec_id, user["user_id"], body.duration_actual_min)
    return {"ok": ok}


@router.post("/{rec_id}/abandoned", status_code=202)
async def rec_abandoned(
    rec_id: str, body: AbandonedIn, user: dict = Depends(require_user)
) -> dict:
    ok = await efficacy.mark_abandoned(rec_id, user["user_id"], body.abandoned_after_min)
    return {"ok": ok}


@router.get("/me/history")
async def my_history(days: int = 30, user: dict = Depends(require_user)) -> dict:
    """Últimos eventos do usuário atual (para debug/histórico do próprio aluno)."""
    from datetime import timedelta
    from core import _now, _iso
    since = _iso(_now() - timedelta(days=max(1, min(days, 90))))
    items: list[dict] = []
    async for e in db.recommendation_events.find(
        {"user_id": user["user_id"], "recommended_at": {"$gte": since}},
        {"_id": 0},
    ).sort("recommended_at", -1).limit(200):
        items.append(e)
    return {"since": since, "count": len(items), "items": items}


@router.get("/me/efficacy")
async def my_efficacy(rule: str, user: dict = Depends(require_user)) -> dict:
    return await efficacy.rule_efficacy(user["user_id"], rule)


@router.get("/me/profile")
async def my_profile(user: dict = Depends(require_user)) -> dict:
    return await efficacy.behavior_profile(user["user_id"])


@router.get("/me/learning-profile")
async def my_learning_profile(user: dict = Depends(require_user)) -> dict:
    """Ritmo sustentável ATUAL descoberto por comportamento observado.

    Debug/instrumentação — o motor consome internamente via
    `efficacy.get_effective_typical_min`. Não exposto na UI (por decisão de PO).
    """
    # Pega o declared_typical_min do profile do usuário
    prof = await db.user_profiles.find_one({"user_id": user["user_id"]}, {"_id": 0, "typical_study_min": 1})
    declared = int((prof or {}).get("typical_study_min") or 45)
    return await efficacy.learning_profile(user["user_id"], declared)
