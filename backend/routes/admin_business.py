"""Indicadores de gestão do MedFlow, separados da observabilidade técnica."""
from __future__ import annotations

from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ai_quota import limit_for
from core import _iso, _now, _today_str, db
from routes.admin import require_admin, require_technical_admin

router = APIRouter(prefix="/api/admin/business", tags=["admin-business"])


def _date_window(days: int) -> str:
    return _iso(_now() - timedelta(days=days))


async def _student_ids() -> list[str]:
    rows = await db.users.find(
        {"is_admin": {"$ne": True}},
        {"_id": 0, "user_id": 1},
    ).to_list(None)
    return [str(row["user_id"]) for row in rows if row.get("user_id")]


async def _last_activity_by_student() -> dict[str, str]:
    rows = await db.user_sessions.aggregate(
        [
            {"$group": {"_id": "$user_id", "last_access": {"$max": "$created_at"}}},
            {"$project": {"_id": 0, "user_id": "$_id", "last_access": 1}},
        ]
    ).to_list(None)
    return {str(row["user_id"]): str(row["last_access"]) for row in rows if row.get("user_id")}


@router.get("/overview")
async def business_overview(_: dict = Depends(require_admin)) -> dict:
    """Responde às cinco perguntas diárias sem simular receita ou dados ausentes."""
    import learning_memory as lm

    student_ids = await _student_ids()
    student_id_set = set(student_ids)
    activity = await _last_activity_by_student()
    active_cutoff_7d = _date_window(7)
    active_cutoff_30d = _date_window(30)
    active_students_7d = sum(
        1
        for user_id, value in activity.items()
        if user_id in student_id_set and value >= active_cutoff_7d
    )
    active_students_30d = sum(
        1
        for user_id, value in activity.items()
        if user_id in student_id_set and value >= active_cutoff_30d
    )
    today = _today_str()
    students_today = await db.users.count_documents(
        {"is_admin": {"$ne": True}, "created_at": {"$gte": f"{today}T00:00:00"}}
    )
    students_month = await db.users.count_documents(
        {"is_admin": {"$ne": True}, "created_at": {"$gte": _date_window(30)}}
    )
    students_week = await db.users.count_documents(
        {"is_admin": {"$ne": True}, "created_at": {"$gte": _date_window(7)}}
    )
    last_accesses = [
        value
        for user_id, value in activity.items()
        if user_id in student_id_set and value
    ]
    plan_rows = await db.users.aggregate(
        [
            {"$match": {"is_admin": {"$ne": True}}},
            {"$group": {"_id": "$subscription_plan", "count": {"$sum": 1}}},
        ]
    ).to_list(None)
    plans = {str(row["_id"] or "free"): int(row["count"]) for row in plan_rows}
    mission_completed = await db.mission_events.count_documents({"completed": True})
    learning_events = await db.student_content_events.count_documents({})
    checkins = await db.checkins.count_documents({})
    ai_rows = await db.ai_usage.aggregate(
        [
            {"$match": {"date": today}},
            {"$group": {"_id": "$kind", "count": {"$sum": "$count"}}},
        ]
    ).to_list(None)
    ai_usage = {str(row["_id"]): int(row["count"]) for row in ai_rows}
    memory_metrics = await lm.content_reuse_metrics()
    engine_metrics = lm.get_engine_metrics()
    circuit = engine_metrics["circuit_breaker"]
    health = "healthy"
    if circuit["state"] != "CLOSED":
        health = "attention"
    if engine_metrics["counters"]["llm_calls_failed"] > 0:
        health = "attention"
    alerts: list[dict] = []
    if health != "healthy":
        alerts.append({
            "level": "attention",
            "title": "IA precisa de atenção",
            "detail": "Houve falha recente ou indisponibilidade temporária na IA.",
        })
    if active_students_30d == 0 and student_ids:
        alerts.append({
            "level": "attention",
            "title": "Sem atividade recente",
            "detail": "Nenhum aluno teve sessão registrada nos últimos 30 dias.",
        })
    if memory_metrics.get("quarantined", 0):
        alerts.append({
            "level": "attention",
            "title": "Conteúdo em revisão",
            "detail": "Há conteúdo aguardando revisão antes de novo uso.",
        })
    recent_rows = await db.users.aggregate(
        [
            {"$match": {"is_admin": {"$ne": True}, "created_at": {"$gte": _date_window(7)}}},
            {"$project": {"day": {"$substrBytes": ["$created_at", 0, 10]}}},
            {"$group": {"_id": "$day", "new_students": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
    ).to_list(None)
    return {
        "growth": {
            "total_students": len(student_ids),
            "active_students": active_students_30d,
            "active_students_7d": active_students_7d,
            "active_students_30d": active_students_30d,
            "new_students_today": students_today,
            "new_students_7d": students_week,
            "new_students_30d": students_month,
            "last_access": {
                "latest_at": max(last_accesses) if last_accesses else None,
                "students_with_recorded_access": len(last_accesses),
            },
            "plans": {"free": plans.get("free", 0), "premium": plans.get("premium", 0)},
            "timeline": [
                {"date": row["_id"], "new_students": int(row["new_students"])}
                for row in recent_rows
            ],
        },
        "learning": {
            "completed_study_actions": mission_completed,
            "learning_interactions": learning_events,
            "checkins": checkins,
            "active_students": active_students_30d,
        },
        "revenue": {
            "connected": False,
            "message": "Receitas e assinaturas aparecerão aqui após a conexão de pagamentos.",
        },
        "ai": {
            "questions_today": ai_usage.get("tutor", 0),
            "plans_today": ai_usage.get("feedback", 0),
            "daily_limit": {
                "tutor": limit_for("tutor"),
                "feedback": limit_for("feedback"),
            },
            "health": health,
            "cache_reuse_ratio": memory_metrics.get("reuse_ratio", 0),
            "estimated_savings_usd": memory_metrics.get("estimated_usd_saved", 0),
        },
        "alerts": alerts,
        "updated_at": _iso(_now()),
    }


@router.get("/beta-intelligence")
async def beta_intelligence(_: dict = Depends(require_admin)) -> dict:
    """Relatório agregado de uso e confiança, sem expor alunos ou mudar decisões."""
    student_ids = set(await _student_ids())
    activity = await _last_activity_by_student()
    active_cutoff = _date_window(30)
    active_users = sum(
        1
        for user_id, last_access in activity.items()
        if user_id in student_ids and last_access >= active_cutoff
    )
    displayed = await db.recommendation_events.count_documents({"shown_at": {"$ne": None}})
    opened = await db.recommendation_events.count_documents({"started_at": {"$ne": None}})
    completed = await db.recommendation_events.count_documents({"completed_at": {"$ne": None}})
    rejected = await db.recommendation_events.count_documents({"abandoned_at": {"$ne": None}})
    why_expanded = await db.recommendation_events.count_documents({"why_expanded_at": {"$ne": None}})
    confidence_rows = await db.confidence_shadow_events.aggregate(
        [
            {"$group": {"_id": None, "average": {"$avg": "$confidence_level"}, "count": {"$sum": 1}}},
        ]
    ).to_list(1)
    confidence = confidence_rows[0] if confidence_rows else {}
    low_confidence = await db.confidence_shadow_events.aggregate(
        [
            {"$match": {"confidence_level": {"$lte": 2}}},
            {
                "$group": {
                    "_id": {"discipline": "$discipline", "topic": "$topic"},
                    "count": {"$sum": 1},
                    "average_confidence": {"$avg": "$confidence_level"},
                }
            },
            {"$sort": {"count": -1, "average_confidence": 1}},
            {"$limit": 5},
        ]
    ).to_list(5)
    shown_rate = round(opened / displayed, 3) if displayed else None
    why_rate = round(why_expanded / displayed, 3) if displayed else None
    insights: list[str] = []
    if displayed < 10:
        insights.append("Dados insuficientes para concluir como alunos reagem às recomendações.")
    elif shown_rate is not None:
        insights.append(
            f"{round(shown_rate * 100)}% das recomendações exibidas foram abertas pelo aluno."
        )
    if why_rate is not None and displayed >= 10:
        insights.append(
            f"{round(why_rate * 100)}% das recomendações exibidas tiveram o motivo expandido."
        )
    if confidence.get("count", 0) >= 5:
        insights.append(
            f"A confiança média observada é {round(float(confidence['average']), 2)} de 5."
        )
    return {
        "active_users": active_users,
        "recommendations": {
            "displayed": displayed,
            "opened": opened,
            "executed": completed,
            "rejected": rejected,
            "why_expanded": why_expanded,
            "open_rate": shown_rate,
            "why_expanded_rate": why_rate,
        },
        "confidence": {
            "average": round(float(confidence["average"]), 2) if confidence.get("average") else None,
            "sample_size": int(confidence.get("count") or 0),
            "low_confidence_topics": [
                {
                    "discipline": (row["_id"] or {}).get("discipline") or "Não informado",
                    "topic": (row["_id"] or {}).get("topic") or "Não informado",
                    "count": int(row["count"]),
                    "average_confidence": round(float(row["average_confidence"]), 2),
                }
                for row in low_confidence
            ],
        },
        "insights": insights,
        "observation_only": True,
        "updated_at": _iso(_now()),
    }


@router.get("/students")
async def business_students(
    search: str = "",
    university: str = "",
    period: Optional[int] = Query(default=None, ge=1, le=12),
    plan: str = "",
    status: str = "",
    _: dict = Depends(require_admin),
) -> dict:
    """Lista operacional filtrável sem métricas financeiras inventadas."""
    users = await db.users.find(
        {"is_admin": {"$ne": True}},
        {
            "_id": 0,
            "user_id": 1,
            "name": 1,
            "email": 1,
            "created_at": 1,
            "subscription_plan": 1,
            "access_blocked": 1,
        },
    ).to_list(500)
    profile_rows = await db.user_profiles.find(
        {},
        {
            "_id": 0,
            "user_id": 1,
            "university": 1,
            "curriculum_university": 1,
            "semester": 1,
            "period_number": 1,
        },
    ).to_list(500)
    profiles = {str(item["user_id"]): item for item in profile_rows if item.get("user_id")}
    activity = await _last_activity_by_student()
    active_cutoff = _date_window(30)
    normalized_search = search.strip().lower()
    rows: list[dict] = []
    for user in users:
        profile = profiles.get(str(user.get("user_id")), {})
        school = profile.get("university") or profile.get("curriculum_university") or "Não informado"
        student_period = profile.get("semester") or profile.get("period_number")
        last_access = activity.get(str(user.get("user_id")))
        student_status = "Ativo" if last_access and last_access >= active_cutoff else "Inativo"
        subscription = user.get("subscription_plan") or "free"
        searchable = f"{user.get('name', '')} {user.get('email', '')}".lower()
        if normalized_search and normalized_search not in searchable:
            continue
        if university and school != university:
            continue
        if period and student_period != period:
            continue
        if plan and subscription != plan:
            continue
        if status and student_status.lower() != status.lower():
            continue
        rows.append({
            "user_id": user["user_id"],
            "name": user.get("name") or "Sem nome",
            "email": user.get("email") or "Sem e-mail",
            "university": school,
            "period": student_period,
            "plan": subscription,
            "status": student_status,
            "access_blocked": bool(user.get("access_blocked")),
            "last_access": last_access,
            "created_at": user.get("created_at"),
        })
    rows.sort(key=lambda item: item.get("last_access") or "", reverse=True)
    universities = sorted({row["university"] for row in rows if row["university"] != "Não informado"})
    return {"students": rows, "filters": {"universities": universities}}


class StudentAdminUpdate(BaseModel):
    subscription_plan: Optional[Literal["free", "premium"]] = None
    access_blocked: Optional[bool] = None


@router.patch("/students/{user_id}")
async def update_business_student(
    user_id: str,
    payload: StudentAdminUpdate,
    _: dict = Depends(require_admin),
) -> dict:
    """Atualiza só plano e acesso, preservando dados e histórico de estudo."""
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Nenhuma alteração informada")
    result = await db.users.update_one(
        {"user_id": user_id, "is_admin": {"$ne": True}},
        {"$set": updates},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Aluno não encontrado")
    if updates.get("access_blocked"):
        await db.user_sessions.delete_many({"user_id": user_id})
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "password_hash": 0},
    )
    return {"student": user, "sessions_revoked": bool(updates.get("access_blocked"))}


@router.get("/students/{user_id}")
async def business_student_detail(user_id: str, _: dict = Depends(require_admin)) -> dict:
    user = await db.users.find_one(
        {"user_id": user_id, "is_admin": {"$ne": True}},
        {"_id": 0, "password_hash": 0},
    )
    if user is None:
        raise HTTPException(status_code=404, detail="Aluno não encontrado")
    profile = await db.user_profiles.find_one({"user_id": user_id}, {"_id": 0}) or {}
    progress = {
        "checkins": await db.checkins.count_documents({"user_id": user_id}),
        "study_actions": await db.student_content_events.count_documents({"user_id": user_id}),
        "missions_completed": await db.mission_events.count_documents(
            {"user_id": user_id, "completed": True}
        ),
        "ai_requests": await db.ai_usage.count_documents({"user_id": user_id}),
    }
    return {
        "student": user,
        "profile": {
            "university": profile.get("university") or profile.get("curriculum_university"),
            "period": profile.get("semester") or profile.get("period_number"),
            "mode": profile.get("mode"),
        },
        "progress": progress,
        "billing": {"connected": False, "message": "Sem integração de pagamentos conectada."},
    }


@router.get("/learning")
async def business_learning(_: dict = Depends(require_admin)) -> dict:
    import learning_memory as lm

    difficult = await lm.collective_difficulty(min_sample=3)
    frequent_topics = await db.student_content_events.aggregate(
        [
            {"$match": {"topic": {"$exists": True, "$ne": ""}}},
            {"$group": {"_id": "$topic", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 8},
        ]
    ).to_list(8)
    return {
        "difficult_topics": difficult[:8],
        "studied_topics": [
            {"topic": row["_id"], "count": int(row["count"])} for row in frequent_topics
        ],
        "total_interactions": await db.student_content_events.count_documents({}),
        "notice": "Indicadores agregados; nenhum aluno é classificado individualmente nesta tela.",
    }


class ContentItemCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    content_type: Literal["course", "module", "lesson", "simulation", "pdf"]
    url: Optional[str] = Field(default=None, max_length=500)
    parent_title: Optional[str] = Field(default=None, max_length=160)
    published: bool = True


class ContentVisibilityUpdate(BaseModel):
    published: bool


@router.get("/content")
async def business_content(_: dict = Depends(require_admin)) -> dict:
    items = await db.cms_resources.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    normalized = []
    for item in items:
        normalized.append({
            "id": item.get("id"),
            "title": item.get("title") or "Sem título",
            "content_type": item.get("content_type") or item.get("type") or "lesson",
            "parent_title": item.get("parent_title") or item.get("category"),
            "url": item.get("url"),
            "published": item.get("published", True),
            "created_at": item.get("created_at"),
        })
    return {
        "items": normalized,
        "resources": len(normalized),
        "learning_materials": await db.content_memory.count_documents({"status": "ACTIVE"}),
        "quarantined_materials": await db.content_memory.count_documents({"status": "QUARANTINED"}),
    }


@router.post("/content")
async def create_business_content(
    payload: ContentItemCreate,
    admin: dict = Depends(require_admin),
) -> dict:
    document = {
        "id": f"cnt_{__import__('uuid').uuid4().hex[:12]}",
        "title": payload.title.strip(),
        "content_type": payload.content_type,
        "parent_title": payload.parent_title.strip() if payload.parent_title else None,
        "url": payload.url.strip() if payload.url else None,
        "published": payload.published,
        "created_by": admin["user_id"],
        "created_at": _iso(_now()),
    }
    response_item = document.copy()
    await db.cms_resources.insert_one(document)
    return {"item": response_item}


@router.patch("/content/{content_id}/visibility")
async def update_content_visibility(
    content_id: str,
    payload: ContentVisibilityUpdate,
    _: dict = Depends(require_admin),
) -> dict:
    result = await db.cms_resources.update_one(
        {"id": content_id},
        {"$set": {"published": payload.published}},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Conteúdo não encontrado")
    return {"id": content_id, "published": payload.published}


@router.get("/wellness")
async def business_wellness(_: dict = Depends(require_admin)) -> dict:
    mood_rows = await db.checkins.aggregate(
        [
            {"$match": {"mood": {"$type": "number"}}},
            {"$group": {"_id": None, "average": {"$avg": "$mood"}, "count": {"$sum": 1}}},
        ]
    ).to_list(1)
    return {
        "checkins": await db.checkins.count_documents({}),
        "wellness_items": await db.cms_leisure.count_documents({}),
        "average_mood": round(float(mood_rows[0]["average"]), 2) if mood_rows else None,
        "recent_items": await db.cms_leisure.find({}, {"_id": 0}).sort("created_at", -1).to_list(8),
    }


@router.get("/settings")
async def business_settings(user: dict = Depends(require_admin)) -> dict:
    import os

    technical_access = bool(user.get("is_technical_admin"))
    return {
        "platform": {"name": "MedFlow", "beta_mode": True},
        "ai": {"enabled": True, "technical_status_available": technical_access},
        "emails": {"sender_configured": bool(os.environ.get("RESEND_API_KEY"))},
        "logs": {
            "sessions_last_24h": await db.user_sessions.count_documents(
                {"created_at": {"$gte": _date_window(1)}}
            ),
            "note": "Resumo operacional sem dados individuais.",
        },
    }


@router.get("/developer/overview")
async def developer_overview(_: dict = Depends(require_technical_admin)) -> dict:
    """Visão técnica reduzida, separada do painel de gestão diário."""
    import learning_memory as lm
    from mip.phase2_store import phase2_metrics

    return {
        "shadow_mode": await phase2_metrics(),
        "content_memory": await lm.content_reuse_metrics(),
        "engine": lm.get_engine_metrics(),
    }


# ─── Beta Controlado: ativação + adoção + retenção (somente leitura) ────────
async def _distinct_students(collection, filt: dict, student_set: set) -> set:
    ids = await getattr(db, collection).distinct("user_id", filt)
    return {str(i) for i in ids if i} & student_set


@router.get("/beta-metrics")
async def beta_metrics(_: dict = Depends(require_admin)) -> dict:
    """Instrumentação mínima do Beta Controlado (agregado, sem novos dados).

    - Ativação: funil login → onboarding → 1º check-in → 1º Preceptor → 1ª sessão.
    - Adoção: funil de recomendações (exibida → iniciada → concluída) + taxa.
    - Retenção: D+1 / D+3 / D+7 a partir da data de cadastro de cada aluno.

    Tudo derivado de coleções já persistidas. Endpoint read-only, admin-only.
    """
    from datetime import datetime as _dt, timezone as _tz

    students = await db.users.find(
        {"is_admin": {"$ne": True}}, {"_id": 0, "user_id": 1, "created_at": 1}
    ).to_list(None)
    student_set = {str(s["user_id"]) for s in students if s.get("user_id")}
    total = len(student_set)

    # ── Ativação (quantos alunos alcançaram cada marco) ──
    logged_in = await _distinct_students("user_sessions", {}, student_set)
    onboarded_rows = await db.user_profiles.distinct(
        "user_id", {"minimal_onboarding_done": True}
    )
    onboarded = {str(i) for i in onboarded_rows if i} & student_set
    checked_in = await _distinct_students("checkins", {}, student_set)
    used_preceptor = (
        await _distinct_students("ai_usage", {}, student_set)
        | await _distinct_students(
            "recommendation_events", {"started_at": {"$ne": None}}, student_set
        )
    )
    studied = (
        await _distinct_students("pomodoro_sessions", {}, student_set)
        | await _distinct_students("mission_events", {"completed": True}, student_set)
    )

    def _pct(n: int) -> float:
        return round(n / total, 3) if total else 0.0

    activation = {
        "total_students": total,
        "logged_in": {"count": len(logged_in), "rate": _pct(len(logged_in))},
        "onboarding_done": {"count": len(onboarded), "rate": _pct(len(onboarded))},
        "first_checkin": {"count": len(checked_in), "rate": _pct(len(checked_in))},
        "first_preceptor": {"count": len(used_preceptor), "rate": _pct(len(used_preceptor))},
        "first_study_session": {"count": len(studied), "rate": _pct(len(studied))},
    }

    # ── Adoção (funil de recomendações) ──
    base = {"user_id": {"$in": list(student_set)}} if student_set else {"user_id": "__none__"}
    shown = await db.recommendation_events.count_documents({**base, "shown_at": {"$ne": None}})
    started = await db.recommendation_events.count_documents({**base, "started_at": {"$ne": None}})
    completed = await db.recommendation_events.count_documents({**base, "completed_at": {"$ne": None}})
    abandoned = await db.recommendation_events.count_documents({**base, "abandoned_at": {"$ne": None}})
    adoption = {
        "recommendations_shown": shown,
        "recommendations_started": started,
        "recommendations_completed": completed,
        "recommendations_abandoned": abandoned,
        # Métrica estratégica principal: quantos alunos agiram após a recomendação.
        "adoption_rate": round(started / shown, 3) if shown else 0.0,
        "completion_rate": round(completed / shown, 3) if shown else 0.0,
    }

    # ── Retenção D+1 / D+3 / D+7 ──
    # Datas de atividade por aluno (retornou e fez algo).
    activity: dict[str, set] = {}

    def _add(uid: str, day: str) -> None:
        if uid in student_set and day:
            activity.setdefault(uid, set()).add(day[:10])

    async for c in db.checkins.find({}, {"_id": 0, "user_id": 1, "created_at": 1}):
        _add(str(c.get("user_id")), str(c.get("created_at") or ""))
    async for p in db.pomodoro_sessions.find({}, {"_id": 0, "user_id": 1, "created_at": 1}):
        _add(str(p.get("user_id")), str(p.get("created_at") or ""))
    async for a in db.ai_usage.find({}, {"_id": 0, "user_id": 1, "date": 1}):
        _add(str(a.get("user_id")), str(a.get("date") or ""))

    today = _now().date()
    windows = {"d1": 1, "d3": 3, "d7": 7}
    retention: dict[str, dict] = {}
    for label, n in windows.items():
        eligible = 0
        retained = 0
        for s in students:
            uid = str(s.get("user_id"))
            created = str(s.get("created_at") or "")
            if uid not in student_set or len(created) < 10:
                continue
            try:
                d0 = _dt.fromisoformat(created.replace("Z", "+00:00")).date()
            except Exception:
                continue
            target = d0 + timedelta(days=n)
            if target > today:
                continue  # janela ainda não fechou para este aluno
            eligible += 1
            if target.isoformat() in activity.get(uid, set()):
                retained += 1
        retention[label] = {
            "eligible": eligible,
            "retained": retained,
            "rate": round(retained / eligible, 3) if eligible else None,
        }

    return {
        "activation": activation,
        "adoption": adoption,
        "retention": retention,
        "notice": (
            "Agregado do Beta Controlado. Ativação/adoção/retenção derivadas de "
            "coleções já existentes; nenhum dado individual é exposto aqui."
        ),
        "updated_at": _iso(_now()),
    }
