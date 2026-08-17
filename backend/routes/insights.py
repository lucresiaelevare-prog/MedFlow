"""Insights consolidados — Foco + Hábitos + Humor + coaching IA.

- `GET /api/insights/weekly-report?days=7`
    Retorna séries diárias (últimos N dias) de:
      - focused_minutes (pomodoro_sessions completadas)
      - care_actions   (care_logs)
      - avg_mood       (checkins.mood, média por dia)
    Mais uma frase de "coaching" curta gerada 1× por dia via Claude Sonnet 4.5.
    Cache no doc user_profiles.weekly_coaching = {date, text}.
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends

from core import EMERGENT_LLM_KEY, _iso, _now, db, require_user

logger = logging.getLogger("medflow.insights")
router = APIRouter(prefix="/api/insights", tags=["insights"])


DEFAULT_COACH = (
    "Semana em construção — mantenha o ritmo, mesmo em pequenos passos. Consistência abre caminho."
)


async def _generate_coaching(context: dict) -> str:
    """Frase curta (≤ 30 palavras) baseada no report semanal. Retorna DEFAULT_COACH em falha."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception:  # noqa: BLE001
        return DEFAULT_COACH

    system = (
        "Você é o MedFlow, copiloto de estudantes de Medicina no Brasil. "
        "Devolva UMA única frase em pt-BR (máx 28 palavras), tom acolhedor, sem emoji, sem markdown, "
        "sem diagnóstico. Foco em reconhecer o padrão da semana e sugerir 1 micro-ação concreta."
    )
    prompt = (
        "Resumo da última semana do aluno (números crus):\n"
        f"- minutos totais de foco: {context['total_focus_min']}\n"
        f"- ações de autocuidado: {context['total_care']}\n"
        f"- check-ins: {context['total_checkins']}\n"
        f"- humor médio (1-5): {context['avg_mood']}\n"
        f"- dias com foco > 0: {context['days_focused']}\n"
        f"- dias com autocuidado > 0: {context['days_care']}\n"
        "Escreva 1 frase de coaching."
    )
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"medflow-coach-{uuid.uuid4().hex[:10]}",
            system_message=system,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        reply = await chat.send_message(UserMessage(text=prompt))
    except Exception as exc:  # noqa: BLE001
        logger.warning("coaching LLM call failed: %s", exc)
        return DEFAULT_COACH
    text = (reply.strip() if isinstance(reply, str) else str(reply)).strip()
    # first non-empty line, no quotes/markdown noise
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), text)
    line = line.strip('"“”\' ').strip()
    return line[:240] or DEFAULT_COACH


