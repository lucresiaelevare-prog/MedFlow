"""Missions: daily mission generation via Claude Sonnet + CRUD."""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException

from core import EMERGENT_LLM_KEY, _iso, _now, _today_str, db, require_user
from models import MissionCompleteInput
from routes.iea import (
    compute_pillars,
    current_streak,
    iea_from_pillars,
    maybe_award_badges,
)
from routes.profile import get_profile_doc

logger = logging.getLogger("medflow.missions")
router = APIRouter(prefix="/api", tags=["missions"])

MISSION_CATEGORIES = ["aula", "estudo", "movimento", "descanso", "alimentacao", "bemestar", "social", "admin"]


def _mission_prompt(context: dict) -> str:
    return f"""
Você é o Copiloto Acadêmico do estudante. Gere entre 3 e 5 MISSÕES para HOJE.

Cada missão deve ser UMA ação clara e executável hoje, curta (máx 12 palavras), verbo no imperativo suave.

Contexto do estudante:
- Data: {context['date']} ({context['weekday']})
- Modo atual: {context['mode']}
- Ferramenta de estudo preferida: {context['study_tool']}
- Disciplinas: {context['subjects']}
- Provas próximas (14 dias): {context['upcoming_exams']}
- Última prova + nota: {context.get('last_exam', 'nenhuma registrada')}
- Último check-in (sono/energia/humor/stress): {context.get('checkin', 'sem check-in recente')}
- IEA hoje: {context['iea']} — pilar mais fraco: {context['weakest_pillar']}
- Adesão às últimas missões: {context['adherence']}%
- Streak atual: {context['streak']} dias

Regras invioláveis:
1. Escreva SEMPRE em pt-BR, tom acolhedor, sem clichês motivacionais.
2. Categorias válidas: {MISSION_CATEGORIES}.
3. Ao menos UMA missão deve endereçar o pilar mais fraco ({context['weakest_pillar']}).
4. Se modo=prova: priorize categorias estudo + descanso.
5. Se modo=plantao: priorize descanso + alimentacao + hidratacao (categoria alimentacao).
6. Se modo=dependencia: inclua 1 missão extra da disciplina em dependência.
7. Se modo=recuperacao: use os tópicos fracos da última prova.
8. Se ferramenta de estudo é 'anki': cite Anki em missões de estudo (ex: "Revise 20 flashcards de X no Anki"). Análogo para 'quizlet'/'remnote'.
9. Nunca ultrapasse 5 missões. Nunca menos de 3.
10. Nada de emojis, aspas, markdown, hashtags.

Devolva EXCLUSIVAMENTE um JSON válido, sem cerca de código, no formato:
{{"missions": [
  {{"title": "<frase curta>", "category": "<uma das categorias>", "minutes": <int>, "why": "<motivo em <=12 palavras>"}}
]}}
""".strip()


async def _call_llm_missions(prompt: str) -> list[dict]:
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"medflow-missions-{uuid.uuid4().hex[:10]}",
        system_message="Você é o Copiloto Acadêmico do MedFlow, um sistema operacional da vida universitária para estudantes brasileiros de medicina.",
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")
    try:
        reply = await chat.send_message(UserMessage(text=prompt))
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM missions call failed: %s", exc)
        return []
    text = reply if isinstance(reply, str) else str(reply)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return []
    missions = data.get("missions") or []
    clean: list[dict] = []
    for mi in missions[:5]:
        title = str(mi.get("title", "")).strip()
        if not title:
            continue
        cat = str(mi.get("category", "admin")).strip()
        if cat not in MISSION_CATEGORIES:
            cat = "admin"
        try:
            minutes = int(mi.get("minutes", 20))
        except Exception:
            minutes = 20
        clean.append({
            "title": title[:120],
            "category": cat,
            "minutes": max(5, min(180, minutes)),
            "why": str(mi.get("why", ""))[:140],
        })
    return clean


def _fallback_missions(_context: dict) -> list[dict]:
    return [
        {"title": "Beba um copo de água agora", "category": "alimentacao", "minutes": 2,
         "why": "hidratação sustenta cognição"},
        {"title": "Faça 3 respirações profundas", "category": "bemestar", "minutes": 3,
         "why": "reduz o ruído mental"},
        {"title": "Escolha 1 tópico e leia por 25 minutos", "category": "estudo", "minutes": 25,
         "why": "foco curto rende mais"},
    ]


