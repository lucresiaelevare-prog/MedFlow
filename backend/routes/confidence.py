"""Coleta passiva de confiança do aluno, isolada de recomendações e planos."""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from core import _iso, _now, db, require_user

router = APIRouter(prefix="/api/learning", tags=["confidence-shadow"])


class ConfidenceIn(BaseModel):
    context_id: str = Field(min_length=3, max_length=120)
    context_type: str = Field(pattern="^(smart_review|question|simulation)$")
    confidence_level: int = Field(ge=1, le=5)
    idempotency_key: str = Field(pattern="^[A-Za-z0-9_-]{8,80}$")


def _idempotency_hash(user_id: str, key: str) -> str:
    return hashlib.sha256(f"{user_id}:{key}".encode("utf-8")).hexdigest()


async def ensure_confidence_indexes() -> None:
    await db.confidence_shadow_events.create_index("idempotency_hash", unique=True)
    await db.confidence_shadow_events.create_index([("user_id", 1), ("created_at", -1)])


@router.post("/confidence", status_code=202)
async def record_confidence(payload: ConfidenceIn, user: dict = Depends(require_user)) -> dict:
    """Armazena percepção do aluno sem alterar prioridade, plano ou revisão."""
    review = None
    if payload.context_type == "smart_review":
        review = await db.smart_reviews.find_one(
            {"id": payload.context_id, "user_id": user["user_id"]},
            {"_id": 0, "discipline": 1, "topic": 1, "is_correct": 1, "time_spent_sec": 1},
        )
        if review is None:
            raise HTTPException(status_code=404, detail="Devolutiva não encontrada")
    hashed = _idempotency_hash(user["user_id"], payload.idempotency_key)
    event = {
        "event_id": f"conf_{hashed[:24]}",
        "idempotency_hash": hashed,
        "user_id": user["user_id"],
        "context_id": payload.context_id,
        "context_type": payload.context_type,
        "confidence_level": payload.confidence_level,
        "discipline": (review or {}).get("discipline"),
        "topic": (review or {}).get("topic"),
        "answer_outcome": (review or {}).get("is_correct"),
        "time_spent_sec": (review or {}).get("time_spent_sec"),
        "shadow_mode": True,
        "created_at": _iso(_now()),
    }
    try:
        await db.confidence_shadow_events.insert_one(event)
        duplicate = False
    except DuplicateKeyError:
        duplicate = True
    return {
        "event_id": event["event_id"],
        "accepted": True,
        "duplicate": duplicate,
        "applied_to_recommendations": False,
        "shadow_mode": True,
    }