@router.get("/weekly-report")
async def weekly_report(days: int = 7, user: dict = Depends(require_user)) -> dict:
    user_id = user["user_id"]
    days = max(3, min(days, 30))

    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=days - 1)
    start_iso = _iso(start)
    end_iso = _iso(today + timedelta(days=1))
    start_date = start.date().isoformat()
    end_date = (today + timedelta(days=1)).date().isoformat()

    # Base skeleton — 1 entry per day, in chronological order
    date_keys: list[str] = []
    focus_map: dict[str, int] = {}
    care_map: dict[str, int] = {}
    mood_accum: dict[str, list[int]] = {}
    for i in range(days):
        d = (start + timedelta(days=i)).date().isoformat()
        date_keys.append(d)
        focus_map[d] = 0
        care_map[d] = 0
        mood_accum[d] = []

    # Focus (pomodoro_sessions completed)
    poms = await db.pomodoro_sessions.find(
        {"user_id": user_id, "status": "completed",
         "date": {"$gte": start_date, "$lt": end_date}},
        {"_id": 0, "date": 1, "focused_minutes": 1},
    ).to_list(1000)
    for p in poms:
        k = p.get("date")
        if k in focus_map:
            focus_map[k] += int(p.get("focused_minutes") or 0)

    # Habits (care_logs)
    cares = await db.care_logs.find(
        {"user_id": user_id, "date": {"$gte": start_date, "$lt": end_date}},
        {"_id": 0, "date": 1},
    ).to_list(2000)
    for c in cares:
        k = c.get("date")
        if k in care_map:
            care_map[k] += 1

    # Mood (checkins)
    checkins = await db.checkins.find(
        {"user_id": user_id, "created_at": {"$gte": start_iso, "$lt": end_iso}},
        {"_id": 0, "created_at": 1, "mood": 1},
    ).to_list(500)
    for c in checkins:
        try:
            k = c["created_at"][:10]
        except Exception:
            continue
        if k in mood_accum:
            m = int(c.get("mood") or 0)
            if m:
                mood_accum[k].append(m)

    focus_series = [{"date": d, "minutes": focus_map[d]} for d in date_keys]
    habits_series = [{"date": d, "actions": care_map[d]} for d in date_keys]
    mood_series = [{
        "date": d,
        "mood": round(sum(mood_accum[d]) / len(mood_accum[d]), 1) if mood_accum[d] else None,
    } for d in date_keys]

    total_focus = sum(x["minutes"] for x in focus_series)
    total_care = sum(x["actions"] for x in habits_series)
    total_checkins = len(checkins)
    all_moods = [m for lst in mood_accum.values() for m in lst]
    avg_mood = round(sum(all_moods) / len(all_moods), 1) if all_moods else None
    days_focused = sum(1 for x in focus_series if x["minutes"] > 0)
    days_care = sum(1 for x in habits_series if x["actions"] > 0)

    context = {
        "total_focus_min": total_focus,
        "total_care": total_care,
        "total_checkins": total_checkins,
        "avg_mood": avg_mood if avg_mood is not None else "sem registro",
        "days_focused": days_focused,
        "days_care": days_care,
    }

    # ── P1: Content Memory Engine (unified) ─────────────────────────
    # Substituição do cache ad-hoc `weekly_coaching` no user_profiles.
    # Fingerprint por buckets grossos + semana ISO → cross-user reuse
    # entre alunos com contextos semelhantes na mesma semana.
    today_key = today.date().isoformat()
    year, week, _ = today.isocalendar()
    week_key = f"{year}W{week:02d}"

    import learning_memory as lm
    def _bucket_int(v, lo, hi):
        try:
            x = int(v)
        except Exception:
            return "unspecified"
        return "low" if x <= lo else "high" if x >= hi else "mid"

    key_fields = {
        "discipline": "insights",
        "topic": "weekly_coaching",
        "subtopic": (
            f"f-{_bucket_int(total_focus // 60, 3, 10)}"
            f"_c-{_bucket_int(total_care, 3, 10)}"
            f"_df-{_bucket_int(days_focused, 2, 5)}"
        ),
        "period_bucket": week_key,
    }

    async def _gen_coach() -> dict:
        text = await _generate_coaching(context)
        return {"text": text}

    memo = await lm.remember_or_generate(
        kind="insights_coaching",
        key_fields=key_fields,
        generator=_gen_coach,
        variant=week_key,
        generator_label="ai:claude-sonnet-4-5",
    )
    coaching = (memo["content"]["payload"] or {}).get("text") or DEFAULT_COACH
    coaching_cached = (memo["source"] == "reused")

    return {
        "range": {"start": start_date, "end": today.date().isoformat(), "days": days},
        "focus_series": focus_series,
        "habits_series": habits_series,
        "mood_series": mood_series,
        "totals": {
            "focus_minutes": total_focus,
            "care_actions": total_care,
            "checkins": total_checkins,
            "avg_mood": avg_mood,
            "days_focused": days_focused,
            "days_care": days_care,
        },
        "coaching": {"text": coaching, "cached": coaching_cached, "date": today_key},
    }



# ═══════════════════════════════════════════════════════════════════
# Relatório de Efetividade Pessoal (P2 do briefing MedFlow)
#
# Diferencial estratégico: prova mensurável da potencialização.
# Sem gamificação. Linguagem neutra. Só sinais reais.
# ═══════════════════════════════════════════════════════════════════

def _pct(current: float, previous: float) -> float | None:
    if previous <= 0:
        return None
    return round(((current - previous) / previous) * 100, 1)


