"""Contadores diários de IA por estudante."""
from __future__ import annotations

import os
from datetime import timedelta

from fastapi import HTTPException
from pymongo import ReturnDocument

from core import _iso, _now, db


def limit_for(kind: str) -> int:
    names = {
        "tutor": "AI_TUTOR_DAILY_LIMIT",
        "feedback": "AI_FEEDBACK_DAILY_LIMIT",
    }
    name = names.get(kind)
    if name is None:
        raise ValueError(f"Tipo de uso de IA inválido: {kind}")
    return int(os.environ[name])


async def consume_preceptor_review(user_id: str, plan: str) -> dict:
    """Registra revisão premium; Free limita, Premium adapta após uso intenso."""
    plan = "premium" if plan == "premium" else "free"
    if plan == "free":
        usage = await consume_ai_quota(
            user_id,
            "preceptor_review",
            limit_override=1,
            label="revisão premium",
        )
        return {**usage, "plan": plan, "delivery_mode": "premium_review"}

    now = _now()
    query = {
        "user_id": user_id,
        "date": now.date().isoformat(),
        "kind": "preceptor_review",
    }
    await db.ai_usage.update_one(
        query,
        {"$setOnInsert": {**query, "count": 0, "created_at": _iso(now)}},
        upsert=True,
    )
    usage = await db.ai_usage.find_one_and_update(
        query,
        {"$inc": {"count": 1}, "$set": {"updated_at": _iso(now)}},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )
    quality_limit = int(os.environ["PREMIUM_FULL_REVIEW_QUALITY_LIMIT"])
    delivery_mode = "premium_review" if usage["count"] <= quality_limit else "smart_compact"
    return {**usage, "plan": plan, "delivery_mode": delivery_mode}


async def ensure_ai_quota_indexes() -> None:
    await db.ai_usage.create_index(
        [("user_id", 1), ("date", 1), ("kind", 1)],
        name="ai_usage_user_date_kind_unique",
        unique=True,
    )


async def consume_ai_quota(
    user_id: str,
    kind: str,
    limit_override: int | None = None,
    label: str | None = None,
) -> dict:
    """Reserva uma geração de IA de modo atômico ou responde com limite atingido."""
    limit = limit_override if limit_override is not None else limit_for(kind)
    now = _now()
    date = now.date().isoformat()
    query = {"user_id": user_id, "date": date, "kind": kind}
    await db.ai_usage.update_one(
        query,
        {
            "$setOnInsert": {
                "user_id": user_id,
                "date": date,
                "kind": kind,
                "count": 0,
                "created_at": _iso(now),
            }
        },
        upsert=True,
    )
    usage = await db.ai_usage.find_one_and_update(
        {**query, "count": {"$lt": limit}},
        {"$inc": {"count": 1}, "$set": {"updated_at": _iso(now)}},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )
    if usage is None:
        reset_at = (now + timedelta(days=1)).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        display_label = label or (
            "mensagens do Tutor" if kind == "tutor" else "gerações de plano e feedback"
        )
        raise HTTPException(
            status_code=429,
            detail={
                "message": f"Limite diário de {display_label} atingido.",
                "limit": limit,
                "reset_at": _iso(reset_at),
            },
        )
    return usage


async def has_ai_quota(user_id: str, kind: str) -> bool:
    """Informa se ainda há saldo diário sem consumir uma geração."""
    usage = await db.ai_usage.find_one(
        {"user_id": user_id, "date": _now().date().isoformat(), "kind": kind},
        {"_id": 0, "count": 1},
    )
    return int((usage or {}).get("count", 0)) < limit_for(kind)


async def release_ai_quota(user_id: str, kind: str) -> None:
    """Devolve uma reserva quando o provedor não entregou conteúdo utilizável."""
    await db.ai_usage.update_one(
        {
            "user_id": user_id,
            "date": _now().date().isoformat(),
            "kind": kind,
            "count": {"$gt": 0},
        },
        {"$inc": {"count": -1}, "$set": {"updated_at": _iso(_now())}},
    )


async def release_preceptor_review(user_id: str) -> None:
    await release_ai_quota(user_id, "preceptor_review")