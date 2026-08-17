"""Painel Administrativo + CMS.

- `is_admin` no usuário controla acesso; o 1º usuário criado no banco é
  promovido a admin automaticamente para uso em ambiente demo/dev.
- CMS: gerencia entradas dinâmicas de biblioteca de ócio + recursos curados.
- Coleta de dados: estatísticas de uso (usuários, check-ins, missões, agenda).
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_quota import limit_for
from core import _clean, _iso, _now, _today_str, db, require_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def require_admin(user: dict = Depends(require_user)) -> dict:
    if user.get("is_admin"):
        return user
    raise HTTPException(status_code=403, detail="Acesso restrito a administradores")


async def require_technical_admin(user: dict = Depends(require_user)) -> dict:
    """Protege observabilidade e diagnóstico sem expô-los a toda a operação."""
    if user.get("is_admin") and user.get("is_technical_admin"):
        return user
    raise HTTPException(status_code=403, detail="Acesso restrito à administração técnica")


# ---------------------------------------------------------------
# Estatísticas
# ---------------------------------------------------------------

@router.get("/stats")
async def stats(_: dict = Depends(require_admin)) -> dict:
    now = _now()
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)

    users_total = await db.users.count_documents({})
    users_last7 = await db.users.count_documents({"created_at": {"$gte": _iso(since_7d)}})
    users_last30 = await db.users.count_documents({"created_at": {"$gte": _iso(since_30d)}})
    checkins_total = await db.checkins.count_documents({})
    checkins_last7 = await db.checkins.count_documents({"created_at": {"$gte": _iso(since_7d)}})
    missions_generated = await db.missions_bundles.count_documents({})
    missions_completed = await db.mission_events.count_documents({"completed": True})
    agenda_blocks = await db.agenda_blocks.count_documents({})
    profiles = await db.user_profiles.count_documents({})
    usage_rows = await db.ai_usage.aggregate([
        {"$match": {"date": _today_str()}},
        {"$group": {"_id": "$kind", "count": {"$sum": "$count"}}},
    ]).to_list(10)
    usage = {row["_id"]: row["count"] for row in usage_rows}

    # Distribuição por modo
    mode_agg = await db.user_profiles.aggregate([
        {"$group": {"_id": "$mode", "count": {"$sum": 1}}}
    ]).to_list(20)

    return {
        "users": {"total": users_total, "last_7d": users_last7, "last_30d": users_last30},
        "profiles": profiles,
        "checkins": {"total": checkins_total, "last_7d": checkins_last7},
        "missions": {"bundles": missions_generated, "completed_events": missions_completed},
        "agenda_blocks": agenda_blocks,
        "modes": {row["_id"] or "rotina": row["count"] for row in mode_agg},
        "ai_usage": {
            "date": _today_str(),
            "tutor_messages": usage.get("tutor", 0),
            "feedback_generations": usage.get("feedback", 0),
            "tutor_limit": limit_for("tutor"),
            "feedback_limit": limit_for("feedback"),
        },
    }


@router.get("/users")
async def list_users(_: dict = Depends(require_admin), limit: int = 50) -> dict:
    users = await db.users.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"users": users}


class UserPlanIn(BaseModel):
    subscription_plan: Literal["free", "premium"]


@router.patch("/users/{user_id}/subscription-plan")
async def update_subscription_plan(
    user_id: str,
    payload: UserPlanIn,
    _: dict = Depends(require_admin),
) -> dict:
    result = await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"subscription_plan": payload.subscription_plan}},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Estudante não encontrado")
    return {"user_id": user_id, "subscription_plan": payload.subscription_plan}


# ---------------------------------------------------------------
# CMS — Biblioteca de ócio
# ---------------------------------------------------------------

class LeisureItemInput(BaseModel):
    title: str
    duration_min: int
    energy: str  # baixa | media | alta
    tags: list[str] = []


@router.post("/cms/leisure")
async def create_leisure(payload: LeisureItemInput, admin: dict = Depends(require_admin)) -> dict:
    doc = {
        "id": f"lz_{uuid.uuid4().hex[:10]}",
        "slug": f"custom-{uuid.uuid4().hex[:6]}",
        "title": payload.title,
        "duration_min": max(5, min(360, payload.duration_min)),
        "energy": payload.energy if payload.energy in ("baixa", "media", "alta") else "baixa",
        "tags": [t.lower().strip() for t in payload.tags if t.strip()],
        "created_by": admin["user_id"],
        "created_at": _iso(_now()),
    }
    await db.cms_leisure.insert_one(dict(doc))
    return {"item": _clean(doc)}


@router.get("/cms/leisure")
async def list_leisure(_: dict = Depends(require_admin)) -> dict:
    items = await db.cms_leisure.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"items": items}


@router.delete("/cms/leisure/{item_id}")
async def delete_leisure(item_id: str, _: dict = Depends(require_admin)) -> dict:
    await db.cms_leisure.delete_one({"id": item_id})
    return {"ok": True}


# ---------------------------------------------------------------
# CMS — Recursos
# ---------------------------------------------------------------

class ResourceItemInput(BaseModel):
    title: str
    type: str  # artigo|video|podcast|audio
    duration_min: int
    category: str
    pillar: str
    excerpt: Optional[str] = ""
    url: str


@router.post("/cms/resources")
async def create_resource(payload: ResourceItemInput, admin: dict = Depends(require_admin)) -> dict:
    doc = {
        "id": f"rs_{uuid.uuid4().hex[:10]}",
        "slug": f"cms-{uuid.uuid4().hex[:6]}",
        **payload.model_dump(),
        "created_by": admin["user_id"],
        "created_at": _iso(_now()),
    }
    await db.cms_resources.insert_one(dict(doc))
    return {"item": _clean(doc)}


@router.get("/cms/resources")
async def list_resources_cms(_: dict = Depends(require_admin)) -> dict:
    items = await db.cms_resources.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"items": items}


@router.delete("/cms/resources/{item_id}")
async def delete_resource(item_id: str, _: dict = Depends(require_admin)) -> dict:
    await db.cms_resources.delete_one({"id": item_id})
    return {"ok": True}


# ---------------------------------------------------------------
# Endpoint auxiliar público — retorna 200/403 para o frontend decidir
# se mostra o link para Admin.
# ---------------------------------------------------------------

@router.get("/whoami")
async def whoami(user: dict = Depends(require_user)) -> dict:
    return {
        "user_id": user["user_id"],
        "email": user.get("email"),
        "is_admin": bool(user.get("is_admin")),
        "is_technical_admin": bool(user.get("is_technical_admin")),
    }


# ---------------------------------------------------------------
# MedFlow Research — banco anonimizado de padrões de aprendizagem
# ---------------------------------------------------------------
# Filosofia:
#   - Nunca expõe user_id, email, nome. Apenas coortes agregadas.
#   - Nunca conclui — sugere HIPÓTESES para investigação humana.
#   - Cada hipótese carrega n (tamanho da amostra) e Δ (diferença observada).
#   - Se n < 3, o padrão nem aparece.
#
# Três produtos futuros previstos:
#   MedFlow Student → ajuda o aluno.
#   MedFlow Institution → ajuda faculdades a entender dificuldades dos alunos.
#   MedFlow Research → gera dados para pesquisas acadêmicas.

def _period_bucket(period: int | None) -> str:
    """Agrupa períodos em faixas grandes (anonimização por generalização)."""
    if period is None:
        return "não informado"
    try:
        p = int(period)
    except Exception:
        return "não informado"
    if p <= 2:
        return "básico (1–2)"
    if p <= 6:
        return "clínico (3–6)"
    if p <= 10:
        return "internato (7–10)"
    return "outros (11+)"


def _sleep_bucket(sleep: float | int | None) -> str:
    if sleep is None:
        return "sem_dado"
    s = float(sleep)
    if s <= 3:
        return "baixo"
    if s <= 6:
        return "médio"
    return "alto"


def _duration_bucket(mins: int | None) -> str:
    if mins is None:
        return "sem_dado"
    if mins <= 15:
        return "curta (≤15)"
    if mins <= 30:
        return "média (16–30)"
    if mins <= 60:
        return "longa (31–60)"
    return "extensa (60+)"


@router.get("/research/cohort")
async def research_cohort(_: dict = Depends(require_admin)) -> dict:
    """Coorte anonimizada — só distribuições agregadas.

    Nunca inclui user_id, email, nome. Faixas etárias/de período viram
    buckets grandes; matérias e universidades só entram como contagem.
    """
    # Perfis (apenas campos anonimizados)
    period_dist: dict[str, int] = {}
    chronotype_dist: dict[str, int] = {}
    focus_technique_dist: dict[str, int] = {}
    neurodivergent_count = 0
    living_alone_count = 0
    total_profiles = 0
    async for p in db.user_profiles.find(
        {},
        {
            "_id": 0,
            "semester": 1, "period_number": 1, "chronotype": 1,
            "focus_technique": 1, "is_neurodivergent": 1, "living_alone": 1,
        },
    ):
        total_profiles += 1
        period_dist[_period_bucket(p.get("semester") or p.get("period_number"))] = (
            period_dist.get(_period_bucket(p.get("semester") or p.get("period_number")), 0) + 1
        )
        c = p.get("chronotype") or "não informado"
        chronotype_dist[c] = chronotype_dist.get(c, 0) + 1
        f = p.get("focus_technique") or "não informado"
        focus_technique_dist[f] = focus_technique_dist.get(f, 0) + 1
        if p.get("is_neurodivergent"):
            neurodivergent_count += 1
        if p.get("living_alone"):
            living_alone_count += 1

    # Check-ins agregados (sem identificar quem)
    total_checkins = await db.checkins.count_documents({})
    sleep_dist: dict[str, int] = {}
    mood_sum = 0
    mood_n = 0
    stress_sum = 0
    stress_n = 0
    async for c in db.checkins.find(
        {}, {"_id": 0, "sleep_hours": 1, "sleep": 1, "mood": 1, "stress": 1}
    ):
        sh = c.get("sleep_hours") if c.get("sleep_hours") is not None else c.get("sleep")
        sleep_dist[_sleep_bucket(sh)] = sleep_dist.get(_sleep_bucket(sh), 0) + 1
        if c.get("mood") is not None:
            try:
                mood_sum += int(c["mood"]); mood_n += 1
            except Exception:
                pass
        if c.get("stress") is not None:
            try:
                stress_sum += int(c["stress"]); stress_n += 1
            except Exception:
                pass

    # Sessões de recomendação (comportamento agregado)
    total_recs = await db.recommendation_events.count_documents({})
    completed_recs = await db.recommendation_events.count_documents({"outcome": "completed"})
    abandoned_recs = await db.recommendation_events.count_documents({"outcome": "abandoned"})

    return {
        "population": {
            "total_users": await db.users.count_documents({}),
            "total_profiles": total_profiles,
            "neurodivergent_share": round(neurodivergent_count / total_profiles, 3) if total_profiles else 0,
            "living_alone_share": round(living_alone_count / total_profiles, 3) if total_profiles else 0,
        },
        "period_distribution": period_dist,
        "chronotype_distribution": chronotype_dist,
        "focus_technique_distribution": focus_technique_dist,
        "checkins": {
            "total": total_checkins,
            "sleep_distribution": sleep_dist,
            "avg_mood": round(mood_sum / mood_n, 2) if mood_n else None,
            "avg_stress": round(stress_sum / stress_n, 2) if stress_n else None,
        },
        "recommendations": {
            "total": total_recs,
            "completed": completed_recs,
            "abandoned": abandoned_recs,
            "completion_rate": round(completed_recs / total_recs, 3) if total_recs else 0,
        },
        "notice": (
            "Dados anonimizados: nenhuma coluna deste endpoint contém identificadores "
            "(sem user_id, email ou nome). Faixas etárias e períodos são generalizados "
            "em buckets amplos para preservar privacidade."
        ),
    }


@router.get("/research/hypotheses")
async def research_hypotheses(_: dict = Depends(require_admin)) -> dict:
    """Padrões observados no comportamento agregado — sempre como HIPÓTESE.

    Nunca conclusivo. Sempre acompanhado de:
      - `sample_size` (n)
      - `delta_pct` (diferença observada)
      - `confidence_level` ('exploratória' | 'sugestiva' | 'consistente')
      - `warning` (limitação metodológica reconhecida)

    O objetivo é gerar hipóteses para investigação humana subsequente
    (MedFlow Research / trabalhos acadêmicos), não substituir análise.
    """
    hypotheses: list[dict] = []

    # ─── Coleta bruta de events (uma única passagem) ────────────────
    events: list[dict] = []
    async for e in db.recommendation_events.find(
        {},
        {
            "_id": 0,
            "rule": 1, "priority": 1, "duration_planned_min": 1,
            "duration_actual_min": 1, "outcome": 1, "context": 1,
        },
    ):
        events.append(e)

    def _confidence(n: int) -> str:
        if n < 5:
            return "exploratória"
        if n < 20:
            return "sugestiva"
        return "consistente"

    # ─── H1: Sessões curtas após sono baixo → maior conclusão ──────
    short_low = [e for e in events
                 if _duration_bucket(e.get("duration_planned_min")) in ("curta (≤15)", "média (16–30)")
                 and _sleep_bucket((e.get("context") or {}).get("sleep")) == "baixo"]
    long_low = [e for e in events
                if _duration_bucket(e.get("duration_planned_min")) in ("longa (31–60)", "extensa (60+)")
                and _sleep_bucket((e.get("context") or {}).get("sleep")) == "baixo"]
    if len(short_low) >= 3 and len(long_low) >= 3:
        short_ok = sum(1 for e in short_low if e.get("outcome") == "completed") / len(short_low)
        long_ok = sum(1 for e in long_low if e.get("outcome") == "completed") / len(long_low)
        delta = short_ok - long_ok
        if abs(delta) >= 0.05:
            hypotheses.append({
                "id": "h_short_after_low_sleep",
                "title": "Sessões menores após baixa qualidade de sono",
                "statement": (
                    f"Estudantes que recebem sessões {'menores' if delta > 0 else 'maiores'} "
                    f"após noites de baixa qualidade de sono apresentam variação de "
                    f"{round(abs(delta)*100)}% na taxa de conclusão."
                ),
                "prompt": "Observamos um padrão. Isso poderia virar uma hipótese?",
                "sample": {"short_n": len(short_low), "long_n": len(long_low)},
                "delta_pct": round(delta * 100, 1),
                "confidence_level": _confidence(min(len(short_low), len(long_low))),
                "warning": "Amostra não controlada; correlação, não causalidade.",
            })

    # ─── H2: Regras clínicas (P5) — completude vs P<5 ────────────────
    clinical = [e for e in events if int(e.get("priority") or 0) >= 5]
    non_clinical = [e for e in events if int(e.get("priority") or 0) < 5]
    if len(clinical) >= 3 and len(non_clinical) >= 3:
        c_ok = sum(1 for e in clinical if e.get("outcome") == "completed") / len(clinical)
        n_ok = sum(1 for e in non_clinical if e.get("outcome") == "completed") / len(non_clinical)
        delta = c_ok - n_ok
        if abs(delta) >= 0.03:
            hypotheses.append({
                "id": "h_clinical_vs_regular",
                "title": "Aderência a recomendações clínicas vs regulares",
                "statement": (
                    f"Recomendações clínicas (bem-estar / P5) apresentam taxa de "
                    f"conclusão {round(abs(delta)*100)}% "
                    f"{'maior' if delta > 0 else 'menor'} que recomendações regulares."
                ),
                "prompt": "Observamos um padrão. Isso poderia virar uma hipótese?",
                "sample": {"clinical_n": len(clinical), "regular_n": len(non_clinical)},
                "delta_pct": round(delta * 100, 1),
                "confidence_level": _confidence(min(len(clinical), len(non_clinical))),
                "warning": "Reflete engajamento reportado — não desfecho clínico.",
            })

    # ─── H3: Duração ideal por bucket ──────────────────────────────
    bucket_stats: dict[str, dict] = {}
    for e in events:
        b = _duration_bucket(e.get("duration_planned_min"))
        d = bucket_stats.setdefault(b, {"total": 0, "completed": 0})
        d["total"] += 1
        if e.get("outcome") == "completed":
            d["completed"] += 1
    ranked = sorted(
        [(b, s["completed"] / s["total"], s["total"]) for b, s in bucket_stats.items() if s["total"] >= 3],
        key=lambda t: t[1], reverse=True,
    )
    if len(ranked) >= 2:
        top_b, top_rate, top_n = ranked[0]
        bot_b, bot_rate, bot_n = ranked[-1]
        delta = top_rate - bot_rate
        if delta >= 0.05:
            hypotheses.append({
                "id": "h_optimal_duration",
                "title": "Duração ideal de sessão",
                "statement": (
                    f"Sessões de duração {top_b} apresentam taxa de conclusão "
                    f"{round(delta*100)}% maior que sessões {bot_b}."
                ),
                "prompt": "Observamos um padrão. Isso poderia virar uma hipótese?",
                "sample": {"top_n": top_n, "bot_n": bot_n, "buckets_ranked": ranked},
                "delta_pct": round(delta * 100, 1),
                "confidence_level": _confidence(min(top_n, bot_n)),
                "warning": "Não considera diferenças individuais de cronotipo e carga.",
            })

    # ─── H4: Ritmo declarado vs sustentado ─────────────────────────
    declared: list[int] = []
    async for p in db.user_profiles.find({}, {"_id": 0, "typical_study_min": 1}):
        v = p.get("typical_study_min")
        if v:
            try:
                declared.append(int(v))
            except Exception:
                pass
    actual = [int(e["duration_actual_min"]) for e in events if e.get("outcome") == "completed" and e.get("duration_actual_min")]
    if len(declared) >= 3 and len(actual) >= 3:
        avg_dec = sum(declared) / len(declared)
        avg_act = sum(actual) / len(actual)
        delta = avg_act - avg_dec
        if abs(delta) >= 5:
            hypotheses.append({
                "id": "h_declared_vs_sustained",
                "title": "Ritmo declarado vs sustentado",
                "statement": (
                    f"A duração média de sessão sustentada ({round(avg_act)} min) "
                    f"é {round(abs(delta))} min {'menor' if delta < 0 else 'maior'} "
                    f"que a duração declarada em onboarding ({round(avg_dec)} min)."
                ),
                "prompt": "Observamos um padrão. Isso poderia virar uma hipótese?",
                "sample": {"declared_n": len(declared), "actual_n": len(actual)},
                "delta_pct": round(abs(delta) / max(1, avg_dec) * 100, 1),
                "confidence_level": _confidence(min(len(declared), len(actual))),
                "warning": "Auto-relato tende a superestimar capacidade sustentável.",
            })

    return {
        "count": len(hypotheses),
        "hypotheses": hypotheses,
        "vision": {
            "student": "MedFlow Student — ajuda o aluno a decidir o que fazer agora.",
            "institution": "MedFlow Institution — ajuda faculdades a entender dificuldades reais dos alunos.",
            "research": "MedFlow Research — gera dados para pesquisas acadêmicas.",
        },
        "notice": (
            "Nenhuma das afirmações acima é conclusão científica. Todas são "
            "hipóteses para investigação — sempre acompanhadas de amostra (n), "
            "diferença observada (Δ) e limitação metodológica."
        ),
    }



# ---------------------------------------------------------------
# MedFlow Learning Memory — coletiva + reuso (Camada 3)
# ---------------------------------------------------------------

@router.get("/research/collective-difficulty")
async def research_collective_difficulty(
    period_bucket: Optional[str] = None,
    min_sample: int = 5,
    _: dict = Depends(require_admin),
) -> dict:
    """Top tópicos com maior taxa de erro coletiva (dificuldade agregada).

    Nunca inclui identificadores individuais — só (discipline, topic, subtopic)
    + estatísticas agregadas de content_memory. Filtro opcional por período.
    """
    import learning_memory as lm
    items = await lm.collective_difficulty(period_bucket=period_bucket, min_sample=max(3, min_sample))
    return {
        "period_bucket": period_bucket,
        "min_sample": max(3, min_sample),
        "count": len(items),
        "items": items,
        "notice": (
            "Cada item agrega tentativas de múltiplos alunos anônimos sobre o mesmo "
            "conteúdo. Um difficulty > 0.5 sugere ponto de reforço coletivo — nunca "
            "conclusão sobre alunos individuais."
        ),
    }


@router.get("/research/content-reuse")
async def research_content_reuse(_: dict = Depends(require_admin)) -> dict:
    """Métricas de reuso da memória de conteúdo (economia de IA + acúmulo)."""
    import learning_memory as lm
    return await lm.content_reuse_metrics()


@router.get("/content-memory")
async def admin_content_memory(_: dict = Depends(require_admin)) -> dict:
    """P1 — Painel administrativo do Content Memory Engine.

    Consolida em uma resposta única as métricas exigidas pelo PO:
    total de conteúdos, cache hits/misses, reuse ratio, tokens/USD
    economizados, quarentena, top reused, top reported, tempos médios,
    e sanidade da configuração vigente (schema version, TTL, thresholds).
    """
    import learning_memory as lm
    metrics = await lm.content_reuse_metrics()

    # Tempo médio de reuse (last_used_at - created_at)
    from datetime import datetime, timezone
    reuse_times_sec: list[float] = []
    gen_times_sec: list[float] = []  # não medimos geração histórica; deixamos slot para futura instrumentação
    async for d in db.content_memory.find(
        {"usage_count": {"$gt": 1}},
        {"_id": 0, "created_at": 1, "last_used_at": 1, "usage_count": 1},
    ):
        try:
            created = datetime.fromisoformat(str(d.get("created_at")).replace("Z", "+00:00"))
            last_used = d.get("last_used_at")
            if not last_used:
                continue
            last = datetime.fromisoformat(str(last_used).replace("Z", "+00:00"))
            avg = (last - created).total_seconds() / max(1, int(d.get("usage_count") or 1) - 1)
            reuse_times_sec.append(avg)
        except Exception:
            continue

    avg_reuse_seconds = round(sum(reuse_times_sec) / len(reuse_times_sec), 2) if reuse_times_sec else None
    # P1: generation_time agora é medido em tempo real pelo engine (via
    # `generation_ms` gravado em cada doc); métricas expostas em
    # metrics["generation_time_ms"]. Mantemos o campo `avg_generation_seconds`
    # aqui como derivação para não quebrar consumidores existentes.
    gen_avg_ms = (metrics.get("generation_time_ms") or {}).get("avg")
    avg_gen_seconds: float | None = round(gen_avg_ms / 1000.0, 3) if isinstance(gen_avg_ms, (int, float)) else None

    return {
        **metrics,
        "config": {
            "current_schema_version": lm.CONTENT_SCHEMA_VERSION,
            "quarantine_min_reports": lm.QUARANTINE_MIN_REPORTS,
            "quarantine_report_ratio": lm.QUARANTINE_REPORT_RATIO,
            "reuse_efficacy_threshold": lm.REUSE_EFFICACY_THRESHOLD,
            "reuse_min_sample": lm.REUSE_MIN_SAMPLE,
            "ttl_by_kind_days": lm.TTL_BY_KIND,
            "default_ttl_days": lm.DEFAULT_TTL_DAYS,
            "circuit_breaker": {
                "failure_threshold": lm.CB_FAILURE_THRESHOLD,
                "open_seconds": lm.CB_OPEN_SECONDS,
                "retry_attempts": lm.CB_RETRY_ATTEMPTS,
                "llm_timeout_seconds": lm.LLM_TIMEOUT_SECONDS,
            },
        },
        "timing": {
            "avg_reuse_interval_seconds": avg_reuse_seconds,
            "avg_generation_seconds": avg_gen_seconds,
            "generation_ms_p95": (metrics.get("generation_time_ms") or {}).get("p95"),
            "generation_ms_p99": (metrics.get("generation_time_ms") or {}).get("p99"),
            "note": "generation_ms medido no doc; ver metrics.generation_time_ms para P50/P95/P99.",
        },
        "stampede_dashboard": {
            "singleflight_waits": metrics["stampede_prevention"]["singleflight_waits"],
            "stampede_prevented": metrics["stampede_prevention"]["stampede_prevented"],
            "duplicate_key_saves_cross_process": metrics["stampede_prevention"]["duplicate_key_saves"],
            "redundant_generations_ever": metrics["redundant_generations"],
            "estimated_extra_tokens_saved_by_stampede_prevention":
                metrics["stampede_prevention"]["stampede_prevented"] * metrics["assumptions"]["avg_tokens_per_generation"],
            "estimated_extra_usd_saved_by_stampede_prevention":
                round(metrics["stampede_prevention"]["stampede_prevented"]
                      * metrics["assumptions"]["avg_tokens_per_generation"]
                      * metrics["assumptions"]["usd_per_token"], 4),
            "estimated_extra_time_saved_seconds_by_stampede_prevention":
                round(metrics["stampede_prevention"]["stampede_prevented"]
                      * ((metrics.get("generation_time_ms") or {}).get("avg") or 0) / 1000.0, 2),
        },
    }