@router.get("/effectiveness-report")
async def effectiveness_report(user: dict = Depends(require_user)) -> dict:
    """Comparativo semana atual vs anterior. Só dados observados."""
    from context_engine import sleep_debt as _debt
    from datetime import datetime, timezone

    now = _now()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    prev_start = week_start - timedelta(days=7)
    uid = user["user_id"]

    async def _week_stats(since: datetime, until: datetime) -> dict:
        s, u = since.isoformat(), until.isoformat()
        # Foco (pomodoros + sessions completed)
        focus_min = 0
        async for p in db.pomodoro_sessions.find(
            {"user_id": uid, "status": "completed", "created_at": {"$gte": s, "$lt": u}},
            {"_id": 0, "focused_minutes": 1},
        ):
            focus_min += int(p.get("focused_minutes") or 0)

        # Recomendações
        rec_total = await db.recommendation_events.count_documents(
            {"user_id": uid, "recommended_at": {"$gte": s, "$lt": u}, "shown_at": {"$ne": None}}
        )
        rec_completed = await db.recommendation_events.count_documents(
            {"user_id": uid, "recommended_at": {"$gte": s, "$lt": u}, "outcome": "completed"}
        )
        rec_abandoned = await db.recommendation_events.count_documents(
            {"user_id": uid, "recommended_at": {"$gte": s, "$lt": u}, "outcome": "abandoned"}
        )
        rec_started = await db.recommendation_events.count_documents(
            {"user_id": uid, "recommended_at": {"$gte": s, "$lt": u}, "started_at": {"$ne": None}}
        )

        # Sono
        sleep_vals: list[float] = []
        low_sleep_days = 0
        async for c in db.checkins.find(
            {"user_id": uid, "created_at": {"$gte": s, "$lt": u}},
            {"_id": 0, "sleep_hours": 1, "sleep": 1},
        ):
            sh = c.get("sleep_hours") if c.get("sleep_hours") is not None else c.get("sleep")
            if sh is None:
                continue
            try:
                sleep_vals.append(float(sh))
                if float(sh) < 6:
                    low_sleep_days += 1
            except Exception:
                pass

        # Disciplinas com mastery derivada de student_content_events
        by_disc_correct: dict[str, int] = {}
        by_disc_incorrect: dict[str, int] = {}
        async for e in db.student_content_events.find(
            {"user_id": uid, "event_type": "answered", "created_at": {"$gte": s, "$lt": u}},
            {"_id": 0, "discipline": 1, "correct": 1},
        ):
            d = e.get("discipline") or "sem-disciplina"
            if e.get("correct") is True:
                by_disc_correct[d] = by_disc_correct.get(d, 0) + 1
            elif e.get("correct") is False:
                by_disc_incorrect[d] = by_disc_incorrect.get(d, 0) + 1

        disc_mastery: dict[str, dict] = {}
        for d in set(by_disc_correct) | set(by_disc_incorrect):
            corr = by_disc_correct.get(d, 0)
            inc = by_disc_incorrect.get(d, 0)
            ans = corr + inc
            score = round(corr / ans, 3) if ans >= 3 else None
            disc_mastery[d] = {"answered": ans, "correct": corr, "score": score}

        return {
            "focus_minutes": focus_min,
            "rec_shown": rec_total,
            "rec_started": rec_started,
            "rec_completed": rec_completed,
            "rec_abandoned": rec_abandoned,
            "completion_rate": round(rec_completed / rec_total, 3) if rec_total else None,
            "avg_sleep": round(sum(sleep_vals) / len(sleep_vals), 2) if sleep_vals else None,
            "low_sleep_days": low_sleep_days,
            "discipline_mastery": disc_mastery,
        }

    curr = await _week_stats(week_start, now)
    prev = await _week_stats(prev_start, week_start)

    # Deltas
    delta_focus_pct = _pct(curr["focus_minutes"], prev["focus_minutes"])
    delta_completion_pct = None
    if prev["completion_rate"] is not None and curr["completion_rate"] is not None:
        delta_completion_pct = round((curr["completion_rate"] - prev["completion_rate"]) * 100, 1)

    # Evolução por disciplina (só onde há score nas duas semanas)
    disc_progress: list[dict] = []
    for d, curr_m in curr["discipline_mastery"].items():
        if curr_m["score"] is None:
            continue
        prev_m = prev["discipline_mastery"].get(d)
        if not prev_m or prev_m["score"] is None:
            continue
        delta_pts = round((curr_m["score"] - prev_m["score"]) * 100, 1)
        disc_progress.append({
            "discipline": d,
            "prev_score": prev_m["score"],
            "curr_score": curr_m["score"],
            "delta_points": delta_pts,
        })
    disc_progress.sort(key=lambda t: t["delta_points"], reverse=True)

    best = disc_progress[:2]
    worst = [d for d in disc_progress[::-1] if d["delta_points"] < 0][:2]

    # Tendências em linguagem neutra
    trends: list[dict] = []
    if delta_completion_pct is not None:
        trends.append({
            "label": "consistência",
            "delta_pct": delta_completion_pct,
            "text": f"{'+' if delta_completion_pct >= 0 else ''}{delta_completion_pct}% consistência",
        })
    if delta_focus_pct is not None:
        trends.append({
            "label": "tempo efetivo",
            "delta_pct": delta_focus_pct,
            "text": f"{'+' if delta_focus_pct >= 0 else ''}{delta_focus_pct}% tempo efetivo",
        })
    if curr["low_sleep_days"] >= 2:
        trends.append({
            "label": "sono",
            "delta_pct": None,
            "text": f"Sono abaixo da meta em {curr['low_sleep_days']} dia(s)",
        })

    return {
        "week_start": week_start.isoformat(),
        "prev_week_start": prev_start.isoformat(),
        "current": curr,
        "previous": prev,
        "trends": trends,
        "best_disciplines": best,
        "worst_disciplines": worst,
        "empty": curr["rec_shown"] == 0 and curr["focus_minutes"] == 0,
    }


# ─── 2026-02 — Peer Benchmarking Anônimo (P0.2) ──────────────
# Comparação com alunos do mesmo bucket de período.
# Sem ranking. Sem competição. Apenas contexto.

@router.get("/peer-benchmark")
async def peer_benchmark(user: dict = Depends(require_user)) -> dict:
    """Comparação anônima de foco (hoje + média semanal) com peers do mesmo período.

    Anonimização por generalização (LGPD-honest): buckets grandes
    (basico/clinico/internato), sample mínimo (>=5 peers ativos),
    só agregados (mediana). Nunca expõe outros usuários.
    """
    import peer_benchmark as pb
    profile = await db.user_profiles.find_one(
        {"user_id": user["user_id"]}, {"_id": 0},
    ) or {}
    return await pb.compute(user["user_id"], profile)

