"""Reschedule routes — reorganização automática (fadiga/saturação).

Consome `reschedule_engine`. Todas as rotas exigem autenticação.

GET  /api/agenda/reschedule/today       → estado atual (pending/accepted/none)
POST /api/agenda/reschedule/preview     → gera pending (idempotente por dia)
POST /api/agenda/reschedule/{id}/apply  → materializa
POST /api/agenda/reschedule/{id}/dismiss → descarta
POST /api/agenda/reschedule/{id}/undo   → desfaz (após apply)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

import reschedule_engine as re_engine
from core import require_user

router = APIRouter(prefix="/api/agenda/reschedule", tags=["reschedule"])


@router.get("/today")
async def today(user: dict = Depends(require_user)) -> dict:
    doc = await re_engine.get_today_reschedule(user["user_id"])
    return {"reschedule": doc}


@router.post("/preview")
async def preview(user: dict = Depends(require_user)) -> dict:
    """Cria (ou retorna existente) a proposta pending para hoje.

    Se não houver motivo (nem saturação nem fadiga), retorna
    {needed: False} sem persistir nada.
    """
    proposal = await re_engine.build_proposal(user["user_id"])
    if not proposal.get("needed"):
        return {"needed": False, "reschedule": None, "reason": proposal.get("reason")}

    saved = await re_engine.save_pending(user["user_id"], proposal)
    return {"needed": True, "reschedule": saved}


@router.post("/{resch_id}/apply", status_code=202)
async def apply(resch_id: str, user: dict = Depends(require_user)) -> dict:
    try:
        doc = await re_engine.apply(user["user_id"], resch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "reschedule": doc}


@router.post("/{resch_id}/dismiss", status_code=202)
async def dismiss(resch_id: str, user: dict = Depends(require_user)) -> dict:
    try:
        doc = await re_engine.dismiss(user["user_id"], resch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "reschedule": doc}


@router.post("/{resch_id}/undo", status_code=202)
async def undo(resch_id: str, user: dict = Depends(require_user)) -> dict:
    try:
        doc = await re_engine.undo(user["user_id"], resch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "reschedule": doc}
