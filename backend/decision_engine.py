"""MedFlow — Decision Engine (extraído de routes/experience.py na iter15).

Refactor puro. Comportamento idêntico à versão anterior. Motivo do split:
`experience.py` passou de 1250 linhas — arquivo unificando capabilities +
onboarding + regras + tradução em humano. Agora cada responsabilidade fica
no seu módulo:

  routes/experience.py   → capabilities, tour, onboarding, endpoint /home/today
  decision_engine.py     → regras P0–P6, why_signals, why_now, helpers

Nada aqui é chamado diretamente por outros routers — só por experience.home_today
(que orquestra) e por testes.

Filosofia mantida:
    Contexto → Recomendação → Ação → Feedback → Aprendizado.
"""
from __future__ import annotations

from datetime import timedelta

from core import _now, db

# ─── Helper legado: monta ação a partir de /priority/today ────
def _recommend_from_priority(items: list[dict], typical_min: int) -> dict | None:
    """LEGADO — mantido para compatibilidade. Prefira `_decide_next_action`.

    Escolhe UMA ação a partir da lista priorizada.
    """
    if not items:
        return None
    # 1) prova mais próxima (≤7 dias)
    for it in items:
        if it.get("kind") == "exam":
            # "prova crítica · em 3 dia(s)" → "Prova em 3 dias."
            why = (it.get("why") or "").replace("prova crítica · ", "").replace("prova ", "")
            why = why.replace("em ", "em ").strip()
            days_note = why.capitalize() + "." if why else "Prova chegando."
            title = it["title"].split(" — ", 1)[0] if " — " in it["title"] else it["title"]
            return {
                "kind": "exam",
                "title": f"Revisar {title}",
                "subtitle": f"{days_note.replace('Em ', 'Prova em ').replace('dia(s)', 'dias')}",
                "duration_min": max(30, typical_min),
                "action_route": "/subjects",
                "action_label": "Começar agora",
            }
    # 2) bloco de estudo/acadêmico "acontece agora" ou próximo
    for it in items:
        if it.get("kind") == "block" and not it.get("done") and it.get("category") in ("study", "academic"):
            starts = it.get("start_time")
            subtitle = f"Começa às {starts}." if starts else "Está agendado para hoje."
            return {
                "kind": "block",
                "title": it["title"],
                "subtitle": subtitle,
                "duration_min": typical_min,
                "action_route": "/pomodoro",
                "action_label": "Começar agora",
            }
    # 3) missão de estudo
    for it in items:
        if it.get("kind") == "mission" and it.get("category") == "estudo" and not it.get("completed"):
            return {
                "kind": "mission",
                "title": it["title"],
                "subtitle": "Sugestão pra manter o ritmo.",
                "duration_min": int(it.get("minutes") or typical_min),
                "action_route": "/pomodoro",
                "action_label": "Começar agora",
            }
    # 4) fallback: qualquer bloco não feito
    for it in items:
        if it.get("kind") == "block" and not it.get("done"):
            return {
                "kind": "block",
                "title": it["title"],
                "subtitle": "No seu planejamento de hoje.",
                "duration_min": typical_min,
                "action_route": "/planner",
                "action_label": "Ver detalhes",
            }
    return None

# ─── Helpers de contexto e navegação ─────────────────────────
async def _last_checkin(user_id: str) -> dict | None:
    """Último check-in do usuário (para leitura de energia/mood/sleep/stress agora)."""
    async for c in db.checkins.find(
        {"user_id": user_id},
        {"_id": 0, "mood": 1, "sleep": 1, "stress": 1, "energy": 1, "created_at": 1},
    ).sort("created_at", -1).limit(1):
        return c
    return None

