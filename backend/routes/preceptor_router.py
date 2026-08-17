"""Preceptor Router — Centro de Aprendizagem Inteligente.

Endpoint universal `/api/tutor/preceptor/interpret` recebe uma entrada
livre (texto, arquivo, voz transcrita) e devolve:
  - intent detectada
  - missão recomendada (com deep-link para o módulo do MedFlow)
  - opção "Revisão Completa" quando aplicável
  - resposta imediata curta do preceptor

A ideia é o aluno NUNCA precisar escolher a ferramenta.
Ele apenas diz o que precisa; o Preceptor conduz.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from ai_router import AIRouterError, smart_chat
from core import _iso, _now, db, logger, require_user
from curriculum_router import route_curriculum
from flashcard_dedup import dedupe_and_complete, synthesize_from_content
from preceptor_pedagogy import (
    PRECEPTOR_SYSTEM,
    focused_prompt,
    memorization_prompt,
    premium_review_prompt,
)

router = APIRouter(prefix="/api/tutor/preceptor", tags=["preceptor-router"])


# ─── Regex-based intent detection (0 tokens) ────────────────────────

_INTENTS = [
    # (pattern, intent, mission, priority)
    (r"prova\s+(em|no)\s+(\d+)\s*dias?", "study_plan", "planejar", 100),
    (r"tenho\s+prova.{0,20}(dia|semana|mês)", "study_plan", "planejar", 100),
    (r"cronograma", "study_plan", "planejar", 90),
    (r"plano\s+de\s+estud", "study_plan", "planejar", 90),

    (r"\b[a-d]\s*\).*\b[a-d]\s*\).*\b[a-d]\s*\)", "question_analysis", "resolver_duvida", 100),
    (r"\benunciad[oa]", "question_analysis", "resolver_duvida", 95),
    (r"analise\s+esta\s+quest[ãa]o", "question_analysis", "resolver_duvida", 100),
    (r"explique\s+esta\s+quest[ãa]o", "question_analysis", "resolver_duvida", 100),
    (r"por\s+que.{0,20}(correta|errada|resposta)", "question_analysis", "resolver_duvida", 90),

    (r"gere?\s+(um\s+)?simulado", "quiz_generation", "treinar", 100),
    (r"gere?\s+(quest[õo]es|perguntas)", "quiz_generation", "treinar", 95),
    (r"simulado\s+sobre", "quiz_generation", "treinar", 100),
    (r"quero\s+treinar", "quiz_generation", "treinar", 80),

    (r"flashcards?", "flashcards", "memorizar", 100),
    (r"anki", "flashcards", "memorizar", 90),
    (r"memorizar", "flashcards", "memorizar", 85),

    (r"resum[eao]\s+(este|esse|esta|essa|deste|desta)", "summary", "revisar", 100),
    (r"resum[oa]\s+em\s+\d+", "summary", "revisar", 95),
    (r"fa[çc]a\s+um\s+resumo", "summary", "revisar", 95),
    (r"tldr", "summary", "revisar", 80),

    (r"mapa\s+mental", "mind_map", "revisar", 100),
    (r"fluxograma", "flowchart", "revisar", 100),

    (r"revis[ãa]o\s+r[áa]pida", "quick_review", "revisar", 95),
    (r"revisar\s+", "review", "revisar", 80),
    (r"^\s*revis[ãa]o\s", "review", "revisar", 80),

    (r"explique?\s+", "explanation", "resolver_duvida", 80),
    (r"o\s+que\s+é\s+", "explanation", "resolver_duvida", 85),
    (r"como\s+funciona", "explanation", "resolver_duvida", 80),

    (r"caso\s+cl[íi]nico", "clinical_case", "treinar", 90),
    (r"vinheta", "clinical_case", "treinar", 85),

    (r"transforme\s+em\s+flashcards", "flashcards", "memorizar", 100),
    (r"transforme\s+em\s+resumo", "summary", "revisar", 100),
]


def _regex_intent(text: str) -> Optional[dict]:
    t = (text or "").lower().strip()
    best = None
    for pat, intent, mission, priority in _INTENTS:
        if re.search(pat, t):
            if not best or priority > best["priority"]:
                best = {"intent": intent, "mission": mission, "priority": priority,
                        "matched": pat}
    return best


# ─── LLM fallback classifier (barato via Groq) ───────────────────────

_INTERPRET_SYSTEM = """Você é o Preceptor Med Flow — interpreta o que o aluno quer aprender.

