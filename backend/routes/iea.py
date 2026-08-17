"""IEA (Índice de Equilíbrio Acadêmico), streak and badges.

Analytics-only routes. Shared helpers `compute_pillars`, `iea_from_pillars`,
`current_streak` and `maybe_award_badges` are used by other route modules
(missions/check-in) — keep them here as the single source of truth.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends

from core import _iso, _now, db, require_user

router = APIRouter(prefix="/api", tags=["iea"])

# ---------------------------------------------------------------------------
# Pillars — canonical definitions used across the app
# ---------------------------------------------------------------------------
PILLARS = ["estudos", "sono", "saude_fisica", "bem_estar", "social"]
PILLAR_LABELS = {
    "estudos": "Estudos",
    "sono": "Sono",
    "saude_fisica": "Saúde Física",
    "bem_estar": "Bem-estar",
    "social": "Social",
}
PILLAR_EMOJI = {
    "estudos": "📚",
    "sono": "😴",
    "saude_fisica": "🏃",
    "bem_estar": "🧠",
    "social": "🤝",
}
CATEGORY_TO_PILLAR = {
    "aula": "estudos",
    "estudo": "estudos",
    "movimento": "saude_fisica",
    "descanso": "sono",
    "alimentacao": "saude_fisica",
    "bemestar": "bem_estar",
    "social": "social",
    "admin": "estudos",
}


async def compute_pillars(user_id: str) -> dict:
    """Compute pillar scores 0..100 across last ~3 days."""
    since = _now() - timedelta(days=3)
    since_iso = _iso(since)

    # Sono: from checkins (last 3 days average)
    checkins = await db.checkins.find(
        {"user_id": user_id, "created_at": {"$gte": since_iso}}, {"_id": 0}
    ).to_list(50)
    if checkins:
        avg_sleep = sum(c.get("sleep_hours", 7) for c in checkins) / len(checkins)
        sono = max(0, min(100, round(100 - abs(avg_sleep - 7.5) * 15)))
    else:
        sono = 60

    # Bem-estar: mood_logs + last checkin mood/stress
    mood_logs = await db.mood_logs.find(
        {"user_id": user_id, "created_at": {"$gte": since_iso}}, {"_id": 0}
    ).to_list(200)
    mood_vals = [m["value"] for m in mood_logs]
    if checkins:
        mood_vals.extend(c.get("mood", 3) for c in checkins)
    stress_vals = [c.get("stress", 3) for c in checkins]
    if mood_vals or stress_vals:
        mood_score = (sum(mood_vals) / len(mood_vals)) * 20 if mood_vals else 60
        stress_score = (5 - (sum(stress_vals) / len(stress_vals))) * 20 if stress_vals else 60
        bem_estar = round((mood_score + stress_score) / 2)
    else:
        bem_estar = 60
    bem_estar = max(0, min(100, bem_estar))

    # Missions in last 3 days → estudos, saude_fisica, social
    bundles = await db.missions_bundles.find(
        {"user_id": user_id, "created_at": {"$gte": since_iso}}, {"_id": 0}
    ).to_list(20)

    pillar_counts: dict[str, dict[str, int]] = {p: {"done": 0, "decided": 0} for p in PILLARS}
    for b in bundles:
        for m in b.get("missions", []):
            pillar = CATEGORY_TO_PILLAR.get(m.get("category", "admin"), "estudos")
            decided = bool(m.get("completed") or m.get("skipped"))
            if decided:
                pillar_counts[pillar]["decided"] += 1
                if m.get("completed"):
                    pillar_counts[pillar]["done"] += 1

    def _pct(p):
        c = pillar_counts[p]
        if c["decided"] == 0:
            return 60  # neutral fallback
        return max(0, min(100, round((c["done"] / c["decided"]) * 100)))

    return {
        "estudos": _pct("estudos"),
        "sono": sono,
        "saude_fisica": _pct("saude_fisica"),
        "bem_estar": bem_estar,
        "social": _pct("social"),
    }


def iea_from_pillars(pillars: dict) -> tuple[int, str]:
    weakest = min(pillars, key=pillars.get)
    return pillars[weakest], weakest


async def compute_pillar_presence(user_id: str) -> dict:
    """Diz, por pilar, se há dado REAL do aluno (últimos ~3 dias).

    Usado apenas pelo endpoint voltado ao aluno para nunca apresentar um
    score/diagnóstico que pareça medido sem base real. Não altera o
    `compute_pillars` (que mantém neutro=60 para uso interno de prompts/badges).
    """
    since_iso = _iso(_now() - timedelta(days=3))

    checkins_3d = await db.checkins.count_documents(
        {"user_id": user_id, "created_at": {"$gte": since_iso}}
    )
    moods_3d = await db.mood_logs.count_documents(
        {"user_id": user_id, "created_at": {"$gte": since_iso}}
    )

    bundles = await db.missions_bundles.find(
        {"user_id": user_id, "created_at": {"$gte": since_iso}}, {"_id": 0}
    ).to_list(20)
    decided = {p: 0 for p in PILLARS}
    for b in bundles:
        for m in b.get("missions", []):
            pillar = CATEGORY_TO_PILLAR.get(m.get("category", "admin"), "estudos")
            if m.get("completed") or m.get("skipped"):
                decided[pillar] += 1

    return {
        "estudos": decided["estudos"] > 0,
        "sono": checkins_3d > 0,
        "saude_fisica": decided["saude_fisica"] > 0,
        "bem_estar": checkins_3d > 0 or moods_3d > 0,
        "social": decided["social"] > 0,
    }


async def current_streak(user_id: str) -> int:
    from datetime import datetime as _dt

    checkins = await db.checkins.find(
        {"user_id": user_id}, {"_id": 0, "created_at": 1}
    ).sort("created_at", -1).to_list(120)
    if not checkins:
        return 0
    dates = set()
    for c in checkins:
        ts = c["created_at"]
        if isinstance(ts, str):
            ts = _dt.fromisoformat(ts)
        dates.add(ts.date())
    today = _now().date()
    streak = 0
    cursor = today
    while cursor in dates:
        streak += 1
        cursor = cursor - timedelta(days=1)
    if streak == 0 and (today - timedelta(days=1)) in dates:
        cursor = today - timedelta(days=1)
        while cursor in dates:
            streak += 1
            cursor = cursor - timedelta(days=1)
    return streak


# ---------------------------------------------------------------------------
# Badges (gamification)
# ---------------------------------------------------------------------------
BADGE_CATALOG = [
    {"slug": "primeiro_passo", "title": "Primeiro passo", "description": "Fez seu primeiro check-in.",
     "icon": "sparkles", "color": "sage"},
    {"slug": "streak_3", "title": "Três dias", "description": "Três dias consecutivos com check-in.",
     "icon": "flame", "color": "terracotta"},
    {"slug": "streak_7", "title": "Uma semana", "description": "Sete dias consecutivos com check-in.",
     "icon": "flame", "color": "terracotta"},
    {"slug": "streak_30", "title": "Um mês", "description": "Trinta dias consecutivos com check-in.",
     "icon": "trophy", "color": "terracotta"},
    {"slug": "ieas_80", "title": "Equilibrado", "description": "IEA ≥ 80 hoje.",
     "icon": "target", "color": "sage"},
    {"slug": "estudo_hero", "title": "Maratona sã", "description": "10 missões de estudo concluídas.",
     "icon": "book-open", "color": "sage"},
    {"slug": "sono_guardian", "title": "Guardião do sono", "description": "Cinco noites com 7h+ de sono.",
     "icon": "moon", "color": "sage"},
    {"slug": "movimento_5", "title": "Em movimento", "description": "Cinco missões de saúde física concluídas.",
     "icon": "activity", "color": "sage"},
    {"slug": "mindful_5", "title": "Presente", "description": "Cinco sessões de mindfulness concluídas.",
     "icon": "wind", "color": "sage"},
    {"slug": "exam_warrior", "title": "Guerreiro de prova", "description": "Registrou nota após um Modo Prova.",
     "icon": "shield", "color": "terracotta"},
]


async def maybe_award_badges(user_id: str) -> None:
    awarded = {
        b["slug"]
        for b in await db.badges_earned.find(
            {"user_id": user_id}, {"_id": 0, "slug": 1}
        ).to_list(50)
    }

    async def award(slug: str) -> None:
        if slug in awarded:
            return
        await db.badges_earned.insert_one({
            "id": f"bg_{uuid.uuid4().hex[:10]}",
            "user_id": user_id, "slug": slug, "earned_at": _iso(_now()),
        })
        awarded.add(slug)

    if await db.checkins.count_documents({"user_id": user_id}) >= 1:
        await award("primeiro_passo")

    streak = await current_streak(user_id)
    if streak >= 3:
        await award("streak_3")
    if streak >= 7:
        await award("streak_7")
    if streak >= 30:
        await award("streak_30")

    pillars = await compute_pillars(user_id)
    iea, _ = iea_from_pillars(pillars)
    if iea >= 80:
        await award("ieas_80")

    bundles = await db.missions_bundles.find({"user_id": user_id}, {"_id": 0}).to_list(60)
    estudo_done = movimento_done = 0
    for b in bundles:
        for m in b.get("missions", []):
            if m.get("completed"):
                if m.get("category") in ("estudo", "aula"):
                    estudo_done += 1
                if m.get("category") in ("movimento", "alimentacao"):
                    movimento_done += 1
    if estudo_done >= 10:
        await award("estudo_hero")
    if movimento_done >= 5:
        await award("movimento_5")

    since = _now() - timedelta(days=30)
    good_sleep = await db.checkins.count_documents({
        "user_id": user_id, "created_at": {"$gte": _iso(since)}, "sleep_hours": {"$gte": 7}
    })
    if good_sleep >= 5:
        await award("sono_guardian")

    if await db.mindfulness_logs.count_documents({"user_id": user_id}) >= 5:
        await award("mindful_5")

    if await db.exams.count_documents({"user_id": user_id, "grade": {"$ne": None}}) >= 1:
        await award("exam_warrior")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/iea")
async def get_iea(user: dict = Depends(require_user)) -> dict:
    """Índice de Equilíbrio Acadêmico — voltado ao aluno.

    Regra de honestidade (P0): nenhum score, pilar ou diagnóstico é
    apresentado como medido sem dado real. Pilares sem histórico retornam
    `score: null` e `has_data: false`. Se nenhum pilar tem dado, `iea` é
    `null` e `has_data` do índice é `false` — o frontend mostra o estado
    "ainda aprendendo o seu ritmo".
    """
    scores = await compute_pillars(user["user_id"])
    presence = await compute_pillar_presence(user["user_id"])

    pillars_out = []
    real_scores: dict[str, int] = {}
    for p in PILLARS:
        has = bool(presence.get(p))
        score = scores[p] if has else None
        if has:
            real_scores[p] = scores[p]
        pillars_out.append({
            "key": p,
            "label": PILLAR_LABELS[p],
            "emoji": PILLAR_EMOJI[p],
            "score": score,
            "has_data": has,
        })

    if real_scores:
        iea = round(sum(real_scores.values()) / len(real_scores))
        weakest = min(real_scores, key=real_scores.get)
        has_data = True
    else:
        iea = None
        weakest = None
        has_data = False

    return {
        "iea": iea,
        "has_data": has_data,
        "weakest_pillar": weakest,
        "pillars": pillars_out,
    }


@router.get("/streak")
async def get_streak(user: dict = Depends(require_user)) -> dict:
    return {"streak": await current_streak(user["user_id"])}


# PODA iter14: endpoint /badges desabilitado — gamificação removida do escopo.
# `maybe_award_badges` continua sendo chamado por outros módulos e persiste
# em `badges_earned` — dados preservados para futuro uso analítico.