async def _least_studied_subject_7d(user_id: str) -> dict | None:
    """Subject com menor tempo de foco nos últimos 7 dias (entre os cadastrados).

    Serve para rotação em recomendações padrão (P1) — evita concentrar sempre
    na mesma matéria.
    """
    since = (_now() - timedelta(days=7)).isoformat()
    times: dict[str, int] = {}
    async for p in db.pomodoro_sessions.find(
        {"user_id": user_id, "status": "completed", "created_at": {"$gte": since}},
        {"_id": 0, "subject_id": 1, "focused_minutes": 1},
    ):
        sid = p.get("subject_id")
        if sid:
            times[sid] = times.get(sid, 0) + int(p.get("focused_minutes") or 0)
    subjects: list[dict] = []
    async for s in db.subjects.find({"user_id": user_id}, {"_id": 0, "id": 1, "name": 1, "priority": 1}):
        subjects.append(s)
    if not subjects:
        return None
    # Ordena por menos-estudado (0 primeiro) e depois por priority se disponível
    def _rank(s):
        mins = times.get(s["id"], 0)
        pri_w = {"critica": 0, "muito_alta": 1, "alta": 2, "media": 3, "baixa": 4}
        return (mins, pri_w.get(str(s.get("priority") or "").lower(), 5))
    subjects.sort(key=_rank)
    return subjects[0]

def _pomodoro_route(subject_id: str | None = None, duration: int | None = None) -> str:
    parts = []
    if subject_id:
        parts.append(f"subject={subject_id}")
    if duration:
        parts.append(f"duration={duration}")
    return "/pomodoro" + (("?" + "&".join(parts)) if parts else "")

# ═══════════════════════════════════════════════════════════════════
# ITER14 — Motor visível
#
# `_build_why_signals` e `_compose_why_now` traduzem o output do motor
# em linguagem humana. NUNCA adicionam informação nova — apenas expõem
# o raciocínio que já estava lá, invisível.
#
# Filosofia: se o aluno não perceber o cérebro do produto, o cérebro
# não vale nada. Estes dois helpers são o vidro pelo qual o aluno vê
# a máquina pensando.
# ═══════════════════════════════════════════════════════════════════

def _build_why_signals(rec: dict, context: dict | None) -> list[dict]:
    """Lista de sinais concretos que o motor observou (icon + label + value).

    Cada sinal é auto-explicativo. Frontend só renderiza. Nenhum sinal
    é inventado — se o dado bruto não existir, o sinal não aparece.
    """
    signals: list[dict] = []
    ev = (rec.get("evidence") or {}).get("data") or {}
    ctx = context or {}

    # Contexto emocional
    if ctx.get("sleep") is not None:
        signals.append({
            "icon": "moon", "kind": "sleep",
            "label": "Sono da última noite",
            "value": f"{ctx['sleep']}h",
        })
    if ctx.get("mood") is not None:
        signals.append({
            "icon": "heart", "kind": "mood",
            "label": "Humor atual",
            "value": f"{ctx['mood']}/10",
        })
    if ctx.get("stress") is not None:
        signals.append({
            "icon": "activity", "kind": "stress",
            "label": "Estresse atual",
            "value": f"{ctx['stress']}/10",
        })

    # Cronotipo / energia
    peak = ev.get("peak_bucket")
    if peak:
        signals.append({
            "icon": "sun", "kind": "chronotype",
            "label": "Seu pico de energia",
            "value": peak.capitalize(),
        })
    if ev.get("hour_bucket_now"):
        signals.append({
            "icon": "clock", "kind": "hour",
            "label": "Momento atual",
            "value": ev["hour_bucket_now"].capitalize()
                     + (" (pico)" if ev.get("is_peak") else " (fora do pico)"),
        })
    elif ctx.get("hour_bucket"):
        # Fallback: sempre emite o "momento atual" quando o contexto tem hora,
        # mesmo se a regra que venceu não injetou hour_bucket_now na evidência.
        signals.append({
            "icon": "clock", "kind": "hour",
            "label": "Momento atual",
            "value": ctx["hour_bucket"].capitalize(),
        })
    if ev.get("sleep_debt_h") and ev["sleep_debt_h"] > 0:
        signals.append({
            "icon": "alert", "kind": "debt",
            "label": "Débito de sono",
            "value": f"{ev['sleep_debt_h']}h abaixo da meta",
        })

    # Confiança e amostra
    if rec.get("confidence_level"):
        signals.append({
            "icon": "brain", "kind": "confidence",
            "label": "Confiança da recomendação",
            "value": {
                "learning": "Aprendendo você",
                "low": "Sinal fraco",
                "medium": "Sinal claro",
                "high": "Sinal forte",
            }.get(rec["confidence_level"], rec["confidence_level"]),
        })
    stats = rec.get("efficacy_stats") or {}
    if stats.get("sample"):
        signals.append({
            "icon": "chart", "kind": "sample",
            "label": "Dessa regra já observei",
            "value": f"{stats['sample']} sessão(ões) sua(s)",
        })

    # Ajustes automáticos
    if rec.get("adjustment_reason"):
        signals.append({
            "icon": "wand", "kind": "adjustment",
            "label": "Ajuste automático",
            "value": rec["adjustment_reason"],
        })

    # Prova próxima (se estava no contexto/evidência)
    if ev.get("exam_days"):
        signals.append({
            "icon": "calendar", "kind": "exam",
            "label": "Prova mais próxima",
            "value": f"em {ev['exam_days']} dia(s)",
        })
    if ev.get("subject_name") and not ev.get("exam_days"):
        signals.append({
            "icon": "book", "kind": "subject",
            "label": "Matéria em foco",
            "value": ev["subject_name"],
        })

    # Curva de esquecimento — revisões vencidas
    if ev.get("due_count"):
        signals.append({
            "icon": "clock", "kind": "due",
            "label": "Cartas com revisão vencida",
            "value": f"{ev['due_count']} item(ns)",
        })

    return signals