Dada a mensagem do aluno, devolva SOMENTE um JSON válido com:
{
  "intent": "study_plan | question_analysis | quiz_generation | flashcards | summary | mind_map | flowchart | quick_review | review | explanation | clinical_case | greeting | unknown",
  "mission": "resolver_duvida | treinar | revisar | memorizar | planejar | conversar",
  "topic": "tema/disciplina extraído em português (curto, sem verbo)",
  "discipline": "disciplina médica se identificável ou null",
  "days_until_exam": número ou null,
  "confidence": "alta | moderada | baixa",
  "immediate_response": "1-2 frases do preceptor confirmando o que entendeu e o próximo passo. Português BR. Tom acolhedor.",
  "suggests_full_review": true/false
}

Regras:
- Se detectar prova/simulado com prazo, extraia days_until_exam.
- Se for uma questão colada (com alternativas A/B/C/D), intent = question_analysis.
- Se for só um tema ("Ciclo de Krebs"), intent = review e sugere Revisão Completa.
- suggests_full_review = true quando fizer sentido oferecer a Revisão Completa (temas amplos).
- Nunca invente disciplina — se não tiver certeza, deixe null."""


async def _llm_interpret(text: str) -> dict:
    """Fallback quando regex não detecta intent claro."""
    try:
        result = await smart_chat(
            system=_INTERPRET_SYSTEM,
            user_msg=f"Mensagem do aluno: {text}",
            tier="fast",
            temperature=0.2,
            max_tokens=400,
        )
    except AIRouterError:
        return {"intent": "unknown", "mission": "conversar",
                "topic": text[:80], "immediate_response": "Recebi sua mensagem.",
                "suggests_full_review": False, "confidence": "baixa"}

    raw = result["text"]
    # extrai JSON
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {"intent": "unknown", "mission": "conversar",
                "topic": text[:80], "immediate_response": raw[:200],
                "suggests_full_review": False, "confidence": "baixa"}
    try:
        parsed = json.loads(match.group(0))
    except Exception:
        parsed = {"intent": "unknown"}
    parsed.setdefault("mission", "conversar")
    parsed.setdefault("topic", text[:80])
    parsed.setdefault("confidence", "moderada")
    parsed.setdefault("suggests_full_review", parsed.get("intent") in
                      ("review", "explanation", "quick_review"))
    parsed.setdefault("immediate_response", "Entendi. Vamos começar.")
    parsed["_llm"] = {"provider": result["provider"],
                      "model": result["model"], "latency_ms": result["latency_ms"]}
    return parsed


# ─── Mapping intent → deep-link + label ─────────────────────────────

_MISSION_LABELS = {
    "resolver_duvida": ("Resolver dúvida", "❓"),
    "treinar":        ("Treinar conhecimento", "🎯"),
    "revisar":        ("Revisar rapidamente", "⚡"),
    "memorizar":      ("Memorizar", "🧠"),
    "planejar":       ("Planejar estudos", "📅"),
    "conversar":      ("Conversar com o Preceptor", "💬"),
}

_INTENT_ACTIONS = {
    "study_plan": {
        "primary_action": "Montar plano de estudos",
        "route": "/tutor?mode=exam_tomorrow",
        "cta_note": "Vou montar seu cronograma personalizado.",
    },
    "question_analysis": {
        "primary_action": "Gerar Devolutiva Inteligente",
        "route": "/tutor/devolutiva",
        "cta_note": "Você cola a questão, eu monto a devolutiva completa.",
    },
    "quiz_generation": {
        "primary_action": "Gerar simulado",
        "route": "/tutor?mode=diagnostic",
        "cta_note": "Vou preparar questões inéditas sobre o tema.",
    },
    "flashcards": {
        "primary_action": "Criar flashcards",
        "route": "/tutor?mode=quick_review",
        "cta_note": "Flashcards focados nos pontos-chave.",
    },
    "summary": {
        "primary_action": "Ver resumo",
        "route": "/tutor?mode=quick_review",
        "cta_note": "Resumo direto e memorizável.",
    },
    "mind_map": {
        "primary_action": "Ver mapa mental",
        "route": "/tutor?mode=quick_review",
        "cta_note": "Vou desenhar o mapa mental do tema.",
    },
    "flowchart": {
        "primary_action": "Ver fluxograma",
        "route": "/tutor?mode=quick_review",
        "cta_note": "Fluxograma da conduta clínica.",
    },
    "quick_review": {
        "primary_action": "Iniciar revisão rápida",
        "route": "/tutor?mode=quick_review",
        "cta_note": "Vou focar no essencial.",
    },
    "review": {
        "primary_action": "Iniciar revisão",
        "route": "/tutor?mode=quick_review",
        "cta_note": "Vamos revisar o tema juntos.",
    },
    "explanation": {
        "primary_action": "Explicar tema",
        "route": "/tutor?mode=quick_review",
        "cta_note": "Explicação passo a passo.",
    },
    "clinical_case": {
        "primary_action": "Ver caso clínico",
        "route": "/tutor?mode=clinical_case",
        "cta_note": "Vinheta clínica com decisão e feedback.",
    },
    "greeting": {
        "primary_action": "Ver como posso ajudar",
        "route": "/tutor",
        "cta_note": "Estou aqui. Me diga o que você quer aprender.",
    },
    "unknown": {
        "primary_action": "Explorar opções",
        "route": "/tutor",
        "cta_note": "Vou te mostrar o que posso fazer.",
    },
}

# Intents que oferecem "Revisão Completa"
_REVIEW_COMPATIBLE_INTENTS = {
    "review", "quick_review", "explanation", "mind_map",
    "flowchart", "summary", "flashcards",
}


# ─── Endpoint ────────────────────────────────────────────────────────

class InterpretIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000,
                      description="Texto digitado, colado, transcrito ou extraído")
    source: str = Field("typed", description="typed | paste | voice | file | camera")
    file_name: Optional[str] = None
    file_type: Optional[str] = None  # pdf, image, audio


@router.post("/interpret")
async def interpret(body: InterpretIn, user: dict = Depends(require_user)) -> dict:
    """Interpreta a entrada universal e devolve missão + próximo passo."""
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Texto vazio")

    # 1. Tenta regex (rápido, 0 tokens)
    regex_hit = _regex_intent(text)

    # 2. LLM só quando regex não detectou algo forte
    if regex_hit and regex_hit["priority"] >= 90:
        # Extrai tópico de forma leve (primeiras palavras após o intent)
        topic = _extract_topic_light(text, regex_hit["intent"])
        interpretation = {
            "intent": regex_hit["intent"],
            "mission": regex_hit["mission"],
            "topic": topic,
            "confidence": "alta",
            "immediate_response": _canned_response(regex_hit["intent"], topic),
            "suggests_full_review": regex_hit["intent"] in _REVIEW_COMPATIBLE_INTENTS,
            "_llm": None,
            "_via": "regex",
        }
        # days_until_exam captura numérica direta
        m = re.search(r"(\d+)\s*(?:dia|semana|mês)", text.lower())
        if m and regex_hit["intent"] == "study_plan":
            n = int(m.group(1))
            unit = re.search(r"\d+\s*(dia|semana|mês)", text.lower())
            if unit:
                mult = {"dia": 1, "semana": 7, "mês": 30}[unit.group(1)]
                interpretation["days_until_exam"] = n * mult
    else:
        interpretation = await _llm_interpret(text)
        interpretation["_via"] = "llm"

    # 3. Anexa a ação recomendada
    intent = interpretation.get("intent", "unknown")
    action = _INTENT_ACTIONS.get(intent, _INTENT_ACTIONS["unknown"])
    mission_key = interpretation.get("mission", "conversar")
    mission_label, mission_icon = _MISSION_LABELS.get(
        mission_key, _MISSION_LABELS["conversar"]
    )

    # 4. Persiste interpretação (métricas + histórico)
    doc = {
        "user_id": user["user_id"],
        "input_text": text[:2000],
        "source": body.source,
        "file_name": body.file_name,
        "file_type": body.file_type,
        "interpretation": interpretation,
        "created_at": _iso(_now()),
    }
    try:
        await db.preceptor_interpretations.insert_one(dict(doc))
    except Exception:
        pass  # non-fatal

    return {
        "interpretation": interpretation,
        "mission": {
            "key": mission_key,
            "label": mission_label,
            "icon": mission_icon,
        },
        "recommended_action": {
            "label": action["primary_action"],
            "route": action["route"],
            "note": action["cta_note"],
            "params": _build_params(intent, interpretation, text),
        },
        "offer_full_review": interpretation.get("suggests_full_review", False),
    }


def _extract_topic_light(text: str, intent: str) -> str:
    """Extrai o tema principal com heurística leve."""
    t = text.strip()
    # Remove verbos comuns de início
    t = re.sub(r"^(revisar|explique|explica|resumo|resuma|fa[çc]a\s+(um\s+)?resumo\s+(de\s+|do\s+|da\s+)?|fa[çc]a\s+flashcards?\s+(de\s+|do\s+|da\s+)?|transforme\s+em\s+flashcards?\s+(de\s+|do\s+|da\s+)?|gere?\s+quest[õo]es\s+sobre\s+|crie\s+um\s+simulado\s+sobre\s+|quero\s+revisar\s+|preciso\s+revisar\s+|preciso\s+entender\s+|me\s+ensine\s+|me\s+ajude\s+com\s+|mapa\s+mental\s+(de\s+|do\s+|da\s+)?|fluxograma\s+(de\s+|do\s+|da\s+)?)\s*", "", t, flags=re.I)
    # Remove sufixo "em X dias" para intent study_plan
    if intent == "study_plan":
        t = re.sub(r"\s+em\s+\d+\s+(dias?|semanas?|meses|m[êe]s)$", "", t, flags=re.I)
        t = re.sub(r"^tenho\s+prova\s+(de\s+|sobre\s+)?", "", t, flags=re.I)
    return t.strip()[:120] or text.strip()[:120]


def _canned_response(intent: str, topic: str) -> str:
    """Resposta imediata quando regex detecta intent forte."""
    responses = {
        "study_plan": f"Entendi — vamos organizar seu cronograma até a prova. Foco em {topic or 'seus temas prioritários'}.",
        "question_analysis": "Cole a questão que eu monto a devolutiva completa: gabarito, raciocínio clínico, pérola e evidências.",
        "quiz_generation": f"Vou gerar questões sobre {topic or 'o tema'} — inéditas e com feedback.",
        "flashcards": f"Perfeito. Vou transformar {topic or 'esse conteúdo'} em flashcards para você fixar.",
        "summary": f"Resumindo {topic or 'o conteúdo'} em pontos memorizáveis.",
        "mind_map": f"Vou desenhar o mapa mental de {topic or 'o tema'}.",
        "flowchart": f"Vou montar o fluxograma da conduta de {topic or 'o tema'}.",
        "quick_review": f"Revisão rápida de {topic or 'o tema'} — o essencial primeiro.",
        "review": f"Vamos revisar {topic or 'o tema'} juntos.",
        "explanation": f"Vou explicar {topic or 'isso'} passo a passo.",
        "clinical_case": f"Preparando um caso clínico sobre {topic or 'o tema'}.",
    }
    return responses.get(intent, "Vamos lá — me dê um instante.")


def _build_params(intent: str, interp: dict, raw_text: str) -> dict:
    """Parâmetros para pré-preencher o módulo destino."""
    topic = interp.get("topic") or ""
    discipline = interp.get("discipline")
    days = interp.get("days_until_exam")
    if intent == "study_plan":
        return {"discipline": discipline or topic, "days_until_exam": days,
                "topics": [topic] if topic else []}
    if intent == "question_analysis":
        # Frontend usa o próprio texto como enunciado inicial
        return {"prefill_stem": raw_text[:1200]}
    if intent in {"quiz_generation", "clinical_case"}:
        return {"discipline": discipline or topic, "topic": topic}
    return {"discipline": discipline, "topic": topic}


# ─── Revisão Completa (orquestra múltiplas missões) ──────────────────

class FullReviewIn(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200)
    discipline: Optional[str] = None
    mode: str = Field("premium_review", pattern="^(premium_review|memorize|focused)$")
    focus: Optional[str] = None
    curriculum: str = Field("faminas_bh", pattern="^(faminas_bh|fcmmg)$")
    period: Optional[int] = Field(default=None, ge=1, le=12)
    curriculum_module: Optional[str] = Field(default=None, max_length=160)


def _parse_full_review(text: str) -> dict:
    """Aceita JSON puro, cercado por markdown ou strings de mapa com backticks."""
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.I)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    candidate = cleaned[start:end + 1] if start >= 0 and end > start else cleaned
    candidate = re.sub(
        r"`([^`]*)`",
        lambda match: json.dumps(match.group(1), ensure_ascii=False),
        candidate,
        flags=re.DOTALL,
    )
    return json.loads(candidate)


@router.post("/full-review")
async def full_review(body: FullReviewIn,
                      user: dict = Depends(require_user)) -> dict:
    """Revisão Completa — o diferencial do MedFlow.

    Gera em paralelo/sequência:
      1. Explicação detalhada
      2. Resumo inteligente
      3. Mapa mental
      4. Pontos mais cobrados em provas
      5. Flashcards
      6. Questões inéditas
      7. Caso clínico
      8. Erros frequentes

    Todos via smart_chat (tier fast — Groq preferido).
    """
    prompt = f"""Gere uma REVISÃO COMPLETA CONCISA do tema para um estudante de Medicina brasileiro.
