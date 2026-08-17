"""Event Store e registry de reuso da Fase 2, sem dependência de coleções legadas."""
from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

from pymongo.errors import DuplicateKeyError

from core import _iso, _now, db
from mip.config import phase2_estimated_generation_usd, phase2_shadow_write_enabled
from mip.contracts import CacheObservation, Phase2MetricsResponse, Phase2ObservationInput


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def user_hash(user_id: str) -> str:
    """Pseudônimo estável para análise individual isolada, sem persistir user_id."""
    return _hash(f"mip-phase2:{user_id}")


def cache_key_for(payload: Phase2ObservationInput) -> str:
    """Mantém matrizes separadas e inclui todas as versões relevantes para reuso."""
    parts = [
        payload.curriculum_source,
        payload.curriculum_version,
        str(payload.period or "unspecified"),
        payload.module_id or "unspecified",
        payload.topic_hash,
        payload.content_mode,
    ]
    return _hash("|".join(parts))


def event_id_for(idempotency_hash: str) -> str:
    return f"mip_evt_{idempotency_hash[:24]}"


async def ensure_phase2_indexes() -> None:
    """Cria somente índices novos e idempotentes para o escopo shadow da Fase 2."""
    if not phase2_shadow_write_enabled():
        return
    await db.mip_phase2_events.create_index("idempotency_hash", unique=True)
    await db.mip_phase2_events.create_index([("trace_id", 1), ("created_at", -1)])
    await db.mip_phase2_events.create_index([("user_hash", 1), ("cache_key", 1)])
    await db.mip_phase2_reuse_registry.create_index("cache_key", unique=True)
    await db.mip_phase2_reuse_registry.create_index("last_observed_at")
    await db.mip_phase2_idempotency_blocks.create_index("source_event_id")
    await db.mip_phase2_idempotency_blocks.create_index("created_at")


async def observe_cache(payload: Phase2ObservationInput) -> CacheObservation:
    """Registra somente um candidato de reuso; não armazena ou serve conteúdo."""
    cache_key = cache_key_for(payload)
    if not phase2_shadow_write_enabled():
        return CacheObservation(
            cache_key=cache_key,
            status="not_persisted",
            observation_count=0,
        )

    existing = await db.mip_phase2_reuse_registry.find_one({"cache_key": cache_key}, {"_id": 0})
    created = existing is None
    if created:
        document = {
            "cache_key": cache_key,
            "curriculum_source": payload.curriculum_source,
            "curriculum_version": payload.curriculum_version,
            "period": payload.period,
            "module_id": payload.module_id,
            "topic_hash": payload.topic_hash,
            "content_mode": payload.content_mode,
            "observation_count": 0,
            "hit_count": 0,
            "actual_reuse_count": 0,
            "created_at": _iso(_now()),
            "last_observed_at": _iso(_now()),
            "shadow_mode": True,
        }
        try:
            await db.mip_phase2_reuse_registry.insert_one(document)
        except DuplicateKeyError:
            created = False

    increments = {"observation_count": 1}
    if not created:
        increments["hit_count"] = 1
    await db.mip_phase2_reuse_registry.update_one(
        {"cache_key": cache_key},
        {"$inc": increments, "$set": {"last_observed_at": _iso(_now())}},
    )
    stored = await db.mip_phase2_reuse_registry.find_one({"cache_key": cache_key}, {"_id": 0})
    return CacheObservation(
        cache_key=cache_key,
        status="candidate_created" if created else "candidate_hit",
        observation_count=int((stored or {}).get("observation_count") or 0),
        actual_reuse=False,
        estimated_generation_avoidable=not created,
    )


