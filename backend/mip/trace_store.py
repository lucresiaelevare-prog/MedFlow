"""Trace mínimo e pseudonimizado da Fase 1 do MIP/PIE."""
from __future__ import annotations

import hashlib
import json
import uuid

from core import _iso, _now, db, logger
from mip.config import phase1_shadow_write_enabled
from mip.contracts import MIPTrace, TraceRequest


def create_trace(request_text: str, safety_pre, safety_post=None) -> MIPTrace:
    digest = hashlib.sha256(request_text.encode("utf-8")).hexdigest()
    return MIPTrace(
        trace_id=f"mip_{uuid.uuid4().hex}",
        request=TraceRequest(input_hash=digest, input_length=len(request_text)),
        safety_pre=safety_pre,
        safety_post=safety_post,
        created_at=_iso(_now()),
    )


async def ensure_shadow_indexes() -> None:
    if not phase1_shadow_write_enabled():
        return
    await db.mip_phase1_traces.create_index("trace_id", unique=True)
    await db.mip_phase1_traces.create_index("created_at")


async def persist_shadow_trace(trace: MIPTrace) -> bool:
    """Escreve somente na coleção nova quando o shadow-write estiver habilitado."""
    logger.info("mip_phase1_trace=%s", json.dumps(trace.model_dump(), ensure_ascii=False))
    if not phase1_shadow_write_enabled():
        return False
    await db.mip_phase1_traces.insert_one(trace.model_dump())
    return True