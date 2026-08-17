"""MedFlow — Memória de Eficácia (P0.2.1).

Camada de aprendizado comportamental. O motor de decisão passa a responder:
    "Eu recomendei X para este aluno neste contexto. Funcionou?"

NÃO usa IA generativa. Aprende exclusivamente por comportamento observado.

Coleções:
- `recommendation_events`: log imutável. Cada recomendação apresentada gera
  um evento com contexto completo + ciclo de vida (shown → started →
  completed | abandoned).
- `user_behavior_profiles` (cache): agregados por (user_id, rule) e
  (user_id, context_bucket). Recalculado quando um evento fecha.

Uso pelo motor:
    ctx = await snapshot_context(user_id)
    reco = pick_base_decision(...)      # decisão baseada em regras
    reco = await adjust_by_efficacy(user_id, reco, ctx)  # aprendizado
    rec_id = await persist_recommendation(user_id, reco, ctx)
    reco['id'] = rec_id
    reco['confidence'] = ...

Regras de fronteira:
- Nunca cria efeitos nas regras clínicas P5 (bem-estar tem precedência).
- Ajuste inicial só quando sample_size >= 3.
- Ajuste máximo: reduzir duração pela metade OU trocar action de "study"
  para "review_light" quando abandono for consistente.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from core import _iso, _now, db


# ─── Buckets de contexto ─────────────────────────────────────────
def _sleep_bucket(sleep: Optional[int]) -> str:
    if sleep is None:
        return "unknown"
    if sleep <= 3:
        return "low"
    if sleep <= 4:
        return "mid"
    return "high"


def _stress_bucket(stress: Optional[int]) -> str:
    if stress is None:
        return "unknown"
    if stress >= 7:
        return "high"
    if stress >= 4:
        return "mid"
    return "low"


def _hour_bucket(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 23:
        return "evening"
    return "night"


def _duration_bucket(minutes: int) -> str:
    if minutes <= 15:
        return "short"
    if minutes <= 25:
        return "medium"
    if minutes <= 45:
        return "long"
    return "extended"


async def snapshot_context(user_id: str) -> dict:
    """Captura o contexto atual do usuário para persistir com a recomendação.

    Contexto = tudo que o motor viu no momento da decisão. Isso é o que nos
    permite comparar "recomendei X quando o aluno estava assim; funcionou?".
    """
    # Último check-in (energia, humor, sono, stress)
    last_ck: dict = {}
    async for c in db.checkins.find(
        {"user_id": user_id},
        {"_id": 0, "mood": 1, "sleep": 1, "stress": 1, "energy": 1, "created_at": 1},
    ).sort("created_at", -1).limit(1):
        last_ck = c

    now = _now()
    hour = (now.hour - 3) % 24  # local (Brasil UTC-3)
    return {
        "hour": hour,
        "hour_bucket": _hour_bucket(hour),
        "dow": now.weekday(),
        "mood": last_ck.get("mood"),
        "sleep": last_ck.get("sleep"),
        "stress": last_ck.get("stress"),
        "energy": last_ck.get("energy"),
        "sleep_bucket": _sleep_bucket(last_ck.get("sleep")),
        "stress_bucket": _stress_bucket(last_ck.get("stress")),
        "checkin_at": last_ck.get("created_at"),
    }


# ─── Persistência do evento ─────────────────────────────────────
async def persist_recommendation(user_id: str, reco: dict, context: dict) -> str:
    """Insere o evento inicial. Retorna o `recommendation_id`."""
    rec_id = f"rec_{uuid.uuid4().hex[:16]}"
    doc = {
        "id": rec_id,
        "user_id": user_id,
        "rule": reco.get("rule"),
        "priority": reco.get("priority"),
        "action": reco.get("action"),
        "kind": reco.get("kind"),
        "title": reco.get("title"),
        "subtitle": reco.get("subtitle"),
        "duration_planned_min": reco.get("duration_min"),
        "subject_id": _extract_subject_id(reco),
        "action_route": reco.get("action_route"),
        "confidence": reco.get("confidence"),
        "adjusted": reco.get("adjusted", False),
        "adjustment_reason": reco.get("adjustment_reason"),
        "context": context,
        "recommended_at": _iso(_now()),
        "shown_at": None,
        "why_expanded_at": None,
        "started_at": None,
        "completed_at": None,
        "abandoned_at": None,
        "duration_actual_min": None,
        "abandoned_after_min": None,
        "outcome": None,          # "completed" | "abandoned" | "not_started"
    }
    await db.recommendation_events.insert_one(doc)
    return rec_id


def _extract_subject_id(reco: dict) -> Optional[str]:
    """Best-effort: extrai subject_id do action_route (?subject=X&...)."""
    route = reco.get("action_route") or ""
    if "subject=" in route:
        try:
            return route.split("subject=", 1)[1].split("&", 1)[0]
        except Exception:
            return None
    # fallback: da evidência
    ev = reco.get("evidence") or {}
    data = ev.get("data") or {}
    return data.get("subject_id")


# ─── Ciclo de vida do evento (chamado pelos endpoints) ──────────
async def mark_shown(rec_id: str, user_id: str) -> bool:
    r = await db.recommendation_events.update_one(
        {"id": rec_id, "user_id": user_id, "shown_at": None},
        {"$set": {"shown_at": _iso(_now())}},
    )
    return r.modified_count > 0


async def mark_why_expanded(rec_id: str, user_id: str) -> bool:
    """Registra leitura da explicação sem mudar a recomendação ou seu peso."""
    r = await db.recommendation_events.update_one(
        {"id": rec_id, "user_id": user_id, "why_expanded_at": None},
        {"$set": {"why_expanded_at": _iso(_now())}},
    )
    return r.modified_count > 0


async def mark_started(rec_id: str, user_id: str) -> bool:
    r = await db.recommendation_events.update_one(
        {"id": rec_id, "user_id": user_id, "started_at": None},
        {"$set": {"started_at": _iso(_now())}},
    )
    return r.modified_count > 0


async def mark_completed(rec_id: str, user_id: str, duration_actual_min: Optional[int] = None) -> bool:
    updates = {"completed_at": _iso(_now()), "outcome": "completed"}
    if duration_actual_min is not None:
        updates["duration_actual_min"] = int(duration_actual_min)
    r = await db.recommendation_events.update_one(
        {"id": rec_id, "user_id": user_id, "completed_at": None, "abandoned_at": None},
        {"$set": updates},
    )
    return r.modified_count > 0


async def mark_abandoned(rec_id: str, user_id: str, abandoned_after_min: Optional[int] = None) -> bool:
    updates = {"abandoned_at": _iso(_now()), "outcome": "abandoned"}
    if abandoned_after_min is not None:
        updates["abandoned_after_min"] = int(abandoned_after_min)
    r = await db.recommendation_events.update_one(
        {"id": rec_id, "user_id": user_id, "completed_at": None, "abandoned_at": None},
        {"$set": updates},
    )
    return r.modified_count > 0


# ─── Cálculo de eficácia por regra ──────────────────────────────
async def rule_efficacy(user_id: str, rule: str, n: int = 20) -> dict:
    """Estatísticas dos últimos N eventos desta regra para este usuário."""
    events: list[dict] = []
    async for e in db.recommendation_events.find(
        {"user_id": user_id, "rule": rule, "shown_at": {"$ne": None}},
        {"_id": 0, "started_at": 1, "completed_at": 1, "abandoned_at": 1,
         "duration_planned_min": 1, "duration_actual_min": 1, "abandoned_after_min": 1,
         "outcome": 1, "context": 1},
    ).sort("recommended_at", -1).limit(n):
        events.append(e)

    total_shown = len(events)
    total_started = sum(1 for e in events if e.get("started_at"))
    total_completed = sum(1 for e in events if e.get("completed_at"))
    total_abandoned = sum(1 for e in events if e.get("abandoned_at"))

    start_rate = (total_started / total_shown) if total_shown else 0.0
    completion_rate = (total_completed / total_started) if total_started else 0.0
    abandonment_rate = (total_abandoned / total_started) if total_started else 0.0

    # Tempo médio até abandono (só entre abandonados)
    aband_times = [int(e["abandoned_after_min"]) for e in events
                   if e.get("abandoned_at") and e.get("abandoned_after_min") is not None]
    avg_abandon_min = round(sum(aband_times) / len(aband_times), 1) if aband_times else None

    # Duração real média entre concluídos
    dur_actual = [int(e["duration_actual_min"]) for e in events
                  if e.get("completed_at") and e.get("duration_actual_min") is not None]
    avg_actual_min = round(sum(dur_actual) / len(dur_actual), 1) if dur_actual else None

    return {
        "rule": rule,
        "sample_size": total_shown,
        "total_started": total_started,
        "total_completed": total_completed,
        "total_abandoned": total_abandoned,
        "start_rate": round(start_rate, 3),
        "completion_rate": round(completion_rate, 3),
        "abandonment_rate": round(abandonment_rate, 3),
        "avg_abandon_min": avg_abandon_min,
        "avg_actual_min": avg_actual_min,
    }


# ─── Perfil comportamental agregado ─────────────────────────────
async def behavior_profile(user_id: str) -> dict:
    """Descobre padrões comportamentais individuais.

    Sem configuração explícita — tudo derivado dos eventos. Dimensões:
      - best_hour_bucket: qual período do dia tem maior start_rate
      - best_duration_bucket: qual duração tem maior completion_rate
      - context_low_sleep_completion: completion_rate quando sleep<=3
      - context_high_stress_completion: completion_rate quando stress>=7
      - session_length_success: dict bucket→completion_rate
    """
    events: list[dict] = []
    async for e in db.recommendation_events.find(
        {"user_id": user_id, "shown_at": {"$ne": None}},
        {"_id": 0, "started_at": 1, "completed_at": 1, "abandoned_at": 1,
         "duration_planned_min": 1, "context": 1},
    ).sort("recommended_at", -1).limit(80):
        events.append(e)

    if not events:
        return {"sample_size": 0}

    def _rate(subset, key_started="started_at", key_end="completed_at"):
        started = [e for e in subset if e.get(key_started)]
        if not started:
            return None
        return round(sum(1 for e in started if e.get(key_end)) / len(started), 3)

    # Por hour_bucket
    by_hour: dict[str, list[dict]] = {}
    for e in events:
        b = (e.get("context") or {}).get("hour_bucket")
        if b:
            by_hour.setdefault(b, []).append(e)
    hour_stats = {b: _rate(v) for b, v in by_hour.items()}
    hour_stats = {k: v for k, v in hour_stats.items() if v is not None}
    best_hour = max(hour_stats.items(), key=lambda kv: kv[1])[0] if hour_stats else None

    # Por duration_bucket
    by_dur: dict[str, list[dict]] = {}
    for e in events:
        planned = e.get("duration_planned_min")
        if planned is None:
            continue
        by_dur.setdefault(_duration_bucket(int(planned)), []).append(e)
    dur_stats = {b: _rate(v) for b, v in by_dur.items()}
    dur_stats = {k: v for k, v in dur_stats.items() if v is not None}
    best_dur = max(dur_stats.items(), key=lambda kv: kv[1])[0] if dur_stats else None

    # Contexto: baixo sono
    low_sleep_subset = [e for e in events if (e.get("context") or {}).get("sleep_bucket") == "low"]
    low_sleep_completion = _rate(low_sleep_subset)

    # Contexto: alto stress
    high_stress_subset = [e for e in events if (e.get("context") or {}).get("stress_bucket") == "high"]
    high_stress_completion = _rate(high_stress_subset)

    return {
        "sample_size": len(events),
        "hour_bucket_completion": hour_stats,
        "best_hour_bucket": best_hour,
        "duration_bucket_completion": dur_stats,
        "best_duration_bucket": best_dur,
        "context_low_sleep_completion": low_sleep_completion,
        "context_high_stress_completion": high_stress_completion,
    }


# ─── Confidence score ───────────────────────────────────────────
def compute_confidence(sample_size: int, completion_rate: Optional[float]) -> dict:
    """Retorna dict { score: 0..1, level: 'low'|'medium'|'high', reason: str }.

    Base:
    - sample_size determina o teto (10+ = full ceiling; 5-9 = teto 0.75;
      3-4 = teto 0.55; <3 = "learning", score 0.35).
    - completion_rate empurra para cima ou para baixo dentro do teto.

    Quando confidence < 0.5 → UI deve usar linguagem de "aprendizado".
    """
    if sample_size < 3 or completion_rate is None:
        return {
            "score": 0.35,
            "level": "learning",
            "reason": "Ainda estou aprendendo como você funciona.",
            "sample_size": sample_size,
        }
    if sample_size < 5:
        ceiling, floor = 0.55, 0.30
    elif sample_size < 10:
        ceiling, floor = 0.75, 0.35
    else:
        ceiling, floor = 0.95, 0.35

    # Interpola pela completion_rate (bounded 0..1)
    score = floor + (ceiling - floor) * max(0.0, min(1.0, completion_rate))
    score = round(score, 2)

    if score >= 0.75:
        level, reason = "high", "Padrão consistente detectado no seu histórico."
    elif score >= 0.5:
        level, reason = "medium", "Padrão em formação — ainda validando."
    else:
        level, reason = "low", "Poucos casos comparáveis até agora."

    return {"score": score, "level": level, "reason": reason, "sample_size": sample_size}


# ─── Ajuste da recomendação pela memória de eficácia ────────────
async def adjust_by_efficacy(user_id: str, reco: dict, context: dict) -> dict:
    """Ajusta a recomendação com base no histórico e adiciona confidence.

    Regras de ajuste (conservadoras, nunca invasivas):
      A. Se `sample_size >= 3` e `completion_rate < 0.35` E `duration_min > 15`:
         reduzir duração pela metade (min 10min) e marcar `adjusted=True`.
      B. Se `avg_abandon_min` é conhecido e planejamos mais que 1.5× esse valor,
         limitar duração a `avg_abandon_min` (sinal de que sessões longas
         não terminam).
      C. Preferência de horário: se contexto atual está no `best_hour_bucket`,
         aumentar confidence (é o momento em que este aluno mais entrega).

    Regras clínicas P5 nunca são reduzidas em duração (bem-estar prevalece),
    mas ganham confidence do histórico como qualquer outra.
    """
    rule = reco.get("rule")
    priority = reco.get("priority", 0)
    planned = int(reco.get("duration_min") or 0)

    eff = await rule_efficacy(user_id, rule, n=20)
    profile = await behavior_profile(user_id)

    adjusted = False
    reasons: list[str] = []
    new_duration = planned

    # A. Baixa taxa de conclusão → sessão mais curta
    if priority < 5 and eff["sample_size"] >= 3 and planned > 15:
        if eff["completion_rate"] is not None and eff["completion_rate"] < 0.35:
            new_duration = max(10, planned // 2)
            adjusted = True
            pct = int(round(eff["completion_rate"] * 100))
            reasons.append(
                f"Nas últimas {eff['sample_size']} vezes com esta recomendação, "
                f"você concluiu {pct}%. Reduzi para {new_duration} min."
            )

    # B. Duração > 1.5× tempo médio até abandono
    if priority < 5 and eff.get("avg_abandon_min") is not None:
        avg_ab = float(eff["avg_abandon_min"])
        if avg_ab > 0 and new_duration > avg_ab * 1.5:
            capped = max(10, int(round(avg_ab)))
            if capped < new_duration:
                new_duration = capped
                adjusted = True
                reasons.append(
                    f"Você costuma pausar após {int(round(avg_ab))} min neste tipo de sessão. "
                    f"Sugeri {capped} min pra você chegar até o fim."
                )

    reco["duration_min"] = new_duration

    # Recalcula action_route pra refletir nova duração (se ela estava lá)
    route = reco.get("action_route") or ""
    if "duration=" in route:
        parts = []
        for p in route.split("?", 1)[1].split("&") if "?" in route else []:
            if p.startswith("duration="):
                parts.append(f"duration={new_duration}")
            else:
                parts.append(p)
        base = route.split("?", 1)[0]
        reco["action_route"] = f"{base}?{'&'.join(parts)}" if parts else base

    # C. Confidence baseado em histórico da regra + bump se hora ótima
    conf = compute_confidence(eff["sample_size"], eff["completion_rate"])
    if profile.get("best_hour_bucket") and profile["best_hour_bucket"] == context.get("hour_bucket"):
        conf["score"] = round(min(0.98, conf["score"] + 0.05), 2)
        conf["reason"] = (conf["reason"] + " · Este é seu melhor período do dia.").strip()

    reco["confidence"] = conf["score"]
    reco["confidence_level"] = conf["level"]
    reco["confidence_reason"] = conf["reason"]
    reco["adjusted"] = adjusted
    reco["adjustment_reason"] = " ".join(reasons) if reasons else None

    # Estatísticas úteis para o popover "Como o MedFlow percebeu isso?" (P0.3)
    reco["efficacy_stats"] = {
        "sample_size": eff["sample_size"],
        "completion_rate": eff["completion_rate"],
        "abandonment_rate": eff["abandonment_rate"],
        "avg_actual_min": eff["avg_actual_min"],
    }
    return reco


# ─── Perfil de aprendizagem: typical_study_min VIVO ─────────────
# Filosofia: o que o aluno declara no onboarding ("tenho 2 horas") ≠ o que
# ele realmente sustenta. Este perfil aprende o RITMO SUSTENTÁVEL ATUAL,
# não o desejado. Motor usa internamente — não é exposto na UI ainda.
#
# Fontes de sessão concluída (ordem de preferência):
#   1. `recommendation_events` com outcome=='completed' e duration_actual_min
#   2. `pomodoro_sessions` com status=='completed' e focused_minutes>0
#      (cold start: cobre usuários existentes antes do event log crescer)
#
# Peso exponencial: mais recente vale mais.
#   w_i = 0.85 ** i, i=0 (mais recente) até min(9, N-1)


async def _recent_completed_sessions(user_id: str, limit: int = 10) -> list[tuple[str, int]]:
    """Retorna lista de (timestamp_iso, duration_min) das sessões concluídas
    mais recentes. Combina recommendation_events + pomodoro_sessions.
    """
    entries: list[tuple[str, int]] = []

    # Fonte 1: eventos de recomendação concluídos
    async for e in db.recommendation_events.find(
        {"user_id": user_id, "outcome": "completed",
         "duration_actual_min": {"$ne": None, "$gt": 0}},
        {"_id": 0, "completed_at": 1, "duration_actual_min": 1},
    ).sort("completed_at", -1).limit(limit):
        ts = e.get("completed_at")
        d = e.get("duration_actual_min")
        if ts and d:
            entries.append((ts, int(d)))

    # Fonte 2 (fallback / cold start): sessões de pomodoro concluídas.
    # Só adicionamos até completar `limit` entradas — assim o event log,
    # se existir, é sempre preferido.
    if len(entries) < limit:
        need = limit - len(entries)
        async for p in db.pomodoro_sessions.find(
            {"user_id": user_id, "status": "completed",
             "focused_minutes": {"$gt": 0}},
            {"_id": 0, "created_at": 1, "focused_minutes": 1},
        ).sort("created_at", -1).limit(need):
            ts = p.get("created_at")
            d = p.get("focused_minutes")
            if ts and d:
                entries.append((ts, int(d)))

    # Ordena decrescente por timestamp (mais recente primeiro), tira até `limit`
    entries.sort(key=lambda x: x[0], reverse=True)
    return entries[:limit]


async def learning_profile(user_id: str, declared_typical_min: int | None = None) -> dict:
    """Ritmo sustentável ATUAL — descoberto por comportamento observado.

    Retorna:
      {
        typical_study_min: int,      # o valor calibrado (ou declarado se insuficiente)
        source: 'learned' | 'declared' | 'default',
        sample_size: int,
        confidence: float 0..1,
        last_updated: iso | None,    # timestamp da sessão mais recente considerada
        weighted_avg_min: float | None,
        raw_sessions: list[int],     # durações usadas, ordem desc por data
        declared_typical_min: int | None,
      }
    """
    sessions = await _recent_completed_sessions(user_id, limit=10)
    sample_size = len(sessions)
    declared = int(declared_typical_min) if declared_typical_min else None

    if sample_size < 3:
        # Ainda não sabemos. Se tem declared, usa; caso contrário 45 (default).
        return {
            "typical_study_min": declared if declared else 45,
            "source": "declared" if declared else "default",
            "sample_size": sample_size,
            "confidence": 0.35,
            "last_updated": sessions[0][0] if sessions else None,
            "weighted_avg_min": None,
            "raw_sessions": [d for _, d in sessions],
            "declared_typical_min": declared,
        }

    # Peso exponencial. Alpha 0.15 → 0.85^i.
    weights = [0.85 ** i for i in range(sample_size)]
    durations = [d for _, d in sessions]  # já ordenados desc por data
    weighted_sum = sum(d * w for d, w in zip(durations, weights))
    weight_total = sum(weights)
    weighted_avg = weighted_sum / weight_total

    # Arredonda para o múltiplo de 5 min mais próximo (estabiliza recomendações)
    calibrated = int(round(weighted_avg / 5.0) * 5)
    calibrated = max(10, min(90, calibrated))  # clamp sanidade

    # Confidence do perfil de aprendizagem
    if sample_size >= 10:
        conf = 0.9
    elif sample_size >= 5:
        conf = 0.7
    else:
        conf = 0.55

    return {
        "typical_study_min": calibrated,
        "source": "learned",
        "sample_size": sample_size,
        "confidence": round(conf, 2),
        "last_updated": sessions[0][0],
        "weighted_avg_min": round(weighted_avg, 1),
        "raw_sessions": durations,
        "declared_typical_min": declared,
    }


async def get_effective_typical_min(user_id: str, declared_typical_min: int | None) -> int:
    """Atalho para o motor: devolve inteiro pronto pra usar.

    Se o perfil de aprendizagem tem base suficiente (>=3), usa o calibrado.
    Senão, cai pro declarado (ou 45 default). Isso é o único ponto de
    consumo obrigatório pra que o motor "aprenda" o ritmo do aluno.
    """
    lp = await learning_profile(user_id, declared_typical_min)
    return int(lp["typical_study_min"])