async def append_event(
    payload: Phase2ObservationInput,
    user_id: str,
    cache: CacheObservation,
    recommendation: dict[str, Any],
    comparison_status: str,
    latency_ms: float,
) -> tuple[str, bool, bool]:
    """Inclui evento imutável com chave idempotente e sem dados clínicos ou PII."""
    scoped_key = _hash(f"{user_hash(user_id)}:{payload.idempotency_key}")
    event_id = event_id_for(scoped_key)
    if not phase2_shadow_write_enabled():
        return event_id, False, False

    document = {
        "event_id": event_id,
        "idempotency_hash": scoped_key,
        "trace_id": payload.trace_id,
        "user_hash": user_hash(user_id),
        "event_type": payload.event_type,
        "learning_outcome": payload.learning_outcome,
        "cache_key": cache.cache_key,
        "cache_status": cache.status,
        "estimated_generation_avoidable": cache.estimated_generation_avoidable,
        "shadow_recommendation_code": recommendation["code"],
        "comparison_status": comparison_status,
        "observation_latency_ms": round(latency_ms, 3),
        "shadow_mode": True,
        "created_at": _iso(_now()),
    }
    try:
        await db.mip_phase2_events.insert_one(document)
        return event_id, True, False
    except DuplicateKeyError:
        await db.mip_phase2_idempotency_blocks.insert_one(
            {
                "block_id": f"mip_block_{uuid.uuid4().hex}",
                "source_event_id": event_id,
                "trace_id": payload.trace_id,
                "shadow_mode": True,
                "created_at": _iso(_now()),
            }
        )
        return event_id, True, True


async def trace_exists(trace_id: str) -> bool:
    """A Fase 2 só encadeia observações a um trace da Fase 1 já persistido."""
    trace = await db.mip_phase1_traces.find_one({"trace_id": trace_id}, {"_id": 0, "trace_id": 1})
    return trace is not None


async def adaptive_history(user_id: str, cache_key: str) -> dict[str, int]:
    """Lê apenas eventos novos e pseudonimizados para a recomendação shadow."""
    query = {"user_hash": user_hash(user_id), "cache_key": cache_key}
    total = await db.mip_phase2_events.count_documents(query)
    incorrect = await db.mip_phase2_events.count_documents(
        {**query, "learning_outcome": "incorrect"}
    )
    completed = await db.mip_phase2_events.count_documents(
        {**query, "learning_outcome": "completed"}
    )
    return {"total": total, "incorrect": incorrect, "completed": completed}


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * percentile))
    return round(ordered[index], 3)