def _compose_why_now(rec: dict) -> str:
    """Frase única resumindo POR QUÊ ESTA recomendação AGORA.

    Não é marketing. Não é IA. É a árvore de decisão do motor traduzida
    para 1 frase curta.
    """
    rule = rec.get("rule") or "unknown"
    ev = (rec.get("evidence") or {}).get("data") or {}

    if rule == "saturation_mode":
        return "Detectei sinais de sobrecarga nos últimos check-ins. Hoje priorizo consolidar, não avançar."
    if rule == "spaced_review_due":
        n = ev.get("due_count") or 0
        return f"Você tem {n} carta(s) com revisão vencendo — consolidar rende mais que começar tema novo agora."
    if rule == "recover_neglected_subject":
        s = ev.get("subject_name") or "essa matéria"
        return f"Você não estuda {s} há vários dias — sugeri retomar antes que o esquecimento aumente."
    if rule == "exam_prep_critical":
        d = ev.get("exam_days")
        return f"Prova em {d} dia(s). Reduzi o escopo pra revisão ativa focada."
    if rule == "exam_prep_soon":
        return "Prova se aproximando. Bom momento pra começar revisão ativa antes da pressão aumentar."
    if rule == "checkin_pending":
        return "Ainda não fez check-in hoje — sem isso não consigo escolher a atividade certa."
    if rule == "block_scheduled":
        return "Você tem um bloco reservado agora na sua agenda."
    if rule == "routine_rotation":
        s = ev.get("subject_name")
        if ev.get("is_peak") and s:
            return f"{s} é sua matéria com menos foco na semana, e agora é seu horário de pico — hora de investir carga."
        if s:
            return f"{s} é sua matéria com menos foco na semana, mas você está fora do pico — sugeri uma revisão leve."
    if rule == "explore_free":
        if ev.get("peak_bucket"):
            return "Sem urgência hoje. Deixei uma janela livre pra você escolher."
    if rule == "mental_health_alert":
        return "Sinais de esgotamento apareceram. Cuidado agora é a próxima melhor decisão."
    return "Combinação dos sinais atuais me fez sugerir essa ação."

