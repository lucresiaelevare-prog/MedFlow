"""Priorização inteligente de tarefas do dia.

Ranks HOJE: blocos de agenda + missões pendentes + provas próximas em uma lista
única, ordenada por urgência/importância, com um score explicável.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends

from core import _now, _today_str, db, require_user
from routes.profile import get_profile_doc

router = APIRouter(prefix="/api", tags=["priority"])


CATEGORY_WEIGHT = {
    "academic": 90, "study": 85, "care": 70, "physical": 60,
    "sleep": 55, "leisure": 40, "family": 45, "social": 45, "love": 42,
}


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _score_block(block: dict, now_min: int) -> tuple[int, str]:
    base = CATEGORY_WEIGHT.get(block.get("category"), 50)
    reasons = [f"Categoria {block.get('category')}"]
    start = _minutes(block.get("start_time", "23:59"))
    if abs(start - now_min) <= 60:
        base += 25
        reasons.append("acontece agora")
    elif start > now_min:
        base += max(0, 15 - (start - now_min) // 30)
    if block.get("done"):
        base -= 60
        reasons.append("já feito")
    return base, " · ".join(reasons)


def _score_mission(mission: dict, adherence: int) -> tuple[int, str]:
    cat_map = {"estudo": 80, "descanso": 55, "movimento": 60, "alimentacao": 45,
               "bemestar": 50, "social": 40, "admin": 35, "aula": 90}
    base = cat_map.get(mission.get("category"), 50)
    reasons = [f"Missão · {mission.get('category')}"]
    if mission.get("completed"):
        base -= 60
        reasons.append("concluída")
    elif adherence < 40:
        base += 15
        reasons.append("baixa adesão recente")
    return base, " · ".join(reasons)


def _score_exam(exam: dict) -> tuple[int, str]:
    try:
        d = datetime.fromisoformat(exam["exam_date"]).date()
        days_left = (d - _now().date()).days
    except Exception:
        return 40, "prova sem data válida"
    if days_left < 0:
        return 0, "prova já ocorrida"
    weight = float(exam.get("weight") or 1.0)
    urgency = max(0, 30 - days_left) * 3
    is_critical = bool(exam.get("subject_is_critical"))
    critical_bonus = 12 if is_critical else 0
    tag = "prova crítica · " if is_critical else "prova "
    return (
        int(60 + urgency + weight * 5 + critical_bonus),
        f"{tag}em {days_left} dia(s)",
    )


@router.get("/priority/today")
async def priority_today(user: dict = Depends(require_user)) -> dict:
    user_id = user["user_id"]
    profile = await get_profile_doc(user_id)
    now = _now()
    now_min = now.hour * 60 + now.minute
    dow = now.weekday()

    # Agenda de hoje (recorrentes deste dia + com date == hoje)
    today_iso = _today_str()
    blocks = await db.agenda_blocks.find(
        {"user_id": user_id,
         "$or": [{"day_of_week": dow}, {"date": today_iso}]},
        {"_id": 0},
    ).to_list(200)

    # Missões de hoje
    bundle = await db.missions_bundles.find_one(
        {"user_id": user_id, "date": today_iso}, {"_id": 0}
    )
    missions = (bundle or {}).get("missions", [])

    # Adesão recente (3 dias)
    since = now - timedelta(days=3)
    bundles = await db.missions_bundles.find(
        {"user_id": user_id, "created_at": {"$gte": since.isoformat()}}, {"_id": 0}
    ).to_list(10)
    total = sum(len(b.get("missions", [])) for b in bundles) or 1
    done = sum(1 for b in bundles for m in b.get("missions", []) if m.get("completed"))
    adherence = round(done / total * 100)

    # Provas próximas (7 dias)
    upcoming_deadline = (now.date() + timedelta(days=7)).isoformat()
    exams = await db.exams.find(
        {"user_id": user_id, "exam_date": {"$gte": today_iso, "$lte": upcoming_deadline}},
        {"_id": 0},
    ).to_list(50)

    items = []
    for b in blocks:
        s, why = _score_block(b, now_min)
        items.append({
            "kind": "block", "id": b["id"], "title": b["title"],
            "category": b["category"], "score": s, "why": why,
            "start_time": b.get("start_time"), "end_time": b.get("end_time"),
            "done": bool(b.get("done")),
        })
    for m in missions:
        s, why = _score_mission(m, adherence)
        items.append({
            "kind": "mission", "id": m.get("id"), "title": m.get("title"),
            "category": m.get("category"), "score": s, "why": why,
            "minutes": m.get("minutes"), "completed": bool(m.get("completed")),
        })
    for e in exams:
        s, why = _score_exam(e)
        items.append({
            "kind": "exam", "id": e.get("id"),
            "title": f"{e.get('subject_name')} — {e.get('name')}",
            "category": "prova", "score": s, "why": why,
            "exam_date": e.get("exam_date"), "weight": e.get("weight"),
        })

    items.sort(key=lambda x: x["score"], reverse=True)
    return {
        "date": today_iso,
        "adherence": adherence,
        "mode": profile.get("mode", "rotina"),
        "items": items[:20],
    }
