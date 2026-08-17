"""Planner routes — Agenda (time-blocks), Study strategies, Sleep diet, Leisure.

Implements the 5 high-priority features:
  1) Persistência de Dados do Aluno  → extended profile fields (handled in profile.py + models.py).
  2) Gerenciamento de Tempo e Agenda → CRUD /api/agenda/blocks + proposal generator.
  3) Estratégias de Estudo           → GET /api/study/strategies.
  4) Dieta de Sono                   → GET /api/sleep/plan.
  5) Propostas de Atividades p/ Ócio → GET /api/leisure/suggestions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core import _clean, _iso, _now, db, require_user
from models import AgendaBlockInput, AgendaBlockUpdate
from routes.profile import get_profile_doc

router = APIRouter(prefix="/api", tags=["planner"])


CATEGORY_COLORS = {
    "academic": "#2F6BFF",
    "study": "#7A5CFF",
    "physical": "#22B573",
    "leisure": "#F59E0B",
    "social": "#EC4899",
    "family": "#EF4444",
    "love": "#F472B6",
    "sleep": "#0F172A",
    "care": "#14B8A6",
}
VALID_CATEGORIES = set(CATEGORY_COLORS.keys())


def _validate_hhmm(value: str) -> None:
    try:
        datetime.strptime(value, "%H:%M")
    except Exception:
        raise HTTPException(status_code=400, detail=f"Horário inválido: {value} (use HH:MM)")


def _time_to_minutes(hhmm: str) -> int:
    dt = datetime.strptime(hhmm, "%H:%M")
    return dt.hour * 60 + dt.minute


def _minutes_to_hhmm(mins: int) -> str:
    mins = mins % (24 * 60)
    return f"{mins // 60:02d}:{mins % 60:02d}"


# ─────────────────────────────────────────────────────────────
# ETAPA 2 — Agenda (time blocks)
# ─────────────────────────────────────────────────────────────

@router.post("/agenda/blocks")
async def create_block(payload: AgendaBlockInput, user: dict = Depends(require_user)) -> dict:
    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Categoria inválida")
    _validate_hhmm(payload.start_time)
    _validate_hhmm(payload.end_time)
    if _time_to_minutes(payload.end_time) <= _time_to_minutes(payload.start_time):
        raise HTTPException(status_code=400, detail="end_time deve ser depois de start_time")
    if payload.day_of_week is None and not payload.date:
        raise HTTPException(status_code=400, detail="Informe day_of_week (recorrente) ou date (pontual)")

    doc = {
        "id": f"blk_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"],
        "title": payload.title.strip() or payload.category.capitalize(),
        "category": payload.category,
        "start_time": payload.start_time,
        "end_time": payload.end_time,
        "day_of_week": payload.day_of_week,
        "date": payload.date,
        "note": payload.note,
        "color": payload.color or CATEGORY_COLORS[payload.category],
        "done": False,
        "created_at": _iso(_now()),
        "source": "manual",
    }
    await db.agenda_blocks.insert_one(dict(doc))
    return {"block": _clean(doc)}


@router.get("/agenda/blocks")
async def list_blocks(user: dict = Depends(require_user)) -> dict:
    items = await db.agenda_blocks.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort([("day_of_week", 1), ("start_time", 1)]).to_list(1000)
    return {"blocks": items}


@router.patch("/agenda/blocks/{block_id}")
async def update_block(block_id: str, payload: AgendaBlockUpdate,
                       user: dict = Depends(require_user)) -> dict:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "category" in updates and updates["category"] not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Categoria inválida")
    for tk in ("start_time", "end_time"):
        if tk in updates:
            _validate_hhmm(updates[tk])
    updates["updated_at"] = _iso(_now())
    result = await db.agenda_blocks.update_one(
        {"id": block_id, "user_id": user["user_id"]}, {"$set": updates}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Bloco não encontrado")
    block = await db.agenda_blocks.find_one({"id": block_id}, {"_id": 0})
    return {"block": block}


@router.delete("/agenda/blocks/{block_id}")
async def delete_block(block_id: str, user: dict = Depends(require_user)) -> dict:
    await db.agenda_blocks.delete_one({"id": block_id, "user_id": user["user_id"]})
    return {"ok": True}


@router.get("/agenda/week")
async def week_agenda(user: dict = Depends(require_user)) -> dict:
    blocks = await db.agenda_blocks.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).to_list(1000)
    days = {i: [] for i in range(7)}
    for b in blocks:
        if b.get("day_of_week") is not None:
            days[b["day_of_week"]].append(b)
        elif b.get("date"):
            try:
                dow = datetime.fromisoformat(b["date"]).weekday()
                days[dow].append(b)
            except Exception:
                continue
    for k in days:
        days[k].sort(key=lambda x: x.get("start_time", ""))
    return {"days": days, "categories": CATEGORY_COLORS}


def _proposed_blocks_from_profile(profile: dict) -> list[dict]:
    """Build a suggested weekly agenda based on profile answers."""
    wake = profile.get("wake_time") or "07:00"
    sleep = profile.get("sleep_time") or "23:30"
    target_sleep = profile.get("target_sleep_hours") or 8
    energy_peak = profile.get("energy_peak") or "manha"
    chronotype = profile.get("chronotype") or "matutino"
    phys_days = int(profile.get("physical_days_per_week") or 3)
    social_pref = profile.get("social_pref") or "media"
    family_pref = profile.get("family_pref") or "semanal"

    _validate_hhmm(wake)
    _validate_hhmm(sleep)
    wm = _time_to_minutes(wake)
    sm = _time_to_minutes(sleep)

    # Study window aligned with peak
    if energy_peak == "manha":
        study_start = _minutes_to_hhmm(wm + 60)   # +1h após acordar
        study_end = _minutes_to_hhmm(wm + 60 + 180)  # 3h
    elif energy_peak == "tarde":
        study_start = "14:00"
        study_end = "17:00"
    else:
        study_start = "19:30"
        study_end = "22:00"

    physical_start = "07:00" if chronotype == "matutino" else "18:00"
    physical_end = _minutes_to_hhmm(_time_to_minutes(physical_start) + 60)

    blocks: list[dict] = []

    # Segunda a sexta: academic + study
    for dow in range(0, 5):
        blocks.append({"category": "academic", "title": "Aulas / Rotação",
                       "start_time": "08:00", "end_time": "12:00", "day_of_week": dow})
        blocks.append({"category": "study", "title": "Estudo focado",
                       "start_time": study_start, "end_time": study_end, "day_of_week": dow})
        blocks.append({"category": "leisure", "title": "Ócio protegido",
                       "start_time": "21:00", "end_time": "22:00", "day_of_week": dow})

    # Atividade física distribuída
    phys_days = max(0, min(7, phys_days))
    phys_slots = [1, 3, 5, 0, 2, 4, 6][:phys_days]
    for dow in phys_slots:
        blocks.append({"category": "physical", "title": "Atividade física",
                       "start_time": physical_start, "end_time": physical_end,
                       "day_of_week": dow})

    # Vida social
    social_days = {"baixa": [5], "media": [5, 6], "alta": [4, 5, 6]}.get(social_pref, [5, 6])
    for dow in social_days:
        blocks.append({"category": "social", "title": "Amigos / vida social",
                       "start_time": "19:00", "end_time": "22:30", "day_of_week": dow})

    # Família
    family_map = {"diaria": list(range(7)), "semanal": [6], "quinzenal": [6], "mensal": [6]}
    for dow in family_map.get(family_pref, [6]):
        blocks.append({"category": "family", "title": "Família",
                       "start_time": "12:00", "end_time": "14:00", "day_of_week": dow})

    # Sono (bloco visual)
    blocks.append({"category": "sleep", "title": f"Sono ({target_sleep}h)",
                   "start_time": sleep, "end_time": wake, "day_of_week": None,
                   "note": f"Rotina de sono todos os dias · dormir {sleep}, acordar {wake}"})

    # Wrap com defaults e ids
    now_iso = _iso(_now())
    finished: list[dict] = []
    for b in blocks:
        b.setdefault("date", None)
        b.setdefault("day_of_week", None)
        # Bloco sleep: aplica todos os dias
        finished.append({
            "id": f"blk_{uuid.uuid4().hex[:10]}",
            "user_id": None,
            "title": b["title"],
            "category": b["category"],
            "start_time": b["start_time"],
            "end_time": b["end_time"] if b["category"] != "sleep" else b["end_time"],
            "day_of_week": b["day_of_week"],
            "date": None,
            "note": b.get("note"),
            "color": CATEGORY_COLORS.get(b["category"], "#6B8E76"),
            "done": False,
            "created_at": now_iso,
            "source": "proposal",
        })
    return finished


@router.post("/agenda/proposal")
async def generate_proposal(
    user: dict = Depends(require_user),
    replace: bool = Query(default=False, description="Substitui blocos gerados anteriormente"),
) -> dict:
    profile = await get_profile_doc(user["user_id"])
    if replace:
        await db.agenda_blocks.delete_many(
            {"user_id": user["user_id"], "source": "proposal"}
        )
    proposal = _proposed_blocks_from_profile(profile)
    for b in proposal:
        b["user_id"] = user["user_id"]
    if proposal:
        await db.agenda_blocks.insert_many([dict(b) for b in proposal])
    return {"created": len(proposal), "blocks": proposal}


# ─────────────────────────────────────────────────────────────
# ETAPA 3 — Estratégias de Estudo
# ─────────────────────────────────────────────────────────────

def _build_study_strategies(profile: dict, subjects: list[dict], exams: list[dict]) -> dict:
    chronotype = profile.get("chronotype") or "matutino"
    energy_peak = profile.get("energy_peak") or "manha"
    technique = profile.get("focus_technique") or "pomodoro"
    is_nd = bool(profile.get("is_neurodivergent"))
    nd_type = (profile.get("neurodivergence_type") or "").lower()

    # Duração ideal de bloco
    if is_nd and nd_type == "tdah":
        block_min, break_min, blocks_per_session = 25, 5, 3
    elif is_nd and nd_type == "tea":
        block_min, break_min, blocks_per_session = 45, 10, 3
    elif technique == "ultradian":
        block_min, break_min, blocks_per_session = 90, 20, 2
    elif technique == "flow":
        block_min, break_min, blocks_per_session = 60, 15, 3
    else:  # pomodoro / livre
        block_min, break_min, blocks_per_session = 50, 10, 4

    # Melhor janela de estudo
    windows = {
        "manha": "07:30–11:30",
        "tarde": "14:00–17:30",
        "noite": "19:30–22:30",
    }
    window = windows.get(energy_peak, windows["manha"])

    # Frequência semanal
    weekly_frequency = "5 dias/semana (seg–sex), com sábado leve"
    if is_nd and nd_type == "tdah":
        weekly_frequency = "6 sessões curtas por semana, evitando maratonas"

    # Priorização por prova
    upcoming = sorted([e for e in exams if e.get("exam_date")],
                      key=lambda e: e["exam_date"])[:5]
    priority = []
    today = _now().date()
    for e in upcoming:
        try:
            days = (datetime.fromisoformat(e["exam_date"]).date() - today).days
        except Exception:
            days = None
        priority.append({
            "exam_id": e.get("id"),
            "subject_name": e.get("subject_name"),
            "name": e.get("name"),
            "exam_date": e.get("exam_date"),
            "days_left": days,
            "weight": e.get("weight") or 1.0,
        })

    dep_subjects = [s for s in subjects if s.get("is_dependency")]
    dep_names = [s["name"] for s in dep_subjects]

    techniques = [
        {
            "name": "Revisão espaçada",
            "detail": "Revise cada tópico após 1, 3, 7 e 14 dias. Cartões (Anki) funcionam bem.",
        },
        {
            "name": "Recuperação ativa",
            "detail": "Feche o material e escreva o que lembra. Descubra as lacunas antes da prova.",
        },
        {
            "name": "Estudo intercalado",
            "detail": "Alterne 2–3 matérias por sessão. Melhora fixação em áreas correlatas.",
        },
        {
            "name": "Bloco de 5 minutos",
            "detail": "Quando travar, comprometa-se a estudar apenas 5 min. Baixa o custo de iniciar.",
        },
    ]

    tips = []
    if is_nd and nd_type == "tdah":
        tips.append("Ligue o timer visual. Comece pela tarefa mais aversiva por só 10 min.")
        tips.append("Prepare o ambiente antes: água, celular no modo foco, materiais prontos.")
    if is_nd and nd_type == "tea":
        tips.append("Rotina previsível: mesmo horário e mesmo lugar todos os dias.")
    if dep_names:
        tips.append(f"Reserve 30–45 min extras/dia para dependências: {', '.join(dep_names)}.")
    if chronotype == "noturno":
        tips.append("Evite conteúdo novo tarde da noite; use a noite para revisão ativa.")

    return {
        "session": {
            "block_minutes": block_min,
            "break_minutes": break_min,
            "blocks_per_session": blocks_per_session,
            "session_length_minutes": (block_min + break_min) * blocks_per_session,
            "technique": technique,
        },
        "best_window": window,
        "weekly_frequency": weekly_frequency,
        "techniques": techniques,
        "priority_exams": priority,
        "dependencies": dep_names,
        "tips": tips,
    }


@router.get("/study/strategies")
async def study_strategies(user: dict = Depends(require_user)) -> dict:
    profile = await get_profile_doc(user["user_id"])
    subjects = await db.subjects.find(
        {"user_id": user["user_id"]}, {"_id": 0}).to_list(200)
    exams = await db.exams.find(
        {"user_id": user["user_id"]}, {"_id": 0}).sort("exam_date", 1).to_list(200)
    return {"strategies": _build_study_strategies(profile, subjects, exams)}


# ─────────────────────────────────────────────────────────────
# ETAPA 4 — Dieta de Sono
# ─────────────────────────────────────────────────────────────

def _build_sleep_plan(profile: dict) -> dict:
    target = float(profile.get("target_sleep_hours") or 8)
    wake = profile.get("wake_time") or "07:00"
    sleep_time = profile.get("sleep_time")
    chronotype = profile.get("chronotype") or "matutino"

    _validate_hhmm(wake)
    if not sleep_time:
        # Calcula a partir do wake_time
        sleep_min = (_time_to_minutes(wake) - int(target * 60)) % (24 * 60)
        sleep_time = _minutes_to_hhmm(sleep_min)
    else:
        _validate_hhmm(sleep_time)

    wind_down = _minutes_to_hhmm((_time_to_minutes(sleep_time) - 45) % (24 * 60))
    no_screens = _minutes_to_hhmm((_time_to_minutes(sleep_time) - 60) % (24 * 60))
    no_caffeine_hour = 14 if chronotype == "matutino" else 15
    nap_window = "13:00–13:20" if chronotype != "noturno" else "15:00–15:20"

    checklist = [
        {"time": no_caffeine_hour, "label": f"Sem cafeína após {no_caffeine_hour}:00"},
        {"time": no_screens, "label": f"Reduza telas às {no_screens}"},
        {"time": wind_down, "label": f"Rotina de desaceleração às {wind_down}"},
        {"time": sleep_time, "label": f"Luzes apagadas às {sleep_time}"},
        {"time": wake, "label": f"Acordar às {wake} (mesmo no fim de semana)"},
    ]

    tips = [
        "Mantenha o quarto entre 18–22°C e escuro.",
        "Álcool prejudica o sono profundo — evite nas noites de estudo intenso.",
        "Exponha-se à luz natural nos primeiros 30 min após acordar.",
    ]
    if chronotype == "noturno":
        tips.append("Se preciso, avance o horário de dormir em 15 min a cada 3 dias.")

    return {
        "target_hours": target,
        "wake_time": wake,
        "sleep_time": sleep_time,
        "wind_down_start": wind_down,
        "no_screens_after": no_screens,
        "no_caffeine_after": f"{no_caffeine_hour}:00",
        "nap_window": nap_window,
        "chronotype": chronotype,
        "checklist": checklist,
        "tips": tips,
    }


@router.get("/sleep/plan")
async def sleep_plan(user: dict = Depends(require_user)) -> dict:
    profile = await get_profile_doc(user["user_id"])
    return {"plan": _build_sleep_plan(profile)}


# ─────────────────────────────────────────────────────────────
# ETAPA 5 — Propostas de Ócio
# ─────────────────────────────────────────────────────────────

LEISURE_LIBRARY = [
    {"slug": "walk-20", "title": "Caminhada leve de 20 min",
     "duration_min": 20, "energy": "baixa", "tags": ["fisico", "ar-livre"]},
    {"slug": "playlist-chill", "title": "Playlist para relaxar",
     "duration_min": 30, "energy": "baixa", "tags": ["musica", "casa"]},
    {"slug": "livro-30", "title": "Leia 30 min de um livro não-acadêmico",
     "duration_min": 30, "energy": "baixa", "tags": ["leitura", "casa"]},
    {"slug": "cine-pipoca", "title": "Filme com pipoca",
     "duration_min": 120, "energy": "baixa", "tags": ["cinema", "casa"]},
    {"slug": "cafe-amigo", "title": "Café com um amigo",
     "duration_min": 60, "energy": "media", "tags": ["social", "rua"]},
    {"slug": "video-jogo", "title": "45 min de videogame",
     "duration_min": 45, "energy": "media", "tags": ["games", "casa"]},
    {"slug": "cozinha-nova", "title": "Cozinhe uma receita nova",
     "duration_min": 60, "energy": "media", "tags": ["culinaria", "casa"]},
    {"slug": "bike", "title": "Pedale 45 min",
     "duration_min": 45, "energy": "alta", "tags": ["fisico", "ar-livre"]},
    {"slug": "diario", "title": "Escreva 15 min no diário",
     "duration_min": 15, "energy": "baixa", "tags": ["autoconhecimento", "casa"]},
    {"slug": "arte", "title": "Faça um esboço ou desenho livre",
     "duration_min": 30, "energy": "baixa", "tags": ["arte", "casa"]},
    {"slug": "meditacao", "title": "10 min de respiração guiada",
     "duration_min": 10, "energy": "baixa", "tags": ["mindfulness", "casa"]},
    {"slug": "boardgame", "title": "Jogo de tabuleiro com amigos",
     "duration_min": 90, "energy": "media", "tags": ["social", "casa", "games"]},
    {"slug": "parque", "title": "Vá a um parque",
     "duration_min": 60, "energy": "media", "tags": ["ar-livre", "familia"]},
    {"slug": "podcast", "title": "Ouça um podcast fora de Medicina",
     "duration_min": 45, "energy": "baixa", "tags": ["audio", "casa", "rua"]},
    {"slug": "banho-quente", "title": "Banho quente + alongamento",
     "duration_min": 20, "energy": "baixa", "tags": ["autocuidado", "casa"]},
]


HOBBY_TO_TAGS = {
    "musica": ["musica"],
    "leitura": ["leitura"],
    "cinema": ["cinema"],
    "games": ["games"],
    "esporte": ["fisico"],
    "arte": ["arte"],
    "culinaria": ["culinaria"],
    "amigos": ["social"],
    "familia": ["familia"],
    "natureza": ["ar-livre"],
    "meditacao": ["mindfulness"],
    "escrita": ["autoconhecimento"],
}


@router.get("/leisure/suggestions")
async def leisure_suggestions(
    user: dict = Depends(require_user),
    max_minutes: Optional[int] = Query(default=None, description="Tempo disponível em min"),
    energy: Optional[str] = Query(default=None, description="baixa | media | alta"),
) -> dict:
    profile = await get_profile_doc(user["user_id"])
    hobbies = [str(h).lower() for h in (profile.get("hobbies") or [])]
    wanted_tags = set()
    for h in hobbies:
        wanted_tags.update(HOBBY_TO_TAGS.get(h, [h]))

    # CMS entries appended to base library
    cms_items = await db.cms_leisure.find({}, {"_id": 0}).to_list(200)
    items = list(LEISURE_LIBRARY) + [
        {"slug": c.get("slug") or c.get("id"), "title": c.get("title"),
         "duration_min": c.get("duration_min"), "energy": c.get("energy"),
         "tags": c.get("tags") or []}
        for c in cms_items
    ]

    def score(item: dict) -> int:
        s = 0
        if wanted_tags & set(item["tags"]):
            s += 5
        if max_minutes and item["duration_min"] <= max_minutes:
            s += 3
        if energy and item["energy"] == energy:
            s += 2
        return s

    ranked = sorted(items, key=score, reverse=True)
    if max_minutes:
        ranked = [i for i in ranked if i["duration_min"] <= max_minutes] or ranked
    if energy:
        ranked = [i for i in ranked if i["energy"] == energy] or ranked

    return {
        "hobbies": hobbies,
        "suggestions": ranked[:10],
    }
