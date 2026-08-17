"""Cache L2 — evidências científicas (PubMed + OpenAlex).

TTL longo (30 dias) porque literatura clássica raramente muda.
Chave: sha256(source + query_normalized + limit).
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from core import db

_TTL_DAYS = 30


def _norm_query(q: str) -> str:
    return re.sub(r"\s+", " ", (q or "").strip().lower())


def _key(source: str, query: str, limit: int) -> str:
    blob = f"{source}::{_norm_query(query)}::{limit}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


async def get(source: str, query: str, limit: int) -> Optional[list[dict]]:
    doc = await db.evidence_cache.find_one({"key": _key(source, query, limit)}, {"_id": 0})
    if not doc:
        return None
    # Verifica TTL
    try:
        cached_at = datetime.fromisoformat(doc["cached_at"].replace("Z", "+00:00"))
    except Exception:
        return None
    if datetime.now(timezone.utc) - cached_at > timedelta(days=_TTL_DAYS):
        return None
    return doc.get("items") or []


async def put(source: str, query: str, limit: int, items: list[dict]) -> None:
    await db.evidence_cache.update_one(
        {"key": _key(source, query, limit)},
        {"$set": {
            "key": _key(source, query, limit),
            "source": source,
            "query_norm": _norm_query(query),
            "limit": limit,
            "items": items,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
