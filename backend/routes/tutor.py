"""Tutor IA — Feedback Inteligente de Provas.

Usa emergentintegrations (Claude Sonnet 4.5) para:
1) analisar a devolutiva de uma prova (tópicos fracos + acertos);
2) gerar 10 questões de revisão focadas nos tópicos fracos;
3) devolver feedback detalhado sobre a evolução do aluno.

Persistência: `db.exam_feedbacks` guarda cada análise por usuário.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from content_policy import MEDFLOW_CONTENT_POLICY
from core import _clean, _iso, _now, db, logger, require_user

router = APIRouter(prefix="/api/tutor", tags=["tutor"])


class ExamFeedbackInput(BaseModel):
    subject: str  # ex: "Anatomia"
    exam_name: Optional[str] = None
    grade: Optional[float] = None  # 0..10
    weak_topics: str  # texto livre com tópicos onde errou
    strong_topics: Optional[str] = None  # texto livre com o que acertou
    notes: Optional[str] = None  # observações extras do aluno


def normalize_topics_key(items) -> str:
    """Chave determinística de tópicos para a identidade do cache da Devolutiva.

    Aceita lista/tupla/set de tópicos, texto livre com separadores (`,` `;`
    `/` ou nova linha) ou None/vazio. NUNCA itera uma string caractere por
    caractere (P0: isso gerava colisão por multiset de caracteres/anagrama).
    """
    if items is None:
        return ""
    if isinstance(items, str):
        raw = re.split(r"[,;/\n\r]+", items)
    elif isinstance(items, (list, tuple, set, frozenset)):
        raw = []
        for it in items:
            if isinstance(it, str):
                raw.extend(re.split(r"[,;/\n\r]+", it))
            else:
                raw.append(str(it))
    else:
        raw = re.split(r"[,;/\n\r]+", str(items))

    cleaned = []
    for t in raw:
        norm = re.sub(r"\s+", " ", str(t)).strip().lower()
        if norm and norm not in cleaned:
            cleaned.append(norm)
    cleaned.sort()
    return ",".join(cleaned)[:120]


def exam_feedback_key_fields(
    *, user_id: str, subject: str, weak_topics, period_bucket: str
) -> dict:
    """Identidade de cache da Devolutiva — inclui `user_id` (P0 cross-user).

    Escopo restrito ao kind `exam_feedback`. Outros kinds do content_memory
    continuam com reuso cross-user (conteúdo seguro para compartilhamento).
    """
    return {
        "user_id": str(user_id),
        "discipline": subject,
        "topic": "exam_feedback",
        "subtopic": normalize_topics_key(weak_topics),
        "period_bucket": period_bucket,
    }


def _extract_json(text: str) -> dict:
    """Tenta encontrar o primeiro bloco JSON no texto (tolerante a fences)."""
    if not text:
        return {}
    # remove fences ```json ... ```
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if not candidate:
        # tenta pegar do primeiro { até o último }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end + 1]
    if not candidate:
        return {}
    try:
        return json.loads(candidate)
    except Exception:
        return {}


async def _call_llm_raw(system: str, user_msg: str) -> str:
    """Chama o roteador (tier `structured`) SEM consumir quota — para permitir
    retry de JSON sem cobrar duas gerações do aluno. Levanta 502 se todos os
    providers caírem.
    """
    from ai_router import smart_chat, AIRouterError

    try:
        result = await smart_chat(
            system=system,
            user_msg=user_msg,
            tier="structured",
            temperature=0.4,
            max_tokens=2400,
            prefer="emergent",  # FASE 2: Gemini Flash primeiro, Claude fallback
        )
        logger.info("Tutor _call_llm: provider=%s latency_ms=%s",
                    result["provider"], result["latency_ms"])
        return result["text"]
    except AIRouterError as exc:
        logger.exception("Tutor router: all providers failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="O tutor IA está temporariamente indisponível. Tente novamente em instantes.",
        )


SYSTEM_PROMPT = (
    "Você é um tutor experiente para estudantes de Medicina brasileiros do 1º ao 3º período. "
    "Seu papel é dar feedback educacional acolhedor e prático sobre o desempenho em provas. "
    "Sempre responda em português do Brasil. "
    "SEMPRE devolva a resposta em JSON válido, sem texto extra, seguindo estritamente o schema pedido."
)

# Etapa 1 (P0-1): a política central de qualidade entra ANTES do prompt específico
# da Devolutiva. A política é invariante; SYSTEM_PROMPT mantém a identidade da
# operação (feedback de desempenho). Composição explícita e auditável.
DEVOLUTIVA_SYSTEM = f"{MEDFLOW_CONTENT_POLICY}\n\n{SYSTEM_PROMPT}"


@router.post("/exam-feedback")
async def generate_exam_feedback(payload: ExamFeedbackInput, user: dict = Depends(require_user)) -> dict:
    grade_txt = f"{payload.grade:.1f}" if payload.grade is not None else "não informada"
    prompt = (
        "O aluno recebeu uma devolutiva de prova. Analise e produza:\n"
        "- um diagnóstico curto (2-3 frases) sobre o desempenho;\n"
        "- 3 áreas prioritárias de foco (com plano curto de estudo em bullets);\n"
        "- 10 questões objetivas de revisão baseadas nos tópicos fracos, com 4 alternativas cada, "
        "gabarito e comentário curto.\n\n"
        f"Matéria: {payload.subject}\n"
        f"Nome da prova: {payload.exam_name or 'não informado'}\n"
        f"Nota: {grade_txt}\n"
        f"Tópicos fracos (onde errou): {payload.weak_topics}\n"
        f"Tópicos fortes (onde acertou): {payload.strong_topics or 'não informado'}\n"
        f"Observações do aluno: {payload.notes or 'nenhuma'}\n\n"
        "Formato de saída (JSON estrito):\n"
        "{\n"
        '  "diagnosis": "texto curto",\n'
        '  "focus_areas": [{"topic": "...", "plan": ["passo1", "passo2", "passo3"]}, ... 3 itens ...],\n'
        '  "questions": [\n'
        '    {"stem": "enunciado", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "answer": "A", "explanation": "por quê"},\n'
        '    ... 10 itens ...\n'
        "  ]\n"
        "}"
    )
    # ── Content Memory Engine — reuso INTRA-USER apenas (P0: cross-user removido) ──
    # Bucket de nota: baixa (<5) / média (5-7) / alta (>7). O reuso ocorre só
    # para o mesmo aluno repetindo a mesma necessidade.
    import learning_memory as lm
    def _grade_bucket(g):
        try:
            v = float(g)
        except Exception:
            return "unknown"
        return "low" if v < 5 else "high" if v > 7 else "mid"
    prof = await db.user_profiles.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
    period_bucket = lm._period_bucket(prof.get("period_number") or prof.get("semester"))

    # ── P0: isolamento cross-user. `user_id` faz parte da IDENTIDADE do cache
    # da Devolutiva: dois alunos NUNCA compartilham uma entrada de exam_feedback,
    # mesmo com subject/tópicos/period_bucket/grade_bucket idênticos. O reuso
    # intra-user (mesmo aluno, mesma necessidade) é preservado.
    key_fields = exam_feedback_key_fields(
        user_id=user["user_id"],
        subject=payload.subject,
        weak_topics=payload.weak_topics,
        period_bucket=period_bucket,
    )
    variant = f"grade-{_grade_bucket(payload.grade)}"

    async def _gen_exam_feedback() -> dict:
        from ai_quota import consume_ai_quota
        from json_utils import repair_and_parse
        # Quota consumida UMA vez (só em cache miss); o retry de JSON não recobra.
        await consume_ai_quota(user["user_id"], "feedback")
        for attempt in range(2):  # parse normal + 1 retry controlado
            raw = await _call_llm_raw(DEVOLUTIVA_SYSTEM, prompt)
            parsed = repair_and_parse(raw)
            if isinstance(parsed, dict) and parsed.get("questions"):
                return parsed
            logger.warning("exam_feedback: JSON inválido/insuficiente (tentativa %d/2)", attempt + 1)
        raise HTTPException(status_code=502, detail="Resposta do tutor IA inválida. Tente novamente.")

    memo = await lm.remember_or_generate(
        kind="exam_feedback",
        key_fields=key_fields,
        generator=_gen_exam_feedback,
        variant=variant,
        generator_label="ai:router-structured",
        user_id=user["user_id"],
    )
    parsed = memo["content"]["payload"]

    doc = {
        "id": f"tf_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"],
        "subject": payload.subject,
        "exam_name": payload.exam_name,
        "grade": payload.grade,
        "weak_topics": payload.weak_topics,
        "strong_topics": payload.strong_topics,
        "notes": payload.notes,
        "diagnosis": parsed.get("diagnosis"),
        "focus_areas": parsed.get("focus_areas") or [],
        "questions": parsed.get("questions") or [],
        "answers_given": {},  # map question_index -> letter
        "score": None,
        "content_id": memo["content"]["id"],
        "content_source": memo["source"],
        "created_at": _iso(_now()),
    }
    await db.exam_feedbacks.insert_one(dict(doc))
    return {"feedback": _clean(doc)}


@router.post("/exam-feedback/stream")
async def generate_exam_feedback_stream(
    payload: ExamFeedbackInput, user: dict = Depends(require_user)
):
    """SSE keep-alive da Devolutiva — mesma geração/validação, sem estourar o
    timeout ~60s do ingress em gerações longas."""
    from sse_utils import sse_response
    return sse_response(generate_exam_feedback(payload, user))


@router.get("/exam-feedback")
async def list_feedbacks(user: dict = Depends(require_user)) -> dict:
    items = await db.exam_feedbacks.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"items": items}


@router.get("/exam-feedback/{feedback_id}")
async def get_feedback(feedback_id: str, user: dict = Depends(require_user)) -> dict:
    doc = await db.exam_feedbacks.find_one(
        {"id": feedback_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Devolutiva não encontrada")
    return {"feedback": doc}


class AnswersInput(BaseModel):
    answers: dict  # {"0": "A", "1": "C", ...}


@router.post("/exam-feedback/{feedback_id}/answers")
async def submit_answers(feedback_id: str, payload: AnswersInput, user: dict = Depends(require_user)) -> dict:
    doc = await db.exam_feedbacks.find_one(
        {"id": feedback_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Devolutiva não encontrada")
    questions = doc.get("questions") or []
    correct = 0
    detail = []
    for i, q in enumerate(questions):
        given = (payload.answers.get(str(i)) or "").strip().upper()[:1]
        expected = (q.get("answer") or "").strip().upper()[:1]
        ok = bool(given) and given == expected
        if ok:
            correct += 1
        detail.append({
            "index": i,
            "stem": q.get("stem"),
            "given": given,
            "expected": expected,
            "correct": ok,
            "explanation": q.get("explanation"),
        })
    total = len(questions) or 1
    score = round((correct / total) * 10, 1)
    await db.exam_feedbacks.update_one(
        {"id": feedback_id, "user_id": user["user_id"]},
        {"$set": {"answers_given": payload.answers, "score": score,
                  "reviewed_at": _iso(_now())}},
    )
    return {"score": score, "correct": correct, "total": total, "detail": detail}


@router.delete("/exam-feedback/{feedback_id}")
async def delete_feedback(feedback_id: str, user: dict = Depends(require_user)) -> dict:
    await db.exam_feedbacks.delete_one({"id": feedback_id, "user_id": user["user_id"]})
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# Meu Tutor — Centro de Aprendizagem Inteligente (P0.2.3)
#
# Orquestrador dos 5 modos de aprendizagem:
#   1. exam_tomorrow  — treino focado antes de uma prova
#   2. post_exam      — devolutiva (mantém fluxo antigo acima)
#   3. diagnostic     — quiz diagnóstico multi-tema
#   4. quick_review   — revisão rápida (5/10/20/40 min)
#   5. guide_me       — MedFlow decide (usa /home/today)
#
# Cada modo devolve um "plano" (lista de slots). O frontend consome os
# slots via /api/learning/request — que reutiliza conteúdo existente ou
# gera via Claude (transparente pro aluno).
# ═══════════════════════════════════════════════════════════════════


class TutorPlanIn(BaseModel):
    mode: str  # exam_tomorrow | diagnostic | quick_review | guide_me
    discipline: Optional[str] = None
    topics: Optional[list[str]] = None
    time_min: Optional[int] = None
    energy: Optional[str] = None  # low | medium | high


def _period_bucket_from_semester(s: Optional[int]) -> Optional[int]:
    if s is None:
        return None
    try:
        return int(s)
    except Exception:
        return None


async def _build_slots_exam_tomorrow(
    discipline: str, topics: list[str], time_min: int, period: Optional[int]
) -> list[dict]:
    """Monta a sequência ideal para provar amanhã.

    Distribuição do tempo (aproximada, sempre em blocos de 5 min):
      15% aquecimento (flashcards)
      55% quiz (questões)
      20% aprofundamento (explicação do subtema mais crítico)
      10% revisão final (bullets)
    """
    time_min = max(10, min(time_min, 240))
    topics = topics[:5] if topics else [discipline]

    warmup_flash = max(1, min(5, time_min // 12))
    quiz_qs = max(2, min(8, time_min // 6))

    slots: list[dict] = []
    # Aquecimento — 1 flashcard por tema (limitado)
    for t in topics[:warmup_flash]:
        slots.append({
            "id": f"slot_{uuid.uuid4().hex[:8]}",
            "kind": "flashcard",
            "discipline": discipline,
            "topic": t,
            "subtopic": None,
            "period": period,
            "duration_min": 2,
            "label": f"Aquecimento — {t}",
            "phase": "warmup",
        })
    # Quiz — 1 questão por tema, distribuídas
    for i in range(quiz_qs):
        t = topics[i % len(topics)]
        slots.append({
            "id": f"slot_{uuid.uuid4().hex[:8]}",
            "kind": "question",
            "discipline": discipline,
            "topic": t,
            "subtopic": None,
            "period": period,
            "duration_min": 3,
            "label": f"Questão {i+1} — {t}",
            "phase": "quiz",
        })
    # Aprofundamento — explicação do 1º tema
    slots.append({
        "id": f"slot_{uuid.uuid4().hex[:8]}",
        "kind": "explanation",
        "discipline": discipline,
        "topic": topics[0],
        "subtopic": None,
        "period": period,
        "duration_min": max(5, time_min // 6),
        "label": f"Aprofundar — {topics[0]}",
        "phase": "deep_dive",
    })
    # Revisão final — resumo com bullets
    slots.append({
        "id": f"slot_{uuid.uuid4().hex[:8]}",
        "kind": "summary",
        "discipline": discipline,
        "topic": topics[0],
        "subtopic": None,
        "period": period,
        "duration_min": 3,
        "label": "Revisão final",
        "phase": "recap",
    })
    return slots


async def _build_slots_quick_review(
    user_id: str, time_min: int, discipline: Optional[str], period: Optional[int]
) -> list[dict]:
    """Revisão rápida em 5/10/20/40 min.

    Prioriza o subtópico mais fraco do aluno. Se não houver dados,
    cai para uma pergunta genérica na disciplina informada.
    """
    time_min = max(5, min(time_min, 120))

    import learning_memory as lm
    weak = await lm.weakest_topic(user_id, discipline)
    d = discipline or (weak["topic"].split("/")[0] if weak else "Anatomia")
    t = weak["topic"] if weak else d
    st = weak.get("subtopic") if weak else None

    slots: list[dict] = []
    if time_min <= 5:
        # 5 min: 2 flashcards
        for i in range(2):
            slots.append({
                "id": f"slot_{uuid.uuid4().hex[:8]}",
                "kind": "flashcard", "discipline": d, "topic": t, "subtopic": st,
                "period": period, "duration_min": 2,
                "label": f"Flashcard {i+1}", "phase": "review",
            })
    elif time_min <= 10:
        # 10 min: 3 flashcards + 1 questão
        for i in range(3):
            slots.append({
                "id": f"slot_{uuid.uuid4().hex[:8]}",
                "kind": "flashcard", "discipline": d, "topic": t, "subtopic": st,
                "period": period, "duration_min": 2,
                "label": f"Flashcard {i+1}", "phase": "review",
            })
        slots.append({
            "id": f"slot_{uuid.uuid4().hex[:8]}",
            "kind": "question", "discipline": d, "topic": t, "subtopic": st,
            "period": period, "duration_min": 4,
            "label": "Questão de fixação", "phase": "quiz",
        })
    elif time_min <= 20:
        # 20 min: 3 questões + 1 explicação
        for i in range(3):
            slots.append({
                "id": f"slot_{uuid.uuid4().hex[:8]}",
                "kind": "question", "discipline": d, "topic": t, "subtopic": st,
                "period": period, "duration_min": 4,
                "label": f"Questão {i+1}", "phase": "quiz",
            })
        slots.append({
            "id": f"slot_{uuid.uuid4().hex[:8]}",
            "kind": "explanation", "discipline": d, "topic": t, "subtopic": st,
            "period": period, "duration_min": 6,
            "label": "Aprofundar", "phase": "deep_dive",
        })
    else:
        # 40+ min: 5 questões + 1 explicação + 1 summary
        for i in range(5):
            slots.append({
                "id": f"slot_{uuid.uuid4().hex[:8]}",
                "kind": "question", "discipline": d, "topic": t, "subtopic": st,
                "period": period, "duration_min": 5,
                "label": f"Questão {i+1}", "phase": "quiz",
            })
        slots.append({
            "id": f"slot_{uuid.uuid4().hex[:8]}",
            "kind": "explanation", "discipline": d, "topic": t, "subtopic": st,
            "period": period, "duration_min": 8,
            "label": "Aprofundar", "phase": "deep_dive",
        })
        slots.append({
            "id": f"slot_{uuid.uuid4().hex[:8]}",
            "kind": "summary", "discipline": d, "topic": t, "subtopic": st,
            "period": period, "duration_min": 3,
            "label": "Revisão final", "phase": "recap",
        })
    return slots


async def _build_slots_diagnostic(discipline: str, period: Optional[int]) -> list[dict]:
    """Quiz diagnóstico — 6 questões variadas na disciplina.

    Como ainda não temos taxonomia canônica de tópicos, pedimos ao aluno
    a disciplina e usamos variantes (v1..v6) pra forçar diversidade no
    fingerprint (evita colidir todas na mesma pergunta reutilizada).
    """
    slots: list[dict] = []
    for i in range(6):
        slots.append({
            "id": f"slot_{uuid.uuid4().hex[:8]}",
            "kind": "question",
            "discipline": discipline,
            "topic": discipline,  # sem subdivisão — o LLM diversifica
            "subtopic": None,
            "period": period,
            "duration_min": 3,
            "label": f"Diagnóstico {i+1}",
            "phase": "diagnostic",
            "variant": f"diag-{i+1}",
        })
    return slots


@router.post("/plan")
async def tutor_plan(body: TutorPlanIn, user: dict = Depends(require_user)) -> dict:
    """Orquestrador do "Meu Tutor". Devolve plano (lista de slots)."""
    valid_modes = {"exam_tomorrow", "diagnostic", "quick_review", "guide_me"}
    if body.mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Modo inválido. Válidos: {sorted(valid_modes)}")

    # Puxa o período do perfil (anonimiza em bucket na hora de gerar)
    prof = await db.user_profiles.find_one({"user_id": user["user_id"]}, {"_id": 0})
    period = _period_bucket_from_semester((prof or {}).get("semester") or (prof or {}).get("period_number"))

    if body.mode == "exam_tomorrow":
        if not body.discipline or not body.topics:
            raise HTTPException(status_code=400, detail="Informe disciplina e ao menos 1 tópico.")
        time_min = body.time_min or 40
        slots = await _build_slots_exam_tomorrow(body.discipline, body.topics, time_min, period)
        title = f"Treino focado — {body.discipline}"
        subtitle = f"{len(slots)} atividades para hoje. Vamos por partes."

    elif body.mode == "diagnostic":
        if not body.discipline:
            raise HTTPException(status_code=400, detail="Informe a disciplina do diagnóstico.")
        slots = await _build_slots_diagnostic(body.discipline, period)
        title = f"Diagnóstico — {body.discipline}"
        subtitle = "6 questões para eu descobrir o que você domina."

    elif body.mode == "quick_review":
        time_min = body.time_min or 10
        slots = await _build_slots_quick_review(user["user_id"], time_min, body.discipline, period)
        title = "Revisão rápida"
        subtitle = f"{time_min} min. Vou focar no que você mais precisa."

    else:  # guide_me
        import learning_memory as lm
        weak = await lm.weakest_topic(user["user_id"])
        if weak:
            slots = await _build_slots_quick_review(user["user_id"], 20, None, period)
            title = "Hoje eu faria isto"
            subtitle = f"Percebi lacuna em {weak.get('topic')}. Vamos reforçar."
        else:
            # sem dados suficientes → um flashcard exploratório
            slots = [{
                "id": f"slot_{uuid.uuid4().hex[:8]}",
                "kind": "flashcard",
                "discipline": body.discipline or "Anatomia",
                "topic": body.discipline or "Fundamentos",
                "subtopic": None,
                "period": period,
                "duration_min": 3,
                "label": "Vamos começar simples",
                "phase": "explore",
            }]
            title = "Hoje eu faria isto"
            subtitle = "Ainda estou aprendendo você. Vamos testar uma coisa e ajustar."

    return {
        "mode": body.mode,
        "title": title,
        "subtitle": subtitle,
        "created_at": _iso(_now()),
        "slots": slots,
        "total_duration_min": sum(s.get("duration_min", 0) for s in slots),
    }


@router.get("/mastery-map")
async def mastery_map(user: dict = Depends(require_user)) -> dict:
    """Mapa de domínio hierárquico do aluno — disciplina → tópico → subtópico.

    Cada nível carrega:
      score (0..1, None quando ainda em learning)
      seen, correct, incorrect, answered
      last_seen_at

    Filosofia: mostrar SÓ o que foi visto. Não inventar taxonomia — o mapa
    cresce organicamente conforme o aluno estuda.
    """
    import learning_memory as lm
    flat = await lm.student_mastery(user["user_id"])
    topics = flat.get("topics", [])

    tree: dict[str, dict] = {}
    for t in topics:
        d = t["discipline"]
        tp = t["topic"]
        st = t.get("subtopic") or ""
        disc = tree.setdefault(d, {
            "discipline": d, "topics": {}, "seen": 0, "correct": 0, "incorrect": 0,
        })
        topic = disc["topics"].setdefault(tp, {
            "topic": tp, "subtopics": [], "seen": 0, "correct": 0, "incorrect": 0,
        })
        topic["subtopics"].append({
            "subtopic": st,
            "score": t["mastery_score"],
            "seen": t["seen"],
            "answered": t["answered"],
            "correct": t["correct"],
            "incorrect": t["incorrect"],
            "last_seen_at": t["last_seen_at"],
        })
        for f in ("seen", "correct", "incorrect"):
            topic[f] += t[f]
            disc[f] += t[f]

    def _agg_score(d):
        answered = d["correct"] + d["incorrect"]
        if answered < 3:
            return None
        raw = (d["correct"] - d["incorrect"]) / answered
        return round((raw + 1) / 2, 3)

    out: list[dict] = []
    for d in tree.values():
        d_topics = []
        for tp in d["topics"].values():
            tp["score"] = _agg_score(tp)
            tp["answered"] = tp["correct"] + tp["incorrect"]
            d_topics.append(tp)
        d_topics.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0)))
        out.append({
            "discipline": d["discipline"],
            "score": _agg_score(d),
            "seen": d["seen"],
            "answered": d["correct"] + d["incorrect"],
            "correct": d["correct"],
            "incorrect": d["incorrect"],
            "topics": d_topics,
        })
    out.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0)))

    return {
        "disciplines_count": len(out),
        "disciplines": out,
        "empty": len(out) == 0,
    }



# ═══════════════════════════════════════════════════════════════════
# Tutor Fast Chat — resposta conversacional rápida (Groq preferido)
# ═══════════════════════════════════════════════════════════════════

class TutorChatIn(BaseModel):
    message: str
    context: Optional[str] = None  # matéria ou tópico atual (opcional)
    prefer: Optional[str] = None   # "groq" | "openai" | "emergent" (override)


_TUTOR_CHAT_SYSTEM = (
    "Você é o Preceptor IA do MedFlow, professor de Medicina para residência brasileira. "
    "Para dúvidas rápidas, responda de modo direto, profundo e clínico — sem transformar "
    "uma pergunta simples em aula longa. Construa mecanismo, relação causa-efeito, uma "
    "pegadinha de prova quando for útil e aplicação clínica. Nunca use tom infantil, "
    "Wikipédia ou lista superficial. Se a pergunta for ampla, entregue a ideia central e "
    "sugira o próximo recorte. Responda em português brasileiro e não invente dados clínicos. "
    "REGRAS DE PRECISÃO: (1) Abra SEMPRE com a resposta central direta à pergunta feita, "
    "em uma frase, antes de qualquer contexto. (2) Permaneça fiel ao fenômeno perguntado: "
    "não desvie para diagnósticos, patologias ou cenários que o aluno não perguntou. "
    "(3) Diferencie claramente achado fisiológico normal de patológico. "
    "(4) Se a informação exata não for conhecida com certeza, diga o que é confiável e "
    "o que é incerto — não preencha com achismo."
)


@router.post("/chat")
async def tutor_chat(body: TutorChatIn, user: dict = Depends(require_user)) -> dict:
    """Chat rápido do Tutor IA — usa o roteador com tier `fast`.

    Ordem preferencial: Groq (llama-3.3-70b, ~500ms) → OpenAI (gpt-4o-mini) →
    Claude via Emergent. Fallback automático.
    """
    from ai_router import smart_chat, AIRouterError
    from ai_quota import consume_ai_quota

    user_msg = body.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Mensagem vazia")
    if body.context:
        user_msg = f"[Contexto: {body.context}]\n\n{user_msg}"

    await consume_ai_quota(user["user_id"], "tutor")

    try:
        result = await smart_chat(
            system=_TUTOR_CHAT_SYSTEM,
            user_msg=user_msg,
            tier="fast",
            temperature=0.4,
            max_tokens=500,
            prefer=body.prefer,
        )
    except AIRouterError as exc:
        logger.exception("Tutor chat router failed: %s", exc)
        raise HTTPException(status_code=502, detail="Tutor indisponível no momento.")

    return {
        "text": result["text"],
        "provider": result["provider"],
        "model": result["model"],
        "latency_ms": result["latency_ms"],
    }
