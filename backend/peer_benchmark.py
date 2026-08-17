"""Peer benchmark — comparação anônima com alunos do mesmo período.

Filosofia (validada com PO):
    Sem ranking. Sem competição. Apenas contexto.
    Você estudou 1h40 hoje.
    Alunos do mesmo período estudaram em média 1h15.

Anonimização por generalização (LGPD-honest):
    - Períodos agrupados em buckets grandes (basico 1-2, clinico 3-6, internato 7-10).
    - Sample mínimo (peers >= 5) para retornar comparação.
    - Só agregados (mediana). Nunca identifica outros usuários.
    - Exclui o próprio usuário do cálculo dos peers.
    - Usuário sem período declarado → available=False.
"""
from __future__ import annotations

from datetime import timedelta
from statistics import median
from typing import Optional

from core import _now, _today_str, db
from learning_memory import _period_bucket

MIN_PEER_SAMPLE = 5

BUCKET_LABEL = {
    "basico": "Ciclo básico (1º–2º período)",
    "clinico": "Ciclo clínico (3º–6º período)",
    "internato": "Internato (7º–10º período)",
    "outros": "Outros períodos",
    "unspecified": "Sem período declarado",
}


def _profile_bucket(profile: dict) -> str:
    """Extrai o bucket do usuário a partir de semester ou period_number."""
    if not profile:
        return "unspecified"
    p = profile.get("semester") or profile.get("period_number")
    return _period_bucket(p)


async def _peers_in_bucket(bucket: str, exclude_user_id: str) -> list[str]:
    """IDs de peers no mesmo bucket, excluindo o próprio usuário."""
    if bucket == "unspecified":
        return []
    # Encontra todos os user_profiles cujo semester/period_number cai no bucket.
    # Como o bucket é calculado, não podemos filtrar no Mongo diretamente.
    # Lê profiles enxutos e filtra em Python.
    peers: list[str] = []
    async for prof in db.user_profiles.find(
        {"user_id": {"$ne": exclude_user_id}},
        {"_id": 0, "user_id": 1, "semester": 1, "period_number": 1},
    ):
        p = prof.get("semester") or prof.get("period_number")
        if _period_bucket(p) == bucket:
            peers.append(prof["user_id"])
    return peers


async def _user_focus_min_today(user_id: str, today_iso: str) -> int:
    """Total de minutos focados hoje (pomodoro completed)."""
    total = 0
    async for s in db.pomodoro_sessions.find(
        {"user_id": user_id, "status": "completed",
         "created_at": {"$regex": f"^{today_iso}"}},
        {"_id": 0, "focused_minutes": 1},
    ):
        total += int(s.get("focused_minutes") or 0)
    return total


async def _user_focus_min_week(user_id: str, since_iso: str) -> int:
    """Total de minutos focados nos últimos 7 dias."""
    total = 0
    async for s in db.pomodoro_sessions.find(
        {"user_id": user_id, "status": "completed",
         "created_at": {"$gte": since_iso}},
        {"_id": 0, "focused_minutes": 1},
    ):
        total += int(s.get("focused_minutes") or 0)
    return total


async def _peers_focus_stats(peer_ids: list[str], today_iso: str, since_iso: str) -> dict:
    """Agregados dos peers via pipeline: total_today e total_week por peer.

    Sem sample_size gate aqui — quem decide é o caller.
    """
    if not peer_ids:
        return {"today_totals": [], "week_totals": [], "active_peers": 0}

    # Um único pipeline: soma today + week por peer
    pipe = [
        {"$match": {
            "user_id": {"$in": peer_ids},
            "status": "completed",
            "created_at": {"$gte": since_iso},
        }},
        {"$group": {
            "_id": "$user_id",
            "week_total": {"$sum": "$focused_minutes"},
            "today_total": {
                "$sum": {"$cond": [
                    {"$regexMatch": {"input": "$created_at", "regex": f"^{today_iso}"}},
                    "$focused_minutes",
                    0,
                ]},
            },
        }},
    ]
    today_totals: list[int] = []
    week_totals: list[int] = []
    active_peers = 0
    async for row in db.pomodoro_sessions.aggregate(pipe):
        active_peers += 1
        week_totals.append(int(row.get("week_total") or 0))
        today_totals.append(int(row.get("today_total") or 0))
    return {
        "today_totals": today_totals,
        "week_totals": week_totals,
        "active_peers": active_peers,
    }


def _fmt(min_val: int) -> str:
    """Formata minutos como '1h40' ou '35 min'."""
    m = int(min_val or 0)
    if m < 60:
        return f"{m} min"
    return f"{m // 60}h{m % 60:02d}"


async def compute(user_id: str, profile: dict) -> dict:
    """Endpoint-ready payload. Sempre retorna com `available`.

    Retornos possíveis:
      - {available: False, reason: 'no_period'}      → usuário não declarou período
      - {available: False, reason: 'insufficient_peers', bucket, sample_size}
      - {available: True, bucket, bucket_label, sample_size, today: {...}, week: {...}}
    """
    bucket = _profile_bucket(profile)
    if bucket == "unspecified":
        return {"available": False, "reason": "no_period"}

    today_iso = _today_str()
    since_iso = (_now() - timedelta(days=7)).isoformat()

    peer_ids = await _peers_in_bucket(bucket, exclude_user_id=user_id)
    peer_stats = await _peers_focus_stats(peer_ids, today_iso, since_iso)
    sample = peer_stats["active_peers"]

    if sample < MIN_PEER_SAMPLE:
        return {
            "available": False,
            "reason": "insufficient_peers",
            "bucket": bucket,
            "bucket_label": BUCKET_LABEL.get(bucket, bucket),
            "sample_size": sample,
            "min_sample": MIN_PEER_SAMPLE,
        }

    # Métricas do próprio usuário
    you_today = await _user_focus_min_today(user_id, today_iso)
    you_week = await _user_focus_min_week(user_id, since_iso)
    you_week_avg = you_week // 7

    peer_today_med = int(median(peer_stats["today_totals"])) if peer_stats["today_totals"] else 0
    peer_week_med_avg = int(median(peer_stats["week_totals"])) // 7 if peer_stats["week_totals"] else 0

    return {
        "available": True,
        "bucket": bucket,
        "bucket_label": BUCKET_LABEL.get(bucket, bucket),
        "sample_size": sample,
        "today": {
            "you_min": you_today,
            "you_fmt": _fmt(you_today),
            "peer_median_min": peer_today_med,
            "peer_median_fmt": _fmt(peer_today_med),
        },
        "week": {
            "you_avg_min": you_week_avg,
            "you_avg_fmt": _fmt(you_week_avg),
            "peer_median_avg_min": peer_week_med_avg,
            "peer_median_avg_fmt": _fmt(peer_week_med_avg),
        },
    }
