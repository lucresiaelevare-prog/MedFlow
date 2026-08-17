"""Telemetry — captura de erros do frontend e painel admin agregado.

Filosofia (ver /app/docs/frontend-rules.md #7):
- Endpoint público sem auth obrigatória (queremos capturar erros da Landing também).
- Fire-and-forget do cliente: sempre 202, sem processamento pesado.
- Painel admin agrega Top 20 erros dos últimos 7 dias.

Coleções MongoDB:
- `frontend_errors`: cada evento individual (com TTL de 60 dias via app-side cleanup).
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import _iso, _now, db, require_user

logger = logging.getLogger("medflow.telemetry")
router = APIRouter(prefix="/api", tags=["telemetry"])


# ─── Ingest ─────────────────────────────────────────────────────
class ErrorEventIn(BaseModel):
    component: str = Field(min_length=1, max_length=80)
    route: str = Field(default="", max_length=200)
    message: str = Field(default="", max_length=1000)
    stack: str = Field(default="", max_length=4000)
    component_stack: str = Field(default="", max_length=2000)
    user_agent: str = Field(default="", max_length=500)
    react_version: str = Field(default="", max_length=32)
    timestamp: str = Field(default="", max_length=64)
    user_reported: bool = Field(default=False)


@router.post("/telemetry/error", status_code=202)
async def ingest_error(
    body: ErrorEventIn,
    request: Request,
    session_token: Optional[str] = Cookie(default=None),
) -> dict:
    """Recebe erro do frontend. Sem auth obrigatória — Landing precisa reportar também."""
    user_id: Optional[str] = None
    if session_token:
        session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0, "user_id": 1})
        if session:
            user_id = session.get("user_id")

    doc = {
        "id": f"err_{uuid.uuid4().hex[:16]}",
        "user_id": user_id,
        "component": body.component,
        "route": body.route,
        "message": body.message,
        "stack": body.stack,
        "component_stack": body.component_stack,
        "user_agent": body.user_agent,
        "react_version": body.react_version,
        "client_timestamp": body.timestamp,
        "server_timestamp": _iso(_now()),
        "ip": (request.client.host if request.client else None),
        "user_reported": body.user_reported,
    }
    try:
        await db.frontend_errors.insert_one(doc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to persist frontend error: %s", exc)
    return {"ok": True}


# ─── Admin panel (auth-guarded) ──────────────────────────────────
async def _require_admin(user: dict = Depends(require_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="admin only")
    return user


@router.get("/admin/telemetry/errors")
async def admin_errors_summary(
    days: int = 7,
    _admin: dict = Depends(_require_admin),
) -> dict:
    """Top erros agregados + últimos eventos brutos."""
    since = (_now() - timedelta(days=max(1, min(days, 90)))).isoformat()

    # Top 20 mensagens agregadas
    pipeline = [
        {"$match": {"server_timestamp": {"$gte": since}}},
        {"$group": {
            "_id": {"component": "$component", "message": "$message"},
            "count": {"$sum": 1},
            "users_affected": {"$addToSet": "$user_id"},
            "routes": {"$addToSet": "$route"},
            "last_seen": {"$max": "$server_timestamp"},
        }},
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]
    top: list[dict] = []
    async for row in db.frontend_errors.aggregate(pipeline):
        users = [u for u in row.get("users_affected", []) if u]
        top.append({
            "component": row["_id"]["component"],
            "message": row["_id"]["message"] or "(vazio)",
            "count": row["count"],
            "users_affected": len(users),
            "routes": [r for r in row.get("routes", []) if r][:5],
            "last_seen": row.get("last_seen"),
        })

    # Últimos 50 eventos crus
    recent: list[dict] = []
    async for row in db.frontend_errors.find(
        {"server_timestamp": {"$gte": since}}, {"_id": 0}
    ).sort("server_timestamp", -1).limit(50):
        recent.append(row)

    total = await db.frontend_errors.count_documents({"server_timestamp": {"$gte": since}})
    return {"since": since, "days": days, "total": total, "top": top, "recent": recent}
