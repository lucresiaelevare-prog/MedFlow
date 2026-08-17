"""Experience layer — capabilities, tour, minimal onboarding e "Home Inteligente".

Filosofia: capabilities-first (não layer-first).
Layer é consequência, não causa.

- capability_state: cada feature tem status {locked | available | enabled}
  - locked: usuário nem sabe que existe
  - available: pode ser desbloqueada (aparece no "descubra")
  - enabled: usuário já vê/usa

- home_layout: "smart" | "control_center"
  - smart: /hoje — 1 recomendação + 1 botão + observação
  - control_center: /dashboard antigo (tudo)

- tour_pending: True para usuários que existiam antes desta iteração.

Endpoints:
  GET  /api/experience/state
  POST /api/experience/tour-complete
  POST /api/experience/onboarding-minimal
  GET  /api/home/today
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import _now, _today_str, db, require_user
from decision_engine import (
    _recommend_from_priority,  # noqa: F401 — legado exposto para testes
    _last_checkin,
    _least_studied_subject_7d,
    _pomodoro_route,
    _build_why_signals,
    _compose_why_now,
    _decide_next_action,
)

logger = logging.getLogger("medflow.experience")
router = APIRouter(prefix="/api", tags=["experience"])


# ─── Capabilities catalog ────────────────────────────────────────
# Order matters — used in the UI "discover" list.
CAPABILITIES = [
    # (slug, label, description, always_on)
    ("smart_home", "Home Inteligente", "Uma decisão por dia.", True),
    ("exam_mode", "Modo Prova", "Quando você tem prova chegando.", True),
    ("checkin", "Check-in diário", "Como você está hoje.", True),
    ("mental_health_signal", "Sinal de bem-estar", "Detecção precoce em texto livre.", True),
    ("tutor_ai", "Tutor IA", "Feedback de provas com IA.", True),
    ("study_rhythm", "Ritmo de estudos", "Aparece após 3 sessões de foco.", False),
    ("pillars", "Pilares", "Aparece após 5 check-ins + 3 focos.", False),
    ("coach_weekly", "Coach semanal", "Aparece após 7 check-ins.", False),
    ("analytics", "Analytics", "Aparece após 7 dias de dados.", False),
    ("google_calendar", "Google Calendar", "Sincronização (em breve).", False),
    ("community", "Comunidade", "Publicações e apoio entre pares.", False),
]


async def _compute_capabilities(user_id: str) -> tuple[dict, dict]:
    """Retorna (capabilities dict, stats dict). Regras baseadas em dados históricos."""
    today = _today_str()
    since_7d = (_now() - timedelta(days=7)).isoformat()

    pomodoros_completed = await db.pomodoro_sessions.count_documents(
        {"user_id": user_id, "status": "completed"}
    )
    checkins_total = await db.checkins.count_documents({"user_id": user_id})
    checkins_7d = await db.checkins.count_documents(
        {"user_id": user_id, "created_at": {"$gte": since_7d}}
    )
    care_actions = await db.care_logs.count_documents({"user_id": user_id})

    # Distinct dias com atividade nos últimos 30 dias
    since_30d = (_now() - timedelta(days=30)).isoformat()
    active_dates: set[str] = set()
    async for c in db.checkins.find(
        {"user_id": user_id, "created_at": {"$gte": since_30d}},
        {"_id": 0, "created_at": 1},
    ):
        try:
            active_dates.add(c["created_at"][:10])
        except Exception:
            pass
    async for p in db.pomodoro_sessions.find(
        {"user_id": user_id, "status": "completed"},
        {"_id": 0, "date": 1},
    ):
        d = p.get("date")
        if d:
            active_dates.add(d)
    days_active = len(active_dates)

    stats = {
        "pomodoros_completed": pomodoros_completed,
        "checkins_total": checkins_total,
        "checkins_7d": checkins_7d,
        "care_actions": care_actions,
        "days_active": days_active,
    }

    def state(unlocked: bool, enabled_by_default: bool = True) -> str:
        if not unlocked:
            return "locked"
        return "enabled" if enabled_by_default else "available"

    caps: dict[str, str] = {}
    for slug, _label, _desc, always in CAPABILITIES:
        if slug in ("smart_home", "exam_mode", "checkin", "mental_health_signal", "tutor_ai"):
            caps[slug] = "enabled"
        elif slug == "study_rhythm":
            caps[slug] = state(pomodoros_completed >= 3)
        elif slug == "pillars":
            caps[slug] = state(checkins_total >= 5 and pomodoros_completed >= 3)
        elif slug == "coach_weekly":
            caps[slug] = state(checkins_total >= 7)
        elif slug == "analytics":
            caps[slug] = state(days_active >= 7)
        elif slug == "google_calendar":
            caps[slug] = "locked"  # unlocked when the integration ships
        elif slug == "community":
            caps[slug] = "locked"  # audit: hidden until critical mass
        else:
            caps[slug] = "available"
    return caps, stats


def _capability_catalog() -> list[dict]:
    return [
        {"slug": s, "label": lbl, "description": desc}
        for s, lbl, desc, _ in CAPABILITIES
    ]


# ─── State ─────────────────────────────────────────────────────
async def _get_or_init_profile(user_id: str) -> dict:
    prof = await db.user_profiles.find_one({"user_id": user_id}, {"_id": 0}) or {}
    return prof


async def _consistency_snapshot(user_id: str) -> dict:
    """Resume atividade recente para a interface, sem influenciar decisões."""
    since = (_now() - timedelta(days=4)).isoformat()
    active_dates: set[str] = set()
    async for checkin in db.checkins.find(
        {"user_id": user_id, "created_at": {"$gte": since}},
        {"_id": 0, "created_at": 1},
    ):
        if checkin.get("created_at"):
            active_dates.add(str(checkin["created_at"])[:10])
    async for session in db.pomodoro_sessions.find(
        {"user_id": user_id, "status": "completed", "created_at": {"$gte": since}},
        {"_id": 0, "date": 1, "created_at": 1},
    ):
        date = session.get("date") or str(session.get("created_at") or "")[:10]
        if date:
            active_dates.add(str(date)[:10])
    return {"active_days_last5": len(active_dates), "window_days": 5}


def _summary_action(item: dict, typical_min: int) -> dict | None:
    """Traduz somente itens já priorizados em uma ação legível no resumo."""
    if item.get("kind") == "exam":
        return {
            "id": item.get("id"),
            "title": f"Revisar {item.get('title')}",
            "duration_min": max(30, typical_min),
            "action_route": "/subjects",
            "action_label": "Ver prova",
        }
    if item.get("kind") == "block" and not item.get("done"):
        return {
            "id": item.get("id"),
            "title": item.get("title") or "Bloco de estudo",
            "duration_min": typical_min,
            "action_route": "/pomodoro",
            "action_label": "Começar",
        }
    if item.get("kind") == "mission" and not item.get("completed"):
        return {
            "id": item.get("id"),
            "title": item.get("title") or "Missão de estudo",
            "duration_min": int(item.get("minutes") or typical_min),
            "action_route": "/pomodoro",
            "action_label": "Começar",
        }
    return None


def _today_summary(recommendation: dict, items: list[dict], typical_min: int) -> dict:
    """Agrupa no máximo três ações já existentes; não cria nova prioridade."""
    actions = [{
        "id": recommendation.get("id"),
        "title": recommendation.get("title") or "Sua próxima ação",
        "duration_min": int(recommendation.get("duration_min") or typical_min),
        "action_route": recommendation.get("action_route") or "/dashboard",
        "action_label": recommendation.get("action_label") or "Começar",
    }]
    action_ids = {str(actions[0].get("id") or "")}
    titles = {actions[0]["title"].strip().lower()}
    for item in items:
        action = _summary_action(item, typical_min)
        action_id = str(action.get("id") or "")
        if action is None or action_id in action_ids or action["title"].strip().lower() in titles:
            continue
        actions.append(action)
        action_ids.add(action_id)
        titles.add(action["title"].strip().lower())
        if len(actions) == 3:
            break
    return {
        "actions": actions,
        "estimated_minutes": sum(int(action["duration_min"]) for action in actions),
    }


@router.get("/experience/state")
async def experience_state(user: dict = Depends(require_user)) -> dict:
    user_id = user["user_id"]
    prof = await _get_or_init_profile(user_id)
    caps, stats = await _compute_capabilities(user_id)

    minimal_done = bool(prof.get("minimal_onboarding_done"))
    # tour_pending default: True for pre-existing users (any data + no explicit choice yet)
    tour_choice = prof.get("home_layout")  # "smart" | "control_center" | None
    tour_completed = bool(prof.get("tour_completed"))
    has_any_history = stats["days_active"] > 0 or stats["checkins_total"] > 0

    tour_pending = (not tour_completed) and has_any_history and (tour_choice is None)

    # Home layout default:
    #   - novos usuários (minimal_done ainda False): "smart"
    #   - existentes sem escolha: "control_center" (comportamento antigo preservado)
    if tour_choice in ("smart", "control_center"):
        home_layout = tour_choice
    elif not has_any_history:
        home_layout = "smart"
    else:
        home_layout = "control_center"

    return {
        "capabilities": caps,
        "stats": stats,
        "home_layout": home_layout,
        "tour_pending": tour_pending,
        "minimal_onboarding_done": minimal_done,
        "catalog": _capability_catalog(),
        "minimal": {
            "period": prof.get("period_number"),
            "faculty": prof.get("faculty"),
            "typical_study_min": prof.get("typical_study_min"),
        },
    }


class TourCompleteIn(BaseModel):
    home_layout: str = Field(pattern="^(smart|control_center)$")


@router.post("/experience/tour-complete")
async def tour_complete(body: TourCompleteIn, user: dict = Depends(require_user)) -> dict:
    await db.user_profiles.update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "home_layout": body.home_layout,
            "tour_completed": True,
            "tour_completed_at": _now().isoformat(),
        }, "$setOnInsert": {"user_id": user["user_id"]}},
        upsert=True,
    )
    return {"ok": True, "home_layout": body.home_layout}


@router.get("/experience/tour-preview")
async def tour_preview(user: dict = Depends(require_user)) -> dict:
    """Snapshot honesto do histórico do usuário para o WelcomeTour.

    Serve o "aha moment": mostra que o app já observou padrões reais.
    - Se houver dado suficiente (>=3 dias ativos): retorna uma observação
      concreta detectada pelo mesmo motor da Home Inteligente.
    - Caso contrário: modo "learning" (nunca inventa).
    """
    user_id = user["user_id"]
    _caps, stats = await _compute_capabilities(user_id)
    observation = await _observation(user_id, stats)

    # Humor médio dos últimos 30 dias (só usado se >=3 registros)
    since_30d_iso = (_now() - timedelta(days=30)).isoformat()
    moods: list[int] = []
    async for c in db.checkins.find(
        {"user_id": user_id, "created_at": {"$gte": since_30d_iso}},
        {"_id": 0, "mood": 1},
    ):
        try:
            moods.append(int(c["mood"]))
        except Exception:
            pass
    avg_mood = round(sum(moods) / len(moods), 1) if len(moods) >= 3 else None

    if observation:
        mode = "observed"
        text = observation["text"]
        rule = observation["rule"]
        evidence = observation["evidence"]
    elif stats["checkins_total"] == 0 and stats["pomodoros_completed"] == 0:
        mode = "learning"
        text = "Ainda estou aprendendo como você estuda."
        rule = None
        evidence = None
    else:
        mode = "learning"
        text = "Ainda preciso de mais alguns dias pra perceber padrões."
        rule = None
        evidence = None

    return {
        "mode": mode,
        "text": text,
        "rule": rule,
        "evidence": evidence,
        "stats": {
            "pomodoros_completed": stats["pomodoros_completed"],
            "checkins_total": stats["checkins_total"],
            "days_active": stats["days_active"],
            "avg_mood": avg_mood,
        },
    }


class MinimalOnboardingIn(BaseModel):
    period_number: int = Field(ge=1, le=12)
    faculty: str = Field(min_length=1, max_length=120)
    typical_study_min: int = Field(ge=15, le=240)


@router.post("/experience/onboarding-minimal")
async def onboarding_minimal(
    body: MinimalOnboardingIn, user: dict = Depends(require_user)
) -> dict:
    user_id = user["user_id"]
    await db.user_profiles.update_one(
        {"user_id": user_id},
        {"$set": {
            "period_number": body.period_number,
            "faculty": body.faculty.strip(),
            "typical_study_min": body.typical_study_min,
            "minimal_onboarding_done": True,
            "minimal_onboarding_at": _now().isoformat(),
            "home_layout": "smart",  # novo usuário começa com smart home
        }, "$setOnInsert": {"user_id": user_id}},
        upsert=True,
    )
    return {"ok": True}


# ─── Home Inteligente: 1 recomendação + 1 observação ───────────────



async def _observation(user_id: str, stats: dict) -> dict | None:
    """Motor de observações — regra-baseada, evidência-obrigatória.

    Retorna a observação de maior prioridade dentre as detectadas, no formato:
        {
            "rule": "<slug>",
            "text": "<frase humana>",
            "evidence": {"explanation": "<como percebi>", "data": {...}},
            "priority": 1..10,
        }
    Se dados forem insuficientes ou nenhuma regra bater, retorna None.

    Todas as regras seguem o master-prompt.md:
    - Baseadas em dados reais.
    - Nunca inferem, nunca inventam, nunca motivacionais soltas.
    - Cada regra carrega sua evidência estruturada (transparência).
    """
    if stats["days_active"] < 3:
        return None

    candidates: list[dict] = []
    now = _now()
    since_7d_iso = (now - timedelta(days=7)).isoformat()
    since_14d_iso = (now - timedelta(days=14)).isoformat()

    # ─── Coleta de dados brutos (uma passagem por coleção) ────────
    pomodoros_7d: list[dict] = []
    async for p in db.pomodoro_sessions.find(
        {"user_id": user_id, "status": "completed", "created_at": {"$gte": since_7d_iso}},
        {"_id": 0, "created_at": 1, "subject_id": 1, "focused_minutes": 1, "date": 1},
    ):
        pomodoros_7d.append(p)

    pomodoros_14d_by_subject: Counter[str] = Counter()
    async for p in db.pomodoro_sessions.find(
        {"user_id": user_id, "status": "completed", "created_at": {"$gte": since_14d_iso}},
        {"_id": 0, "subject_id": 1, "focused_minutes": 1},
    ):
        sid = p.get("subject_id")
        if sid:
            pomodoros_14d_by_subject[sid] += int(p.get("focused_minutes") or 0)

    checkins_7d: list[dict] = []
    async for c in db.checkins.find(
        {"user_id": user_id, "created_at": {"$gte": since_7d_iso}},
        {"_id": 0, "created_at": 1, "mood": 1, "sleep": 1, "stress": 1},
    ).sort("created_at", 1):
        checkins_7d.append(c)

    # ─── Regra 1: Pico noturno de foco (P3) ────────────────────────
    hours = []
    for p in pomodoros_7d:
        try:
            hours.append(int(p["created_at"][11:13]))
        except Exception:
            pass
    if len(hours) >= 5:
        night = sum(1 for h in hours if 19 <= h <= 23)
        morning = sum(1 for h in hours if 6 <= h <= 11)
        if night / len(hours) >= 0.6:
            pct = round(night / len(hours) * 100)
            candidates.append({
                "rule": "peak_night_focus",
                "text": "Percebi que você costuma render mais depois das 19h.",
                "evidence": {
                    "explanation": f"{pct}% das suas {len(hours)} sessões de foco dos últimos 7 dias começaram entre 19h e 23h.",
                    "data": {"night_pct": round(night / len(hours), 2), "total_sessions": len(hours), "window_days": 7},
                },
                "priority": 3,
            })
        elif morning / len(hours) >= 0.6:
            pct = round(morning / len(hours) * 100)
            candidates.append({
                "rule": "peak_morning_focus",
                "text": "Percebi que você tem rendido bem no período da manhã.",
                "evidence": {
                    "explanation": f"{pct}% das suas {len(hours)} sessões de foco dos últimos 7 dias começaram entre 6h e 11h.",
                    "data": {"morning_pct": round(morning / len(hours), 2), "total_sessions": len(hours), "window_days": 7},
                },
                "priority": 3,
            })

    # ─── Regra 2: Matéria dominante (>40% do tempo em 7d) — P2 ─────
    times_7d: Counter[str] = Counter()
    for p in pomodoros_7d:
        sid = p.get("subject_id")
        if sid:
            times_7d[sid] += int(p.get("focused_minutes") or 0)
    total_7d = sum(times_7d.values())
    if total_7d >= 90 and times_7d:
        top_id, top_min = times_7d.most_common(1)[0]
        share = top_min / total_7d
        if share >= 0.4:
            subj = await db.subjects.find_one({"id": top_id, "user_id": user_id}, {"_id": 0, "name": 1})
            if subj:
                candidates.append({
                    "rule": "subject_dominant",
                    "text": f"Percebi que {subj['name']} está consumindo mais tempo do que suas outras matérias.",
                    "evidence": {
                        "explanation": f"{subj['name']} representou {round(share*100)}% ({top_min} min) do seu tempo de foco dos últimos 7 dias, contra {total_7d - top_min} min das demais matérias juntas.",
                        "data": {"subject_id": top_id, "subject_name": subj["name"], "share": round(share, 2), "top_min": top_min, "total_min": total_7d},
                    },
                    "priority": 2,
                })

    # ─── Regra 3: Matéria negligenciada (P4) ──────────────────────
    # Se existem >=2 matérias cadastradas e uma delas ficou <10% em 14d
    all_subjects: list[dict] = []
    async for s in db.subjects.find({"user_id": user_id}, {"_id": 0, "id": 1, "name": 1, "priority": 1}):
        all_subjects.append(s)
    total_14d = sum(pomodoros_14d_by_subject.values())
    if len(all_subjects) >= 2 and total_14d >= 120:
        neglected = None
        for s in all_subjects:
            mins = pomodoros_14d_by_subject.get(s["id"], 0)
            share = (mins / total_14d) if total_14d else 0
            if share < 0.10 and mins <= 30:
                # prioriza matéria com priority alta
                pri = str(s.get("priority") or "").lower()
                if pri in ("alta", "muito_alta", "critica") or neglected is None:
                    neglected = {"id": s["id"], "name": s["name"], "mins": mins, "share": share}
                    if pri in ("alta", "muito_alta", "critica"):
                        break
        if neglected:
            candidates.append({
                "rule": "subject_neglected",
                "text": f"Percebi que você não tem estudado {neglected['name']} há alguns dias.",
                "evidence": {
                    "explanation": f"Nos últimos 14 dias, {neglected['name']} recebeu apenas {neglected['mins']} min ({round(neglected['share']*100)}% do seu tempo total de foco).",
                    "data": {"subject_id": neglected["id"], "subject_name": neglected["name"], "mins_14d": neglected["mins"], "share": round(neglected["share"], 2)},
                },
                "priority": 4,
            })

    # ─── Regra 4: Consistência semanal (P1 se ≥3, P3 se ≥6) ────────
    checkins_count_7d = stats["checkins_7d"]
    if checkins_count_7d >= 6:
        candidates.append({
            "rule": "checkin_consistency_strong",
            "text": f"Você fez check-in em {checkins_count_7d} dos últimos 7 dias. Isso já me ajuda muito a te entender.",
            "evidence": {
                "explanation": f"Consistência forte: {checkins_count_7d} check-ins nos últimos 7 dias.",
                "data": {"checkins_7d": checkins_count_7d, "window_days": 7},
            },
            "priority": 3,
        })
    elif checkins_count_7d >= 3:
        candidates.append({
            "rule": "checkin_consistency_ok",
            "text": "Percebi que você tem sido consistente com os check-ins essa semana.",
            "evidence": {
                "explanation": f"{checkins_count_7d} check-ins nos últimos 7 dias.",
                "data": {"checkins_7d": checkins_count_7d, "window_days": 7},
            },
            "priority": 1,
        })

    # ─── Regra 5: Tendência de humor (P3 alta / P4 caiu) ───────────
    moods = []
    for c in checkins_7d:
        try:
            moods.append(int(c["mood"]))
        except Exception:
            pass
    if len(moods) >= 4:
        half = len(moods) // 2
        first = sum(moods[:half]) / half
        last = sum(moods[half:]) / (len(moods) - half)
        delta = round(last - first, 2)
        if delta >= 0.6:
            candidates.append({
                "rule": "mood_trend_up",
                "text": "Percebi que seu humor tem melhorado nos últimos dias.",
                "evidence": {
                    "explanation": f"Média de humor subiu de {round(first,1)} para {round(last,1)} nos últimos {len(moods)} check-ins (variação +{delta}).",
                    "data": {"first_half_avg": round(first, 2), "last_half_avg": round(last, 2), "delta": delta, "sample": len(moods)},
                },
                "priority": 3,
            })
        elif -delta >= 0.6:
            candidates.append({
                "rule": "mood_trend_down",
                "text": "Percebi que seu humor caiu um pouco. Vale um cuidado extra hoje.",
                "evidence": {
                    "explanation": f"Média de humor caiu de {round(first,1)} para {round(last,1)} nos últimos {len(moods)} check-ins (variação {delta}).",
                    "data": {"first_half_avg": round(first, 2), "last_half_avg": round(last, 2), "delta": delta, "sample": len(moods)},
                },
                "priority": 4,
            })

    # ─── Regra 6: Sono baixo consistente (P5 — bem-estar) ──────────
    sleep_low = [c for c in checkins_7d if c.get("sleep") is not None and int(c["sleep"]) <= 3]
    total_with_sleep = sum(1 for c in checkins_7d if c.get("sleep") is not None)
    if total_with_sleep >= 4 and len(sleep_low) >= 3:
        candidates.append({
            "rule": "low_sleep_pattern",
            "text": "Percebi que seu sono está baixo há alguns dias. Isso pode afetar sua concentração.",
            "evidence": {
                "explanation": f"Em {len(sleep_low)} dos seus últimos {total_with_sleep} check-ins com sono registrado, a nota ficou em 3 ou menos (escala 1–5).",
                "data": {"low_sleep_days": len(sleep_low), "sample": total_with_sleep},
            },
            "priority": 5,
        })

    # ─── Regra 7: Stress elevado recorrente (P5 — bem-estar) ───────
    stresses = [int(c["stress"]) for c in checkins_7d if c.get("stress") is not None]
    if len(stresses) >= 3:
        avg_stress = sum(stresses) / len(stresses)
        if avg_stress >= 6.5:
            candidates.append({
                "rule": "high_stress_pattern",
                "text": "Percebi que seu stress tem estado alto essa semana.",
                "evidence": {
                    "explanation": f"Média de stress dos seus últimos {len(stresses)} check-ins: {round(avg_stress,1)} (escala 0–10).",
                    "data": {"avg_stress": round(avg_stress, 2), "sample": len(stresses)},
                },
                "priority": 5,
            })

    # ─── Regra 8: Foco↔humor — dia após sessão longa (P3) ─────────
    # Se ao menos 2 dias tiveram foco >=30min E o humor médio nos dias seguintes é
    # significativamente maior que o baseline (média geral do período).
    days_with_focus: dict[str, int] = {}
    for p in pomodoros_7d:
        d = p.get("date") or (p.get("created_at") or "")[:10]
        if d:
            days_with_focus[d] = days_with_focus.get(d, 0) + int(p.get("focused_minutes") or 0)
    long_focus_days = [d for d, m in days_with_focus.items() if m >= 30]
    mood_by_day: dict[str, list[int]] = {}
    for c in checkins_7d:
        d = (c.get("created_at") or "")[:10]
        if d and c.get("mood") is not None:
            mood_by_day.setdefault(d, []).append(int(c["mood"]))
    if len(long_focus_days) >= 2 and len(mood_by_day) >= 3:
        baseline = sum(sum(v)/len(v) for v in mood_by_day.values()) / len(mood_by_day)
        next_moods: list[float] = []
        for d in long_focus_days:
            try:
                next_day = (datetime.fromisoformat(d) + timedelta(days=1)).date().isoformat()
            except Exception:
                continue
            if next_day in mood_by_day:
                next_moods.append(sum(mood_by_day[next_day]) / len(mood_by_day[next_day]))
        if len(next_moods) >= 2:
            next_avg = sum(next_moods) / len(next_moods)
            if next_avg - baseline >= 0.5:
                candidates.append({
                    "rule": "focus_boosts_next_day_mood",
                    "text": "Percebi que você tende a estar melhor no dia seguinte a sessões longas de foco.",
                    "evidence": {
                        "explanation": f"Em {len(long_focus_days)} dias com 30+ min de foco, seu humor médio no dia seguinte foi {round(next_avg,1)}, contra baseline {round(baseline,1)} (+{round(next_avg-baseline,1)}).",
                        "data": {"long_focus_days": len(long_focus_days), "next_day_avg": round(next_avg,2), "baseline_avg": round(baseline,2)},
                    },
                    "priority": 3,
                })

    # ─── Seleção: maior prioridade vence; empate → primeira registrada ───
    if not candidates:
        return None
    candidates.sort(key=lambda c: c["priority"], reverse=True)
    return candidates[0]


# ═════════════════════════════════════════════════════════════════
# MOTOR DE DECISÃO — P0.2
#
# Filosofia (ver /app/docs/master-prompt.md):
#   Nunca duas prioridades concorrentes. Sempre UMA decisão.
#   Observações INFLUENCIAM diretamente (não são só informativas).
#   Cada decisão carrega evidência (transparência).
#
# Sinais considerados (todos existentes hoje):
#   - Último check-in: mood, sleep, stress, energy
#   - Observação atual (rule + priority) do _observation()
#   - Priorização (provas, blocos, missões) via /priority/today
#   - Sequência (streak)
#   - Matérias negligenciadas (via obs.subject_neglected)
#   - Contexto do dia: hora local, check-in feito hoje?
#
# Retorna sempre um objeto único (nunca lista) com:
#   { rule, action, title, subtitle, reasoning, duration_min,
#     action_route, action_label, evidence, priority, kind (compat) }
# ═════════════════════════════════════════════════════════════════









@router.get("/home/today")
async def home_today(user: dict = Depends(require_user)) -> dict:
    user_id = user["user_id"]
    prof = await _get_or_init_profile(user_id)
    declared_typical_min = int(prof.get("typical_study_min") or 45)

    # P0.2.1.7 — Calibração viva do typical_study_min.
    # O que o aluno declarou no onboarding pode divergir do que ele sustenta.
    # Se houver >=3 sessões concluídas, usa o ritmo aprendido; senão, declarado.
    import efficacy as _efficacy
    typical_min = await _efficacy.get_effective_typical_min(user_id, declared_typical_min)

    # Reaproveita /priority/today logic
    from routes.priority import priority_today  # local import to avoid cycles
    try:
        prio = await priority_today(user=user)
        items = prio.get("items", [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("priority fallback: %s", exc)
        items = []

    # Check-in de hoje?
    has_checkin_today = bool(await db.checkins.count_documents(
        {"user_id": user_id, "created_at": {"$regex": f"^{_today_str()}"}}
    ))

    caps, stats = await _compute_capabilities(user_id)
    observation = await _observation(user_id, stats)

    # Motor de decisão P0.2: uma decisão única, com evidência e prioridade.
    # Observações influenciam diretamente (P5–P4 vêm de padrões observados).
    recommendation = await _decide_next_action(
        user_id=user_id,
        stats=stats,
        observation=observation,
        items=items,
        typical_min=typical_min,
        has_checkin_today=has_checkin_today,
    )

    # ─── P0.2.1 — Memória de Eficácia ─────────────────────────────
    # Ajusta a decisão base pelo histórico deste aluno (nunca invasivo),
    # adiciona `confidence`, e persiste o evento para futura aprendizagem.
    context = await _efficacy.snapshot_context(user_id)
    recommendation = await _efficacy.adjust_by_efficacy(user_id, recommendation, context)
    rec_id = await _efficacy.persist_recommendation(user_id, recommendation, context)
    recommendation["id"] = rec_id

    # ─── ITER14 — Motor VISÍVEL — traduz sinais em linguagem humana ────
    # Torna explícito o que o motor observou (ninguém percebe cérebro invisível).
    recommendation["why_signals"] = _build_why_signals(recommendation, context)
    recommendation["why_now"] = _compose_why_now(recommendation)
    summary = _today_summary(recommendation, items, typical_min)
    consistency = await _consistency_snapshot(user_id)

    # Bloco "O que percebi" — dois modos honestos:
    #   - "observed": traz um padrão real detectado (renderiza com label "O que percebi.")
    #   - "learning": admite que ainda não sabe. Frase única e curta,
    #                 sem análise forçada, sem preencher vazio com IA.
    if observation:
        noticed = {
            "mode": "observed",
            "text": observation["text"],
            "rule": observation["rule"],
            "evidence": observation["evidence"],
        }
    else:
        noticed = {
            "mode": "learning",
            "text": "Ainda estou aprendendo sobre sua rotina.",
            "hint": "Continue registrando seus dias.",
            "rule": None,
            "evidence": None,
        }

    # Saudação humana por horário local (assume UTC-3 Brasil)
    local_hour = (_now().hour - 3) % 24
    if 5 <= local_hour < 12:
        greeting = "Bom dia"
    elif 12 <= local_hour < 18:
        greeting = "Boa tarde"
    else:
        greeting = "Boa noite"

    # Modo Prova: link sempre visível
    has_upcoming_exam = False
    try:
        from datetime import timedelta as _td
        cutoff = (_now().date() + _td(days=14)).isoformat()
        has_upcoming_exam = bool(await db.exams.find_one(
            {"user_id": user_id, "exam_date": {"$gte": _today_str(), "$lte": cutoff}}
        ))
    except Exception:
        pass

    # ─── P0.1 (2026-02) — Reordenação automática por fadiga/saturação ───
    # Se saturação/fadiga forem detectadas, o motor GERA (silenciosamente)
    # uma proposta de reordenação da tarde e retorna no payload. UI decide
    # o que fazer. Idempotente por dia (não gera 2x).
    reschedule = None
    try:
        import reschedule_engine as _resched
        existing = await _resched.get_today_reschedule(user_id)
        if existing:
            reschedule = existing
        else:
            proposal = await _resched.build_proposal(user_id)
            if proposal.get("needed"):
                reschedule = await _resched.save_pending(user_id, proposal)
    except Exception as exc:  # noqa: BLE001
        logger.warning("reschedule preview failed: %s", exc)

    return {
        "date": _today_str(),
        "greeting": greeting,
        "has_checkin_today": has_checkin_today,
        "recommendation": recommendation,
        "summary": summary,
        "consistency": consistency,
        "noticed": noticed,
        "exam_mode": {
            "available": True,
            "has_upcoming": has_upcoming_exam,
        },
        "reschedule": reschedule,
        "stats": stats,
    }
