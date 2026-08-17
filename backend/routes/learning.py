"""MedFlow — Learning Memory routes (P0.2.2).

Endpoints públicos do banco de conteúdo compartilhado + eventos individuais.
Nenhum UI ainda — só cérebro.

- POST /api/learning/request                → busca ou gera conteúdo
- POST /api/learning/content/{id}/answered   → registra tentativa (correta/errada)
- POST /api/learning/content/{id}/reviewed   → registra revisão
- POST /api/learning/content/{id}/completed  → registra conclusão
- POST /api/learning/content/{id}/reported-error → aluno reporta erro
- GET  /api/learning/me/mastery              → mastery agregada do aluno
- GET  /api/learning/me/weakest              → subtema mais fraco (debug)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import learning_memory as lm
from core import require_user

router = APIRouter(prefix="/api/learning", tags=["learning"])


class ContentRequestIn(BaseModel):
    kind: str = Field(pattern="^(question|flashcard|summary|explanation|mindmap|review|clinical_case)$")
    discipline: str = Field(min_length=2, max_length=80)
    topic: str = Field(min_length=2, max_length=120)
    subtopic: Optional[str] = Field(default=None, max_length=120)
    period: Optional[int] = Field(default=None, ge=1, le=12)
    variant: str = Field(default="default", max_length=40)


@router.post("/request")
async def request_content(body: ContentRequestIn, user: dict = Depends(require_user)) -> dict:
    """Fluxo memória-antes-de-IA (single source of truth para geração)."""
    from ai_router import AIRouterError
    try:
        result = await lm.request_content(
            user_id=user["user_id"],
            kind=body.kind,
            discipline=body.discipline,
            topic=body.topic,
            subtopic=body.subtopic,
            period=body.period,
            variant=body.variant,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (AIRouterError, lm.CircuitOpenError) as exc:
        raise HTTPException(
            status_code=502,
            detail="A geração de conteúdo está temporariamente indisponível. Tente novamente em instantes.",
        ) from exc
    return result


class AnsweredIn(BaseModel):
    correct: bool
    time_spent_sec: Optional[int] = Field(default=None, ge=0, le=3600)


@router.post("/content/{content_id}/answered", status_code=202)
async def content_answered(
    content_id: str, body: AnsweredIn, user: dict = Depends(require_user)
) -> dict:
    try:
        await lm.register_attempt(content_id, body.correct)
        evt = await lm.log_event(
            user["user_id"], content_id, "answered",
            correct=body.correct, time_spent_sec=body.time_spent_sec,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Sinal de fadiga em sessão ativa (P4 do briefing).
    # Se detectado, o cliente pode interromper a recomendação atual e
    # sugerir pausa. O sinal é sempre retornado (fatigued=false quando não há).
    from context_engine import detect_fatigue
    fatigue = await detect_fatigue(user["user_id"])

    # Curva de esquecimento (SRS) — só atualiza para kinds elegíveis.
    # Não bloqueia o retorno se falhar.
    import spaced_review as sr
    try:
        sched = await sr.register_review(
            user["user_id"], content_id, body.correct, body.time_spent_sec,
        )
    except Exception:  # noqa: BLE001
        sched = None

    return {"ok": True, "event_id": evt, "fatigue": fatigue, "review": sched}


@router.get("/me/fatigue")
async def my_fatigue(user: dict = Depends(require_user)) -> dict:
    """Poll de fadiga — útil pra clientes que preferem checar sob demanda
    em vez de olhar o retorno de /answered."""
    from context_engine import detect_fatigue
    return await detect_fatigue(user["user_id"])


@router.get("/me/due")
async def my_due(
    limit: int = 20, user: dict = Depends(require_user)
) -> dict:
    """Curva de esquecimento — conteúdos com revisão vencida agora.

    Só retorna conteúdo já visto pelo aluno (question/flashcard). Mais
    atrasados primeiro. Enriquecido com payload pra evitar round-trip.
    """
    import spaced_review as sr
    items = await sr.get_due(user["user_id"], limit=max(1, min(limit, 50)))
    return {
        "count": len(items),
        "items": items,
    }


class ReviewedIn(BaseModel):
    time_spent_sec: Optional[int] = Field(default=None, ge=0, le=3600)


@router.post("/content/{content_id}/reviewed", status_code=202)
async def content_reviewed(
    content_id: str, body: ReviewedIn, user: dict = Depends(require_user)
) -> dict:
    try:
        evt = await lm.log_event(
            user["user_id"], content_id, "reviewed",
            time_spent_sec=body.time_spent_sec,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "event_id": evt}


@router.post("/content/{content_id}/completed", status_code=202)
async def content_completed(content_id: str, user: dict = Depends(require_user)) -> dict:
    try:
        await lm.increment_completion(content_id)
        evt = await lm.log_event(user["user_id"], content_id, "completed")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "event_id": evt}


class ReportErrorIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=400)


@router.post("/content/{content_id}/reported-error", status_code=202)
async def content_reported_error(
    content_id: str, body: ReportErrorIn, user: dict = Depends(require_user)
) -> dict:
    """Registra o report do aluno (P0.3: rate-limited 1× por user+conteúdo).

    Rejeição idempotente: se o usuário já reportou este conteúdo, o endpoint
    responde 200 com `duplicate=True` (para o cliente não precisar tratar erro),
    e o contador global NÃO é incrementado — impedindo cache poisoning.
    """
    result = await lm.register_report_rate_limited(user["user_id"], content_id)
    if not result["accepted"]:
        if result["reason"] == "content_not_found":
            raise HTTPException(status_code=404, detail="content_memory not found")
        if result["reason"] == "already_reported":
            return {"ok": True, "duplicate": True, "reason": "already_reported"}
        raise HTTPException(status_code=400, detail=result["reason"] or "invalid")
    # Optional note é anexado ao meta do evento (não afeta o contador).
    if body.note:
        try:
            await lm.log_event(
                user["user_id"], content_id, "reported_error",
                meta={"note": body.note, "kind": "additional_note"},
            )
        except LookupError:
            pass
    return {"ok": True, "duplicate": False, "state": result["state"]}


@router.get("/me/mastery")
async def my_mastery(
    discipline: Optional[str] = None, user: dict = Depends(require_user)
) -> dict:
    return await lm.student_mastery(user["user_id"], discipline)


@router.get("/me/weakest")
async def my_weakest(
    discipline: Optional[str] = None, user: dict = Depends(require_user)
) -> dict:
    """Debug/instrumentação — motor consome internamente."""
    w = await lm.weakest_topic(user["user_id"], discipline)
    return {"weakest": w}
