"""Features de baixo custo:

- Lembretes de Autocuidado Essencial (hidratação, alongamento, alimentação, pausa)
- Sistema de Metas semanais + progresso
- Relatório semanal (Feedback de Hábitos)

Sem dependência de LLM — apenas agregação MongoDB.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core import _iso, _now, _today_str, db, require_user

router = APIRouter(prefix="/api", tags=["habits"])


# ─────────────────────────────────────────────────────────────
# Autocuidado — lembretes leves e configuráveis
# ─────────────────────────────────────────────────────────────

DEFAULT_CARE_TASKS = [
    {"slug": "hydrate", "title": "Beber um copo de água", "emoji": "💧", "minutes": 2, "target_per_day": 8},
    {"slug": "stretch", "title": "Alongar 2 min", "emoji": "🧘", "minutes": 2, "target_per_day": 3},
    {"slug": "meal", "title": "Fazer uma refeição sem tela", "emoji": "🍽️", "minutes": 15, "target_per_day": 3},
    {"slug": "walk", "title": "Caminhada curta", "emoji": "🚶", "minutes": 10, "target_per_day": 1},
    {"slug": "breath", "title": "3 respirações profundas", "emoji": "🌬️", "minutes": 1, "target_per_day": 4},
    {"slug": "eye-rest", "title": "Descanso de olhos (20-20-20)", "emoji": "👀", "minutes": 1, "target_per_day": 6},
]


class CareLogInput(BaseModel):
    slug: str


@router.get("/care/today")
async def care_today(user: dict = Depends(require_user)) -> dict:
    """Retorna as tarefas de autocuidado com o contador de HOJE."""
    today = _today_str()
    logs = await db.care_logs.find(
        {"user_id": user["user_id"], "date": today}, {"_id": 0}
    ).to_list(200)
    counts: dict[str, int] = {}
    for log in logs:
        counts[log["slug"]] = counts.get(log["slug"], 0) + 1

    tasks = []
    for t in DEFAULT_CARE_TASKS:
        done = counts.get(t["slug"], 0)
        tasks.append({
            **t,
            "done_today": done,
            "target": t["target_per_day"],
            "progress": min(1.0, done / t["target_per_day"]) if t["target_per_day"] else 0,
        })
    return {"date": today, "tasks": tasks}


@router.post("/care/log")
async def care_log(payload: CareLogInput, user: dict = Depends(require_user)) -> dict:
    if not any(t["slug"] == payload.slug for t in DEFAULT_CARE_TASKS):
        return {"ok": False, "reason": "slug inválido"}
    doc = {
        "id": f"cl_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"],
        "slug": payload.slug,
        "date": _today_str(),
        "at": _iso(_now()),
    }
    await db.care_logs.insert_one(dict(doc))
    return {"ok": True}


# ─────────────────────────────────────────────────────────────
# Metas semanais (Sistema de Recompensas / Metas)
# ─────────────────────────────────────────────────────────────

WEEKLY_GOALS = [
    {"slug": "checkins-5", "title": "5 check-ins na semana", "type": "checkins", "target": 5},
    {"slug": "missions-15", "title": "Concluir 15 missões", "type": "missions_completed", "target": 15},
    {"slug": "study-blocks-10", "title": "10 blocos de estudo", "type": "study_blocks_done", "target": 10},
    {"slug": "sleep-7", "title": "7h+ de sono em 5 noites", "type": "good_sleep_nights", "target": 5},
    {"slug": "movement-4", "title": "4 sessões de movimento", "type": "movement_sessions", "target": 4},
    {"slug": "care-30", "title": "30 ações de autocuidado", "type": "care_actions", "target": 30},
    {"slug": "mindful-3", "title": "3 pausas de mindfulness", "type": "mindful_sessions", "target": 3},
]


def _week_bounds() -> tuple[datetime, datetime]:
    now = _now()
    start = now - timedelta(days=now.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return start, end


async def _goal_progress(user_id: str) -> list[dict]:
    start, end = _week_bounds()
    start_iso, end_iso = _iso(start), _iso(end)
    start_date, end_date = start.date().isoformat(), end.date().isoformat()

    checkins = await db.checkins.count_documents(
        {"user_id": user_id, "created_at": {"$gte": start_iso, "$lt": end_iso}}
    )
    good_sleep = await db.checkins.count_documents({
        "user_id": user_id, "created_at": {"$gte": start_iso, "$lt": end_iso},
        "sleep_hours": {"$gte": 7},
    })
    missions_done = await db.mission_events.count_documents({
        "user_id": user_id, "completed": True, "at": {"$gte": start_iso, "$lt": end_iso},
    })
    care_actions = await db.care_logs.count_documents({
        "user_id": user_id, "date": {"$gte": start_date, "$lt": end_date},
    })
    mindful = await db.mindfulness_logs.count_documents({
        "user_id": user_id, "created_at": {"$gte": start_iso, "$lt": end_iso},
    })
    # Estudo blocks done (from agenda)
    bundles = await db.missions_bundles.find(
        {"user_id": user_id, "created_at": {"$gte": start_iso, "$lt": end_iso}}, {"_id": 0}
    ).to_list(20)
    study_missions = 0
    movement_missions = 0
    for b in bundles:
        for m in b.get("missions", []):
            if m.get("completed"):
                if m.get("category") in ("estudo", "aula"):
                    study_missions += 1
                if m.get("category") in ("movimento",):
                    movement_missions += 1

    type_map = {
        "checkins": checkins,
        "missions_completed": missions_done,
        "study_blocks_done": study_missions,
        "good_sleep_nights": good_sleep,
        "movement_sessions": movement_missions,
        "care_actions": care_actions,
        "mindful_sessions": mindful,
    }

    out = []
    for goal in WEEKLY_GOALS:
        current = type_map.get(goal["type"], 0)
        out.append({
            **goal,
            "current": current,
            "progress": min(1.0, current / goal["target"]) if goal["target"] else 0,
            "achieved": current >= goal["target"],
        })
    return out


@router.get("/goals/weekly")
async def weekly_goals(user: dict = Depends(require_user)) -> dict:
    start, end = _week_bounds()
    goals = await _goal_progress(user["user_id"])
    achieved = sum(1 for g in goals if g["achieved"])
    return {
        "week_start": start.date().isoformat(),
        "week_end": (end - timedelta(days=1)).date().isoformat(),
        "achieved": achieved,
        "total": len(goals),
        "goals": goals,
    }


# ─────────────────────────────────────────────────────────────
# Feedback de Hábitos / Relatório Semanal
# ─────────────────────────────────────────────────────────────

@router.get("/report/weekly")
async def weekly_report(user: dict = Depends(require_user)) -> dict:
    user_id = user["user_id"]
    start, end = _week_bounds()
    prev_start = start - timedelta(days=7)
    start_iso, end_iso = _iso(start), _iso(end)
    prev_start_iso = _iso(prev_start)

    async def stats_for(range_start_iso: str, range_end_iso: str) -> dict:
        checkins = await db.checkins.find(
            {"user_id": user_id,
             "created_at": {"$gte": range_start_iso, "$lt": range_end_iso}},
            {"_id": 0},
        ).to_list(60)
        missions_done = await db.mission_events.count_documents({
            "user_id": user_id, "completed": True,
            "at": {"$gte": range_start_iso, "$lt": range_end_iso},
        })
        avg_sleep = round(
            sum(c.get("sleep_hours", 0) for c in checkins) / len(checkins), 1
        ) if checkins else 0
        avg_mood = round(
            sum(c.get("mood", 0) for c in checkins) / len(checkins), 1
        ) if checkins else 0
        avg_stress = round(
            sum(c.get("stress", 0) for c in checkins) / len(checkins), 1
        ) if checkins else 0
        return {
            "checkins": len(checkins),
            "missions_completed": missions_done,
            "avg_sleep": avg_sleep,
            "avg_mood": avg_mood,
            "avg_stress": avg_stress,
        }

    current = await stats_for(start_iso, end_iso)
    previous = await stats_for(prev_start_iso, start_iso)

    def delta(now: float, prev: float) -> float:
        return round(now - prev, 1)

    insights: list[str] = []
    if current["checkins"] < previous["checkins"]:
        insights.append("Você fez menos check-ins que na semana passada — 30 segundos ajudam o copiloto a te entender.")
    if current["avg_sleep"] and previous["avg_sleep"] and current["avg_sleep"] < previous["avg_sleep"] - 0.5:
        insights.append(f"Seu sono caiu {round(previous['avg_sleep'] - current['avg_sleep'], 1)}h em média — considere revisar a Dieta de Sono.")
    if current["avg_stress"] > 3.5:
        insights.append("Estresse médio alto esta semana. Pausas de mindfulness e ócio protegido podem ajudar.")
    if current["missions_completed"] > previous["missions_completed"]:
        insights.append(f"Ótimo — {current['missions_completed'] - previous['missions_completed']} missões a mais que na semana anterior.")
    if not insights:
        insights.append("Semana consistente. Continue no seu ritmo.")

    return {
        "week_start": start.date().isoformat(),
        "week_end": (end - timedelta(days=1)).date().isoformat(),
        "current": current,
        "previous": previous,
        "delta": {
            "checkins": current["checkins"] - previous["checkins"],
            "missions_completed": current["missions_completed"] - previous["missions_completed"],
            "avg_sleep": delta(current["avg_sleep"], previous["avg_sleep"]),
            "avg_mood": delta(current["avg_mood"], previous["avg_mood"]),
            "avg_stress": delta(current["avg_stress"], previous["avg_stress"]),
        },
        "insights": insights,
    }