# ═══════════════════════════════════════════════════════════════════
# _decide_next_action — árvore de decisão P0–P6
# ═══════════════════════════════════════════════════════════════════
async def _decide_next_action(
    user_id: str,
    stats: dict,
    observation: dict | None,
    items: list[dict],
    typical_min: int,
    has_checkin_today: bool,
) -> dict:
    """Retorna a única melhor próxima ação, com evidência e prioridade.

    Ordem de urgência (P6 mais urgente, P0 fallback):
      P6 — SATURAÇÃO (stress alto, humor persistente ruim, abandonos consecutivos)
      P5 — Bem-estar crítico (stress agudo AGORA, sono baixo pattern)
      P4 — Prova crítica / queda de humor
      P3 — Prova 4-7 dias / matéria negligenciada
      P2 — Bloco agendado / check-in pendente
      P1 — Rotina (com hora ótima quando aplicável)
      P0 — Fallback exploração
    """
    from context_engine import (
        is_saturated, peak_bucket_of, optimal_window_label,
        local_hour, hour_bucket, sleep_debt,
    )

    # ─── P6: Saturação — sempre vence tudo ────────────────────
    saturated, sat_ev = await is_saturated(user_id)
    if saturated:
        return {
            "rule": "saturation_mode",
            "action": "small_win",
            "kind": "care",
            "title": "Hoje vale uma pequena vitória",
            "subtitle": "10 flashcards curtos, sem material novo.",
            "reasoning": "Sinais recentes indicam alta carga. Melhor consolidar do que aumentar.",
            "duration_min": 10,
            "action_route": "/tutor",
            "action_label": "Começar 10 min",
            "evidence": {
                "explanation": {
                    "stress_high": "Stress alto no último check-in.",
                    "mood_low_persistent": "Humor baixo persistente nos últimos check-ins.",
                    "sleep_low_persistent": "Sono baixo persistente nos últimos check-ins.",
                    "abandon_streak": "Vários abandonos consecutivos nas últimas 48h.",
                }.get(sat_ev.get("rule"), "Padrão de saturação detectado."),
                "data": sat_ev,
            },
            "priority": 6,
        }

    # ─── Perfil + contexto atual (usado por P5/P3/P1 abaixo) ─
    prof = await db.user_profiles.find_one({"user_id": user_id}, {"_id": 0}) or {}
    peak = peak_bucket_of(prof)
    now_h = local_hour()
    now_bucket = hour_bucket(now_h)
    is_peak = bool(peak and now_bucket == peak)
    optimal_hint = optimal_window_label(peak)

    last_ck = await _last_checkin(user_id)
    obs_rule = observation.get("rule") if observation else None

    # Débito de sono → reduz duração pesada
    debt = sleep_debt(prof, (last_ck or {}).get("sleep")) if last_ck else 0.0
    heavy_min = max(15, typical_min if is_peak else int(typical_min * 0.75))
    if debt >= 2:
        heavy_min = min(heavy_min, 20)

    # ─── P5: Stress crítico AGORA (última check-in stress ≥ 8) ─────
    if last_ck and last_ck.get("stress") is not None and int(last_ck["stress"]) >= 8:
        return {
            "rule": "stress_acute_now",
            "action": "care",
            "kind": "care",
            "title": "Respirar antes de estudar",
            "subtitle": "3 min de respiração guiada.",
            "reasoning": "Seu último check-in indicou stress alto. Hoje vale preservar energia antes de aumentar a carga.",
            "duration_min": 3,
            "action_route": "/mindfulness",
            "action_label": "Começar respiração",
            "evidence": {
                "explanation": f"Stress do último check-in: {int(last_ck['stress'])}/10.",
                "data": {"stress_now": int(last_ck["stress"])},
            },
            "priority": 5,
        }

    # ─── P5: Stress alto recorrente (pattern) — sono ok, mas semana pesada ─
    if obs_rule == "high_stress_pattern":
        subj = await _least_studied_subject_7d(user_id)
        subj_txt = f" de {subj['name']}" if subj else ""
        return {
            "rule": "stress_pattern_light",
            "action": "review_light",
            "kind": "mission",
            "title": f"Revisão leve{subj_txt}",
            "subtitle": "Sessão curta, sem material novo.",
            "reasoning": "Seu stress tem estado alto essa semana. Hoje vale reduzir a carga cognitiva.",
            "duration_min": 20,
            "action_route": _pomodoro_route(subj["id"] if subj else None, 20),
            "action_label": "Começar 20 min",
            "evidence": observation.get("evidence") if observation else {"explanation": "Média de stress alta nos últimos 7d.", "data": {}},
            "priority": 5,
        }

    # ─── P5: Sono baixo pattern (bem-estar clínico) ────────────────
    if obs_rule == "low_sleep_pattern":
        subj = await _least_studied_subject_7d(user_id)
        subj_txt = f" de {subj['name']}" if subj else ""
        return {
            "rule": "low_sleep_reduce_load",
            "action": "review_light",
            "kind": "mission",
            "title": f"Revisão curta{subj_txt}",
            "subtitle": "15 min, matéria mais fresca na cabeça.",
            "reasoning": "Seu sono está baixo há alguns dias. Isso pode afetar sua concentração — hoje evite conteúdo novo.",
            "duration_min": 15,
            "action_route": _pomodoro_route(subj["id"] if subj else None, 15),
            "action_label": "Começar 15 min",
            "evidence": observation.get("evidence") if observation else {"explanation": "Padrão de sono baixo detectado.", "data": {}},
            "priority": 5,
        }

    # ─── P4: Prova crítica (≤3 dias) da lista de priority ─────────
    for it in items:
        if it.get("kind") == "exam":
            why = (it.get("why") or "").lower()
            days_val = None
            # tenta extrair número de dias do why (ex.: "em 3 dia(s)")
            import re
            m = re.search(r"em (\d+)\s*dia", why)
            if m:
                try:
                    days_val = int(m.group(1))
                except Exception:
                    pass
            if days_val is not None and days_val <= 3:
                title = it["title"].split(" — ", 1)[0] if " — " in it["title"] else it["title"]
                return {
                    "rule": "exam_imminent",
                    "action": "review_active",
                    "kind": "exam",
                    "title": f"Revisar {title}",
                    "subtitle": f"Prova em {days_val} dia{'s' if days_val != 1 else ''}. Foque no que ainda não domina.",
                    "reasoning": f"Sua prova é em {days_val} dia{'s' if days_val != 1 else ''}. Priorize revisão ativa agora.",
                    "duration_min": max(30, typical_min),
                    "action_route": "/subjects",
                    "action_label": "Começar agora",
                    "evidence": {
                        "explanation": f"Detectei prova crítica de {title} em {days_val} dia{'s' if days_val != 1 else ''} na sua agenda.",
                        "data": {"subject": title, "days_until_exam": days_val, "priority_source": "exam_critical"},
                    },
                    "priority": 4,
                }

    # ─── P4: Queda de humor (obs.mood_trend_down) — sessão leve ───
    if obs_rule == "mood_trend_down":
        subj = await _least_studied_subject_7d(user_id)
        subj_txt = f" de {subj['name']}" if subj else ""
        return {
            "rule": "mood_down_short_session",
            "action": "review_light",
            "kind": "mission",
            "title": f"Sessão curta{subj_txt}",
            "subtitle": "20 min. Vamos manter o ritmo sem forçar.",
            "reasoning": "Seu humor caiu um pouco. Melhor sessão curta e leve hoje.",
            "duration_min": 20,
            "action_route": _pomodoro_route(subj["id"] if subj else None, 20),
            "action_label": "Começar 20 min",
            "evidence": observation.get("evidence") if observation else {"explanation": "Tendência de humor em queda.", "data": {}},
            "priority": 4,
        }

    # ─── P3: Prova em 4–7 dias (revisão ativa) ────────────────────
    for it in items:
        if it.get("kind") == "exam":
            why = (it.get("why") or "").lower()
            import re
            m = re.search(r"em (\d+)\s*dia", why)
            if m:
                try:
                    days_val = int(m.group(1))
                except Exception:
                    days_val = None
                if days_val is not None and 4 <= days_val <= 7:
                    title = it["title"].split(" — ", 1)[0] if " — " in it["title"] else it["title"]
                    return {
                        "rule": "exam_upcoming",
                        "action": "review_active",
                        "kind": "exam",
                        "title": f"Iniciar revisão de {title}",
                        "subtitle": f"Prova em {days_val} dias. Melhor começar agora.",
                        "reasoning": f"Sua prova de {title} é em {days_val} dias. Comece a revisão ativa hoje.",
                        "duration_min": max(30, typical_min),
                        "action_route": "/subjects",
                        "action_label": "Começar agora",
                        "evidence": {
                            "explanation": f"Prova de {title} em {days_val} dias.",
                            "data": {"subject": title, "days_until_exam": days_val},
                        },
                        "priority": 3,
                    }

    # ─── P3: Curva de esquecimento (revisão espaçada vencida) ─────
    # Se há ≥3 conteúdos com revisão vencida agora, isso vira P3 —
    # revisar é sempre mais eficaz que abrir conteúdo novo enquanto
    # há dívida cognitiva. Só age com ao menos 3 itens (menos que isso
    # é ruído; melhor deixar o aluno seguir a rotina).
    try:
        import spaced_review as _sr
        due_n = await _sr.due_count(user_id)
    except Exception:  # noqa: BLE001
        due_n = 0
    if due_n >= 3:
        dur = 10 if due_n <= 5 else (15 if due_n <= 12 else 20)
        return {
            "rule": "spaced_review_due",
            "action": "review",
            "kind": "mission",
            "title": f"Revisar {due_n} cartas vencendo",
            "subtitle": "Revisão espaçada mantém o que você já aprendeu.",
            "reasoning": "Consolidar o que está esquecendo rende mais que abrir tema novo.",
            "duration_min": dur,
            "action_route": "/tutor?mode=due",
            "action_label": f"Revisar {due_n} agora",
            "evidence": {
                "explanation": f"{due_n} conteúdo(s) com revisão vencida — curva de esquecimento sinalizando.",
                "data": {"due_count": due_n},
            },
            "priority": 3,
        }

    # ─── P3: Matéria negligenciada (obs.subject_neglected) ────────
    if obs_rule == "subject_neglected":
        ev = observation.get("evidence") or {}
        data = ev.get("data") or {}
        subj_name = data.get("subject_name") or "sua matéria em atraso"
        subj_id = data.get("subject_id")
        # P0.2.2.5 — enriquece com o subtema mais fraco (memória de aprendizagem)
        subtopic_hint = None
        try:
            import learning_memory as _lm
            weak = await _lm.weakest_topic(user_id, subj_name)
            if weak and weak.get("subtopic"):
                subtopic_hint = weak["subtopic"]
        except Exception:  # noqa: BLE001
            pass
        title = f"Recuperar {subj_name}"
        if subtopic_hint:
            title = f"Recuperar {subj_name} · {subtopic_hint}"
        return {
            "rule": "recover_neglected_subject",
            "action": "recover",
            "kind": "mission",
            "title": title,
            "subtitle": "30 min pra retomar o contato antes de esquecer.",
            "reasoning": f"Você não estuda {subj_name} há alguns dias. Vale recuperar antes de acumular.",
            "duration_min": 30,
            "action_route": _pomodoro_route(subj_id, 30),
            "action_label": "Começar 30 min",
            "evidence": ev if ev else {"explanation": "Matéria negligenciada nos últimos 14 dias.", "data": {}},
            "priority": 3,
        }

    # ─── P2: Bloco agendado agora ─────────────────────────────────
    for it in items:
        if it.get("kind") == "block" and not it.get("done") and it.get("category") in ("study", "academic"):
            starts = it.get("start_time")
            return {
                "rule": "scheduled_block_now",
                "action": "block",
                "kind": "block",
                "title": it["title"],
                "subtitle": f"Começa às {starts}." if starts else "Agendado para hoje.",
                "reasoning": "Você já tem esse bloco de estudo planejado para agora.",
                "duration_min": typical_min,
                "action_route": "/pomodoro",
                "action_label": "Começar agora",
                "evidence": {
                    "explanation": f"Bloco '{it['title']}' agendado na sua agenda para hoje.",
                    "data": {"block_title": it["title"], "start_time": starts},
                },
                "priority": 2,
            }

    # ─── P2: Check-in pendente hoje (horário adequado) ────────────
    local_hour = (_now().hour - 3) % 24
    if not has_checkin_today and 6 <= local_hour < 22:
        return {
            "rule": "checkin_pending",
            "action": "checkin",
            "kind": "checkin",
            "title": "Fazer o check-in de hoje",
            "subtitle": "1 minuto pra eu entender seu contexto.",
            "reasoning": "Ainda não sei como você está hoje. Um check-in rápido calibra tudo o mais.",
            "duration_min": 1,
            "action_route": "/checkin",
            "action_label": "Começar",
            "evidence": {
                "explanation": "Você ainda não fez check-in hoje.",
                "data": {"has_checkin_today": False, "local_hour": local_hour},
            },
            "priority": 2,
        }

    # ─── P1: Rotina — bloco padrão na matéria menos estudada ─────
    subj = await _least_studied_subject_7d(user_id)
    if subj:
        if is_peak:
            title = f"Foco em {subj['name']}"
            subtitle_parts = [f"Bloco de {heavy_min} min."]
            if optimal_hint:
                subtitle_parts.append("Este é seu horário de pico.")
            duration = heavy_min
            reasoning = (
                f"{subj['name']} é a matéria com menos tempo de foco nos últimos 7 dias, "
                f"e agora é seu período de maior rendimento."
            )
        else:
            duration = min(20, heavy_min)
            title = f"Revisão leve — {subj['name']}"
            subtitle_parts = [f"Sessão curta de {duration} min."]
            if optimal_hint:
                subtitle_parts.append(optimal_hint)
            reasoning = (
                f"Fora do seu pico de energia — melhor uma revisão leve. "
                f"Guardar {subj['name']} para o horário ideal."
            )
        return {
            "rule": "routine_rotation",
            "action": "study",
            "kind": "mission",
            "title": title,
            "subtitle": " ".join(subtitle_parts),
            "reasoning": reasoning,
            "duration_min": duration,
            "action_route": _pomodoro_route(subj["id"], duration),
            "action_label": "Começar agora",
            "evidence": {
                "explanation": f"Nos últimos 7 dias, {subj['name']} teve o menor tempo de foco entre suas matérias.",
                "data": {
                    "subject_id": subj["id"], "subject_name": subj["name"],
                    "hour_bucket_now": now_bucket, "peak_bucket": peak,
                    "is_peak": is_peak, "sleep_debt_h": debt,
                },
            },
            "optimal_window": optimal_hint,
            "priority": 1,
        }

    # ─── P0: Fallback — exploração livre ───────────────────────────
    return {
        "rule": "explore_free",
        "action": "explore",
        "kind": "explore",
        "title": "Sem urgência pra hoje",
        "subtitle": "Bom momento pra revisar algo por conta própria."
                    + (f" {optimal_hint}" if optimal_hint else ""),
        "reasoning": "Nada crítico na sua agenda. Escolha o que fizer mais sentido.",
        "duration_min": min(typical_min, heavy_min),
        "action_route": "/pomodoro",
        "action_label": "Iniciar bloco de foco",
        "evidence": {
            "explanation": "Nenhuma prova próxima, nenhum bloco agendado, sem padrões que exijam ação específica.",
            "data": {"hour_bucket_now": now_bucket, "peak_bucket": peak, "is_peak": is_peak},
        },
        "optimal_window": optimal_hint,
        "priority": 0,
    }
