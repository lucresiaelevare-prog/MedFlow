"""Resume checkpoints — "Continuar de onde parei".

Uma única checkpoint ativa por usuário. Expira após 24h de inatividade.
Escrita a partir das telas de execução (Pomodoro, Tutor, etc.) via
`POST /api/resume/save`. Lida por /hoje via `GET /api/resume/state`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core import _iso, _now, db, require_user

router = APIRouter(prefix="/api", tags=["resume"])

STALE_HOURS = 24


class CheckpointIn(BaseModel):
    kind: str = Field(..., description="pomodoro | tutor | flashcards | questions | simulado | resumo | revisao")
    title: str
    subtitle: Optional[str] = None
    route: str
    meta: Optional[dict] = None


@router.post("/resume/save")
async def save_resume(payload: CheckpointIn, user: dict = Depends(require_user)) -> dict:
    await db.resume_checkpoints.update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "user_id":   user["user_id"],
            "kind":      payload.kind,
            "title":     payload.title,
            "subtitle":  payload.subtitle,
            "route":     payload.route,
            "meta":      payload.meta or {},
            "updated_at": _iso(_now()),
        }},
        upsert=True,
    )
    return {"ok": True}


@router.get("/resume/state")
async def get_resume(user: dict = Depends(require_user)) -> dict:
    doc = await db.resume_checkpoints.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        return {"resume": None}
    try:
        dt = datetime.fromisoformat(doc["updated_at"].replace("Z", "+00:00"))
    except Exception:
        return {"resume": None}
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if _now() - dt > timedelta(hours=STALE_HOURS):
        return {"resume": None}
    return {"resume": doc}


@router.post("/resume/clear")
async def clear_resume(user: dict = Depends(require_user)) -> dict:
    await db.resume_checkpoints.delete_one({"user_id": user["user_id"]})
    return {"ok": True}
