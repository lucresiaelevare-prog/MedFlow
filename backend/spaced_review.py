"""MedFlow — Spaced Review (curva de esquecimento individual).

Diferencial estratégico: revisão espaçada POR ALUNO POR CONTEÚDO. Não é
SuperMemo genérico — o intervalo é calculado sobre o histórico específico
de cada estudante em cada `content_memory` doc.

Filosofia:
    Ver → responder → esquecer → revisar → consolidar.
Cada `answered` recalcula quando aquele conteúdo deve reaparecer.
Não invade o motor: só sugere quando existe uma pilha de revisões vencidas.

Algoritmo (SM-2 simplificado, sem `ease factor` global):
    interval_days = 1 se última resposta foi errada
    interval_days = interval_prev * multiplier caso contrário
    multiplier = 2.5 se acerto rápido (time_spent < 15s), 2.0 padrão, 1.5 se lento (>60s)
    max interval = 60 dias (nenhum item some para sempre)

Coleção: `student_review_schedule`
    { user_id, content_id, last_answered_at, last_correct, interval_days,
      next_review_at, review_count }
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from core import _iso, _now, db

# ─── Tipos de conteúdo elegíveis para SRS ────────────────────
SRS_KINDS = {"question", "flashcard"}

MAX_INTERVAL_DAYS = 60
MIN_INTERVAL_DAYS = 1


def _multiplier(time_spent_sec: Optional[int]) -> float:
    """Multiplicador de intervalo baseado no esforço observado.

    Acerto rápido (< 15s) → item bem consolidado, multiplica agressivamente.
    Acerto lento (> 60s) → titubeou, próxima revisão mais cedo.
    """
    if time_spent_sec is None:
        return 2.0
    if time_spent_sec < 15:
        return 2.5
    if time_spent_sec > 60:
        return 1.5
    return 2.0


def compute_next_interval(
    prev_interval_days: int,
    correct: bool,
    time_spent_sec: Optional[int] = None,
) -> int:
    """Devolve o intervalo (dias) até a próxima revisão.

    Regras:
    - Erro → volta para 1 dia (sempre reeaprender do início).
    - Acerto → prev * multiplier, cap em MAX_INTERVAL_DAYS.
    - Primeira exposição (prev=0) e acerto → 3 dias.
    """
    if not correct:
        return MIN_INTERVAL_DAYS
    if prev_interval_days <= 0:
        return 3
    m = _multiplier(time_spent_sec)
    nxt = int(round(prev_interval_days * m))
    return max(MIN_INTERVAL_DAYS, min(nxt, MAX_INTERVAL_DAYS))


async def register_review(
    user_id: str,
    content_id: str,
    correct: bool,
    time_spent_sec: Optional[int] = None,
) -> dict:
    """Atualiza o schedule após uma resposta. Idempotente-friendly.

    Só age em conteúdos elegíveis (kind ∈ SRS_KINDS). Retorna o novo
    schedule (útil para telemetria). Se o content não existe ou não é
    elegível, devolve {"skipped": True, "reason": ...}.
    """
    content = await db.content_memory.find_one(
        {"id": content_id}, {"_id": 0, "kind": 1}
    )
    if not content:
        return {"skipped": True, "reason": "content_not_found"}
    if content.get("kind") not in SRS_KINDS:
        return {"skipped": True, "reason": "kind_not_eligible"}

    now = _now()
    existing = await db.student_review_schedule.find_one(
        {"user_id": user_id, "content_id": content_id}, {"_id": 0}
    )
    prev_interval = int((existing or {}).get("interval_days") or 0)
    review_count = int((existing or {}).get("review_count") or 0)

    new_interval = compute_next_interval(prev_interval, correct, time_spent_sec)
    next_review_at = now + timedelta(days=new_interval)

    doc = {
        "user_id": user_id,
        "content_id": content_id,
        "last_answered_at": _iso(now),
        "last_correct": bool(correct),
        "interval_days": new_interval,
        "next_review_at": _iso(next_review_at),
        "review_count": review_count + 1,
    }
    await db.student_review_schedule.update_one(
        {"user_id": user_id, "content_id": content_id},
        {"$set": doc}, upsert=True,
    )
    return doc


async def due_count(user_id: str) -> int:
    """Quantos itens estão vencidos AGORA para este aluno."""
    return await db.student_review_schedule.count_documents({
        "user_id": user_id, "next_review_at": {"$lte": _iso(_now())},
    })


async def get_due(user_id: str, limit: int = 20) -> list[dict]:
    """Lista de conteúdos com revisão vencida — mais atrasados primeiro.

    Enriquece cada item com o `payload` de `content_memory` para o cliente
    renderizar direto (sem round-trip extra).
    """
    now_iso = _iso(_now())
    items: list[dict] = []
    async for row in db.student_review_schedule.find(
        {"user_id": user_id, "next_review_at": {"$lte": now_iso}},
        {"_id": 0},
    ).sort("next_review_at", 1).limit(limit):
        content = await db.content_memory.find_one(
            {"id": row["content_id"]},
            {
                "_id": 0, "id": 1, "kind": 1, "payload": 1,
                "discipline_label": 1, "topic_label": 1, "subtopic_label": 1,
            },
        )
        if not content:
            continue
        items.append({
            "content_id": row["content_id"],
            "kind": content["kind"],
            "discipline": content.get("discipline_label"),
            "topic": content.get("topic_label"),
            "subtopic": content.get("subtopic_label") or None,
            "payload": content.get("payload"),
            "interval_days": row["interval_days"],
            "review_count": row["review_count"],
            "next_review_at": row["next_review_at"],
            "overdue_days": max(
                0, (_now() - _now().fromisoformat(row["next_review_at"].replace("Z", "+00:00"))).days
            ) if "T" in row["next_review_at"] else 0,
        })
    return items
