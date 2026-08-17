"""Pomodoro adaptativo ancorado à agenda.

- Cada sessão pode estar vinculada a um bloco da agenda (`block_id`) e/ou a uma matéria.
- A configuração (duração de bloco, pausa, ciclos) é derivada do PERFIL do aluno,
  reaproveitando a mesma lógica dos study strategies (TDAH → 25/5, TEA → 45/10,
  ultradian → 90/20, flow → 60/15, pomodoro/livre → 50/10).
- Fluxo:
    1) `POST /api/pomodoro/start`  → cria sessão em memória do usuário.
    2) `POST /api/pomodoro/{id}/complete` — marca sessão finalizada.
    3) `POST /api/pomodoro/{id}/skip` — abandona a sessão sem contar tempo.
    4) `GET /api/pomodoro/today` — traz config + sessões do dia + total.
    5) `GET /api/pomodoro/config` — só a config adaptativa (para preview).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import _iso, _now, db, require_user
from routes.profile import get_profile_doc


router = APIRouter(prefix="/api/pomodoro", tags=["pomodoro"])


def _compute_config(profile: dict) -> dict:
    """Config adaptativa baseada no perfil (mesma lógica de study/strategies)."""
    technique = (profile.get("focus_technique") or "pomodoro").lower()
    is_nd = bool(profile.get("is_neurodivergent"))
    nd_type = (profile.get("neurodivergence_type") or "").lower()

    if is_nd and nd_type == "tdah":
        block_min, break_min, cycles = 25, 5, 3
        reason = "TDAH — blocos curtos (25/5) evitam sobrecarga cognitiva."
    elif is_nd and nd_type == "tea":
        block_min, break_min, cycles = 45, 10, 3
        reason = "TEA — rotina previsível de 45/10 estabiliza o foco."
    elif technique == "ultradian":
        block_min, break_min, cycles = 90, 20, 2
        reason = "Ritmo ultradiano de 90/20 aproveita picos naturais de atenção."
    elif technique == "flow":
        block_min, break_min, cycles = 60, 15, 3
        reason = "Blocos de 60/15 favorecem entrada em estado de flow."
    else:
        block_min, break_min, cycles = 50, 10, 4
        reason = "Pomodoro clássico ampliado: 50/10, 4 ciclos."

    return {
        "block_minutes": block_min,
        "break_minutes": break_min,
        "cycles": cycles,
        "session_length_minutes": (block_min + break_min) * cycles,
        "technique": technique,
        "reason": reason,
    }


def _today_iso() -> str:
    return _now().date().isoformat()


class PomodoroStartInput(BaseModel):
    block_id: Optional[str] = None
    subject_id: Optional[str] = None
    subject: Optional[str] = None
    note: Optional[str] = None


class PomodoroCompleteInput(BaseModel):
    focused_minutes: Optional[int] = None       # override real do timer
    completed_cycles: Optional[int] = None
    interrupted: Optional[bool] = False


@router.get("/config")
async def get_config(user: dict = Depends(require_user)) -> dict:
    profile = await get_profile_doc(user["user_id"])
    return {"config": _compute_config(profile)}


@router.post("/start")
async def start_session(payload: PomodoroStartInput, user: dict = Depends(require_user)) -> dict:
    profile = await get_profile_doc(user["user_id"])
    cfg = _compute_config(profile)

    # Validate/enrich block reference
    block_meta = None
    if payload.block_id:
        block = await db.agenda_blocks.find_one(
            {"id": payload.block_id, "user_id": user["user_id"]}, {"_id": 0}
        )
        if not block:
            raise HTTPException(status_code=404, detail="Bloco de agenda não encontrado")
        block_meta = {
            "id": block["id"],
            "title": block.get("title"),
            "category": block.get("category"),
            "start_time": block.get("start_time"),
            "end_time": block.get("end_time"),
        }

    # Resolve subject reference
    subject_meta = None
    subject_name = payload.subject
    if payload.subject_id:
        subj = await db.subjects.find_one(
            {"id": payload.subject_id, "user_id": user["user_id"]}, {"_id": 0}
        )
        if not subj:
            raise HTTPException(status_code=404, detail="Disciplina não encontrada")
        subject_meta = {
            "id": subj["id"],
            "name": subj.get("name"),
            "is_critical": bool(subj.get("is_critical")),
        }
        subject_name = subj.get("name") or subject_name

    doc = {
        "id": f"pom_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"],
        "block_id": payload.block_id,
        "block": block_meta,
        "subject_id": payload.subject_id,
        "subject_meta": subject_meta,
        "subject": subject_name or (block_meta or {}).get("title"),
        "note": payload.note,
        "config": cfg,
        "planned_minutes": cfg["block_minutes"] * cfg["cycles"],
        "focused_minutes": 0,
        "completed_cycles": 0,
        "status": "running",  # running | completed | skipped
        "date": _today_iso(),
        "started_at": _iso(_now()),
        "completed_at": None,
    }
    await db.pomodoro_sessions.insert_one(dict(doc))
    doc.pop("_id", None)
    return {"session": doc}


@router.post("/{session_id}/complete")
async def complete_session(
    session_id: str,
    payload: PomodoroCompleteInput,
    user: dict = Depends(require_user),
) -> dict:
    sess = await db.pomodoro_sessions.find_one(
        {"id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    started = sess.get("started_at")
    elapsed_min = 0
    if started:
        try:
            started_dt = datetime.fromisoformat(started)
            if started_dt.tzinfo is None:
                started_dt = started_dt.replace(tzinfo=timezone.utc)
            elapsed_min = max(0, int((_now() - started_dt).total_seconds() // 60))
        except Exception:
            elapsed_min = 0

    focused = payload.focused_minutes if payload.focused_minutes is not None else elapsed_min
    focused = max(0, min(focused, sess.get("planned_minutes") or focused))
    cycles = payload.completed_cycles
    if cycles is None:
        block_m = (sess.get("config") or {}).get("block_minutes") or 25
        cycles = max(0, focused // block_m) if block_m else 0

    updates = {
        "focused_minutes": focused,
        "completed_cycles": cycles,
        "status": "completed",
        "interrupted": bool(payload.interrupted),
        "completed_at": _iso(_now()),
    }
    await db.pomodoro_sessions.update_one(
        {"id": session_id, "user_id": user["user_id"]}, {"$set": updates}
    )
    sess.update(updates)

    # Se ancorado a um bloco, marca o bloco como concluído (soft signal).
    if sess.get("block_id") and focused > 0 and not payload.interrupted:
        await db.agenda_blocks.update_one(
            {"id": sess["block_id"], "user_id": user["user_id"]},
            {"$set": {"done": True, "focused_minutes": focused}},
        )

    return {"session": sess}


@router.post("/{session_id}/skip")
async def skip_session(session_id: str, user: dict = Depends(require_user)) -> dict:
    res = await db.pomodoro_sessions.update_one(
        {"id": session_id, "user_id": user["user_id"], "status": "running"},
        {"$set": {"status": "skipped", "completed_at": _iso(_now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou já finalizada")
    return {"ok": True}


@router.get("/today")
async def today_summary(user: dict = Depends(require_user)) -> dict:
    today = _today_iso()
    sessions = await db.pomodoro_sessions.find(
        {"user_id": user["user_id"], "date": today}, {"_id": 0}
    ).sort("started_at", -1).to_list(100)

    total_min = sum((s.get("focused_minutes") or 0) for s in sessions if s.get("status") == "completed")
    total_cycles = sum((s.get("completed_cycles") or 0) for s in sessions if s.get("status") == "completed")
    completed = sum(1 for s in sessions if s.get("status") == "completed")

    profile = await get_profile_doc(user["user_id"])
    return {
        "date": today,
        "config": _compute_config(profile),
        "sessions": sessions,
        "totals": {
            "completed_sessions": completed,
            "focused_minutes": total_min,
            "cycles": total_cycles,
        },
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(require_user)) -> dict:
    await db.pomodoro_sessions.delete_one({"id": session_id, "user_id": user["user_id"]})
    return {"ok": True}


@router.get("/by-subject")
async def stats_by_subject(user: dict = Depends(require_user)) -> dict:
    """Total de minutos focados agrupados por matéria (últimos 30 dias)."""
    from datetime import timedelta
    since = (_now() - timedelta(days=30)).date().isoformat()
    pipeline = [
        {"$match": {
            "user_id": user["user_id"],
            "status": "completed",
            "date": {"$gte": since},
        }},
        {"$group": {
            "_id": {
                "subject_id": "$subject_id",
                "subject": {"$ifNull": ["$subject", "Sem matéria"]},
            },
            "focused_minutes": {"$sum": "$focused_minutes"},
            "sessions": {"$sum": 1},
            "cycles": {"$sum": "$completed_cycles"},
            "is_critical": {"$max": "$subject_meta.is_critical"},
        }},
        {"$sort": {"focused_minutes": -1}},
    ]
    rows = await db.pomodoro_sessions.aggregate(pipeline).to_list(50)
    items = [{
        "subject_id": r["_id"].get("subject_id"),
        "subject": r["_id"].get("subject") or "Sem matéria",
        "focused_minutes": r.get("focused_minutes") or 0,
        "sessions": r.get("sessions") or 0,
        "cycles": r.get("cycles") or 0,
        "is_critical": bool(r.get("is_critical")),
    } for r in rows]
    return {"since": since, "items": items}