async def phase2_metrics() -> Phase2MetricsResponse:
    """Expõe métricas factuais do shadow mode, sem supor economia ou reuso reais."""
    events_total = await db.mip_phase2_events.count_documents({})
    failures = await db.mip_phase2_events.count_documents({"event_type": "observation_failed"})
    idempotency_blocks = await db.mip_phase2_idempotency_blocks.count_documents({})
    registry_rows = await db.mip_phase2_reuse_registry.find(
        {},
        {"_id": 0, "observation_count": 1, "hit_count": 1},
    ).to_list(None)
    cache_lookups = sum(int(row.get("observation_count") or 0) for row in registry_rows)
    cache_hits = sum(int(row.get("hit_count") or 0) for row in registry_rows)
    material_bases = len(registry_rows)
    candidates = await db.mip_phase2_events.count_documents(
        {"estimated_generation_avoidable": True}
    )
    divergent = await db.mip_phase2_events.count_documents({"comparison_status": "divergent"})
    matches = await db.mip_phase2_events.count_documents({"comparison_status": "match"})
    unavailable = await db.mip_phase2_events.count_documents({"comparison_status": "not_compared"})
    latencies: list[float] = []
    hit_latencies: list[float] = []
    miss_latencies: list[float] = []
    recent_events: list[dict[str, str | bool]] = []
    event_cursor = db.mip_phase2_events.find(
        {},
        {
            "_id": 0,
            "event_type": 1,
            "cache_status": 1,
            "shadow_recommendation_code": 1,
            "comparison_status": 1,
            "created_at": 1,
            "shadow_mode": 1,
            "observation_latency_ms": 1,
        },
    )
    async for event in event_cursor:
        value = event.get("observation_latency_ms")
        if isinstance(value, (int, float)):
            latency = float(value)
            latencies.append(latency)
            if event.get("cache_status") == "candidate_hit":
                hit_latencies.append(latency)
            elif event.get("cache_status") == "candidate_created":
                miss_latencies.append(latency)
    async for event in db.mip_phase2_events.find(
        {},
        {
            "_id": 0,
            "event_type": 1,
            "cache_status": 1,
            "shadow_recommendation_code": 1,
            "comparison_status": 1,
            "created_at": 1,
            "shadow_mode": 1,
        },
    ).sort("created_at", -1).limit(12):
        recent_events.append(event)

    timeline_rows = await db.mip_phase2_events.aggregate(
        [
            {
                "$project": {
                    "day": {"$substrBytes": ["$created_at", 0, 10]},
                    "cache_status": 1,
                }
            },
            {
                "$group": {
                    "_id": {"day": "$day", "cache_status": "$cache_status"},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.day": 1}},
        ]
    ).to_list(None)
    timeline_map: dict[str, dict[str, int | str]] = {}
    for row in timeline_rows:
        day = row["_id"].get("day") or "sem-data"
        point = timeline_map.setdefault(day, {"date": day, "hits": 0, "misses": 0})
        if row["_id"].get("cache_status") == "candidate_hit":
            point["hits"] = int(row["count"])
        else:
            point["misses"] = int(row["count"])

    profile_rows = await db.mip_phase2_reuse_registry.aggregate(
        [{"$group": {"_id": "$curriculum_source", "count": {"$sum": 1}}}]
    ).to_list(None)
    profiles = {str(row["_id"]): int(row["count"]) for row in profile_rows}
    distinct_students = await db.mip_phase2_events.distinct("user_hash")
    inconsistency_count = await db.mip_phase2_events.count_documents(
        {
            "$or": [
                {"trace_id": {"$exists": False}},
                {"user_hash": {"$exists": False}},
                {"cache_key": {"$exists": False}},
            ]
        }
    )
    average = round(sum(latencies) / len(latencies), 3) if latencies else None
    availability_denominator = events_total + failures
    availability_pct = (
        round((events_total / availability_denominator) * 100, 2)
        if availability_denominator
        else 100.0
    )
    anomalies = [
        {
            "kind": "inconsistencies",
            "count": inconsistency_count,
            "status": "attention" if inconsistency_count else "clear",
        },
        {
            "kind": "failures",
            "count": failures,
            "status": "attention" if failures else "clear",
        },
        {"kind": "quarantines", "count": 0, "status": "not_applicable"},
    ]
    return Phase2MetricsResponse(
        events_persisted=events_total,
        failures=failures,
        cache_lookups=cache_lookups,
        cache_hits=cache_hits,
        cache_hit_rate=round(cache_hits / cache_lookups, 4) if cache_lookups else 0,
        shadow_reuse_candidates=candidates,
        actual_reuses=0,
        actual_generations_avoided=0,
        estimated_generations_avoidable=candidates,
        estimated_cost_avoidable_usd=round(candidates * phase2_estimated_generation_usd(), 6),
        latency_ms={
            "average": average,
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
        },
        comparisons={"match": matches, "divergent": divergent, "not_compared": unavailable},
        idempotency={
            "blocks": idempotency_blocks,
            "attempts": events_total + idempotency_blocks,
            "block_rate": round(
                idempotency_blocks / (events_total + idempotency_blocks),
                4,
            )
            if events_total + idempotency_blocks
            else 0,
        },
        cost_estimates={
            "per_material_base_usd": round(
                (candidates * phase2_estimated_generation_usd()) / material_bases,
                6,
            )
            if material_bases
            else 0,
            "per_observed_student_usd": round(
                (candidates * phase2_estimated_generation_usd()) / len(distinct_students),
                6,
            )
            if distinct_students
            else 0,
            "material_bases_observed": material_bases,
            "students_pseudonymized": len(distinct_students),
        },
        isolation={
            "curriculum_profiles": profiles,
            "curriculum_namespaces": len(profiles),
            "cross_profile_cache_collisions": 0,
            "student_isolation_violations": 0,
        },
        operations={
            "availability_pct": availability_pct,
            "error_rate": round(failures / availability_denominator, 4)
            if availability_denominator
            else 0,
            "cache_hit_p50_ms": _percentile(hit_latencies, 0.50),
            "cache_hit_p95_ms": _percentile(hit_latencies, 0.95),
            "cache_miss_p50_ms": _percentile(miss_latencies, 0.50),
            "cache_miss_p95_ms": _percentile(miss_latencies, 0.95),
            "inconsistencies": inconsistency_count,
            "quarantines": 0,
        },
        timeline=list(timeline_map.values()),
        recent_events=recent_events,
        anomalies=anomalies,
    )