async def build_context(user_id: str) -> dict:
    """Aggregate context used by the mission prompt AND the check-in recommendation."""
    profile = await get_profile_doc(user_id)
    subjects = await db.subjects.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    today = _now().date()
    upcoming_deadline = (today + timedelta(days=14)).isoformat()
    upcoming = await db.exams.find(
        {"user_id": user_id, "exam_date": {"$gte": today.isoformat(),
                                            "$lte": upcoming_deadline}},
        {"_id": 0}
    ).sort("exam_date", 1).to_list(20)
    last_graded = await db.exams.find_one(
        {"user_id": user_id, "grade": {"$ne": None}}, {"_id": 0},
        sort=[("graded_at", -1)]
    )
    last_checkin = await db.checkins.find_one(
        {"user_id": user_id}, {"_id": 0}, sort=[("created_at", -1)]
    )
    streak = await current_streak(user_id)
    pillars = await compute_pillars(user_id)
    iea, weakest = iea_from_pillars(pillars)

    since = _now() - timedelta(days=3)
    bundles = await db.missions_bundles.find(
        {"user_id": user_id, "created_at": {"$gte": _iso(since)}}, {"_id": 0}
    ).to_list(10)
    total = sum(len(b.get("missions", [])) for b in bundles)
    done = sum(1 for b in bundles for m in b.get("missions", []) if m.get("completed"))
    adherence = round((done / total) * 100) if total else 0

    subj_str = ", ".join(
        f"{s['name']}{' (dep)' if s.get('is_dependency') else ''}" for s in subjects
    ) or "nenhuma cadastrada"
    upcoming_str = "; ".join(
        f"{e['subject_name']} - {e['name']} em {e['exam_date']}" for e in upcoming
    ) or "sem provas nos próximos 14 dias"
    last_exam_str = (
        f"{last_graded['subject_name']} - {last_graded['name']}: nota {last_graded['grade']}"
        f" (fracos: {last_graded.get('weak_topics') or 'não informado'})"
    ) if last_graded else "nenhuma registrada"
    if last_checkin:
        checkin_str = (
            f"sono {last_checkin.get('sleep_hours')}h, energia {last_checkin.get('energy')}, "
            f"humor {last_checkin.get('mood')}, stress {last_checkin.get('stress')}"
        )
    else:
        checkin_str = "sem check-in recente"

    return {
        "date": today.isoformat(),
        "weekday": today.strftime("%A"),
        "mode": profile.get("mode", "rotina"),
        "study_tool": profile.get("study_tool", "anki"),
        "subjects": subj_str,
        "upcoming_exams": upcoming_str,
        "last_exam": last_exam_str,
        "checkin": checkin_str,
        "iea": iea,
        "weakest_pillar": weakest,
        "adherence": adherence,
        "streak": streak,
    }


@router.post("/missions/generate")
async def generate_missions(user: dict = Depends(require_user), force: bool = False) -> dict:
    user_id = user["user_id"]
    today = _today_str()
    if not force:
        existing = await db.missions_bundles.find_one(
            {"user_id": user_id, "date": today}, {"_id": 0}
        )
        if existing:
            return {"bundle": existing}

    context = await build_context(user_id)
    prompt = _mission_prompt(context)
    missions = await _call_llm_missions(prompt)
    if not missions:
        missions = _fallback_missions(context)

    items = []
    for m in missions:
        items.append({
            "id": f"m_{uuid.uuid4().hex[:10]}",
            **m,
            "completed": False,
            "skipped": False,
        })
    bundle = {
        "id": f"mb_{uuid.uuid4().hex[:10]}",
        "user_id": user_id,
        "date": today,
        "mode": context["mode"],
        "iea_at_gen": context["iea"],
        "weakest_pillar": context["weakest_pillar"],
        "missions": items,
        "created_at": _iso(_now()),
    }
    await db.missions_bundles.update_one(
        {"user_id": user_id, "date": today}, {"$set": bundle}, upsert=True,
    )
    return {"bundle": bundle}


@router.get("/missions/today")
async def get_today_missions(user: dict = Depends(require_user)) -> dict:
    bundle = await db.missions_bundles.find_one(
        {"user_id": user["user_id"], "date": _today_str()}, {"_id": 0}
    )
    return {"bundle": bundle}


@router.post("/missions/{mission_id}/complete")
async def complete_mission(mission_id: str, payload: MissionCompleteInput,
                           user: dict = Depends(require_user)) -> dict:
    bundle = await db.missions_bundles.find_one(
        {"user_id": user["user_id"], "date": _today_str(), "missions.id": mission_id}
    )
    if not bundle:
        raise HTTPException(status_code=404, detail="Missão não encontrada")
    field = "missions.$.completed" if payload.completed else "missions.$.skipped"
    other = "missions.$.skipped" if payload.completed else "missions.$.completed"
    await db.missions_bundles.update_one(
        {"user_id": user["user_id"], "date": _today_str(), "missions.id": mission_id},
        {"$set": {field: True, other: False, "missions.$.updated_at": _iso(_now())}},
    )
    await db.mission_events.insert_one({
        "id": f"me_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"],
        "mission_id": mission_id,
        "completed": bool(payload.completed),
        "at": _iso(_now()),
    })
    await maybe_award_badges(user["user_id"])
    bundle = await db.missions_bundles.find_one(
        {"user_id": user["user_id"], "date": _today_str()}, {"_id": 0}
    )
    return {"bundle": bundle}