Tema: {body.topic}
Disciplina: {body.discipline or 'inferida'}

Devolva SOMENTE JSON válido, sem texto fora. Seja DIRETO e OBJETIVO em cada campo (evite frases longas). Formato:
{{
  "topic": "{body.topic}",
  "discipline": "disciplina médica",
  "detailed_explanation": {{
    "paragraphs": ["parágrafo curto 1", "parágrafo curto 2", "parágrafo curto 3"]
  }},
  "smart_summary": {{
    "one_line": "resumo em 1 linha memorável",
    "bullets": ["ponto 1", "ponto 2", "ponto 3", "ponto 4"]
  }},
  "mind_map": "mapa mental curto em markdown (- e indentação, máx 12 linhas)",
  "high_yield_points": ["ponto 1", "ponto 2", "ponto 3", "ponto 4"],
  "flashcards": [
    {{"front": "pergunta 1", "back": "resposta curta 1"}},
    {{"front": "pergunta 2", "back": "resposta curta 2"}},
    {{"front": "pergunta 3", "back": "resposta curta 3"}},
    {{"front": "pergunta 4", "back": "resposta curta 4"}}
  ],
  "practice_questions": [
    {{"stem": "enunciado curto", "options": ["A) ...","B) ...","C) ...","D) ..."], "answer": "A", "explanation": "1 frase"}},
    {{"stem": "enunciado curto", "options": ["A) ...","B) ...","C) ...","D) ..."], "answer": "B", "explanation": "1 frase"}}
  ],
  "clinical_case": {{"vignette": "caso curto (3-4 linhas)", "question": "qual conduta?", "answer": "resposta curta com justificativa"}},
  "common_mistakes": ["erro 1", "erro 2", "erro 3"],
  "spaced_review_days": [1, 3, 7, 21]
}}

Regras: português BR, sem inventar diretrizes, foco em raciocínio clínico. Cada string curta (máx 200 caracteres por parágrafo). Use apenas JSON válido, aspas duplas e quebras de linha escapadas como \n. Não use markdown nem backticks."""

    discipline = body.discipline or "Medicina"
    plan = user.get("subscription_plan", "free")
    curriculum_context = route_curriculum(
        topic=body.topic,
        curriculum=body.curriculum,
        period=body.period,
        module=body.curriculum_module,
    )
    from ai_quota import consume_preceptor_review, release_preceptor_review

    if body.mode == "memorize":
        prompt = memorization_prompt(body.topic, discipline)
        delivery_mode = "memorization"
        max_tokens = 2400
    elif body.mode == "focused":
        prompt = focused_prompt(body.topic, discipline, body.focus or "explanation")
        delivery_mode = "focused"
        max_tokens = 2600
    else:
        usage = await consume_preceptor_review(user["user_id"], plan)
        delivery_mode = usage["delivery_mode"]
        prompt = premium_review_prompt(
            body.topic,
            discipline,
            compact=delivery_mode == "smart_compact",
        )
        max_tokens = 5200 if delivery_mode == "premium_review" else 2400
    from json_utils import repair_and_parse
    parsed = None
    result = None
    # MemORIZAR/focado aceitam 1 tentativa extra com prompt reforçado quando o
    # provedor devolve JSON malformado (prosa) — evita 502 por resposta de texto.
    extra_attempts = 1 if body.mode in ("memorize", "focused") else 0
    for attempt in range(2 + extra_attempts):  # parse normal + retries controlados
        try:
            result = await smart_chat(
                system=f"{PRECEPTOR_SYSTEM}\n\n{curriculum_context['instruction']}",
                user_msg=prompt,
                tier="structured",
                temperature=0.2,
                max_tokens=max_tokens,
                prefer="emergent",  # FASE 2: Gemini Flash primeiro, Claude fallback
                response_format={"type": "json_object"},
            )
        except AIRouterError:
            if body.mode == "premium_review":
                await release_preceptor_review(user["user_id"])
            raise HTTPException(status_code=502,
                                detail="O Preceptor está indisponível. Tente em instantes.")
        candidate = repair_and_parse(result["text"])
        if isinstance(candidate, dict) and candidate:
            parsed = candidate
            break
        logger.warning("full_review: JSON malformado (tentativa %d/%d)",
                       attempt + 1, 2 + extra_attempts)
        if attempt == 1 and extra_attempts:
            # Terceira tentativa com instrução explícita contra prosa.
            prompt = (
                prompt + "\nATENÇÃO: as tentativas anteriores NÃO vieram como "
                "JSON puro (havia texto antes/depois). Responda APENAS o "
                "objeto JSON, sem markdown, sem backticks, sem texto extra."
            )
    if not parsed:
        if body.mode == "premium_review":
            await release_preceptor_review(user["user_id"])
        raise HTTPException(status_code=502, detail="JSON malformado. Tente novamente.")

    # Correção: deduplicar flashcards e completar mínimo SEM inventar ciência.
    content_flashcards = (parsed or {}).get("flashcards") or []
    if isinstance(content_flashcards, list):
        parsed["flashcards"] = dedupe_and_complete(content_flashcards)

    # Módulos obrigatórios vazios: o provedor devolveu JSON válido mas sem
    # o conteúdo essencial (ex.: flashcards=[]). Refaz UMA geração com aviso
    # reforçado no prompt — mais barato que devolver resposta incompleta.
    if (parsed
            and body.mode in ("memorize", "focused")
            and not (parsed.get("flashcards") or [])):
        logger.warning("full_review: módulos obrigatórios vazios (mode=%s), "
                       "refazendo 1 geração reforçada", body.mode)
        reinforce = (
            "\nATENÇÃO: na tentativa anterior o JSON veio SEM flashcards "
            "(lista vazia). Isso é INACEITÁVEL: a seção `flashcards` DEVE "
            "conter de 8 a 12 itens com chaves front/back preenchidas. "
            "Nunca devolva flashcards vazio."
        )
        try:
            result2 = await smart_chat(
                system=f"{PRECEPTOR_SYSTEM}\n\n{curriculum_context['instruction']}",
                user_msg=prompt + reinforce,
                tier="structured",
                temperature=0.2,
                max_tokens=max_tokens,
                prefer="emergent",
                response_format={"type": "json_object"},
            )
            candidate2 = repair_and_parse(result2["text"])
            if (isinstance(candidate2, dict) and candidate2
                    and candidate2.get("flashcards")):
                parsed = candidate2
                result = result2
        except AIRouterError:
            logger.warning("full_review: retry reforçado falhou, "
                           "mantendo resultado original")

    # Ainda sem flashcards após dedup + retry: derivar do conteúdo já
    # entregue pelo provedor (nunca inventar ciência nova).
    if (parsed and body.mode in ("memorize", "focused")
            and not (parsed.get("flashcards") or [])):
        logger.warning("full_review: gerando cards derivados do conteúdo "
                       "(fallback sem invenção)")
        derived = synthesize_from_content(parsed)
        if derived:
            parsed["flashcards"] = derived

    import uuid
    review_id = f"fr_{uuid.uuid4().hex[:12]}"
    doc = {
        "id": review_id,
        "user_id": user["user_id"],
        "topic": body.topic,
        "discipline": body.discipline,
        "content": parsed,
        "provider": result["provider"],
        "model": result["model"],
        "latency_ms": result["latency_ms"],
        "delivery_mode": delivery_mode,
        "subscription_plan": plan,
        "curriculum_context": {key: value for key, value in curriculum_context.items() if key != "instruction"},
        "created_at": _iso(_now()),
    }
    await db.full_reviews.insert_one(dict(doc))

    return {
        "id": review_id,
        "review": parsed,
        "provider": result["provider"],
        "latency_ms": result["latency_ms"],
        "delivery_mode": delivery_mode,
        "subscription_plan": plan,
        "curriculum_context": {key: value for key, value in curriculum_context.items() if key != "instruction"},
    }


@router.post("/full-review/stream")
async def full_review_stream(body: FullReviewIn, user: dict = Depends(require_user)):
    """SSE keep-alive da Revisão Completa — mesma geração/validação, sem estourar
    o timeout ~60s do ingress (gerações de 45–80s)."""
    from sse_utils import sse_response
    return sse_response(full_review(body, user))


@router.get("/full-review/{review_id}")
async def get_full_review(review_id: str,
                          user: dict = Depends(require_user)) -> dict:
    doc = await db.full_reviews.find_one(
        {"id": review_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Revisão não encontrada")
    return {"review": doc}
