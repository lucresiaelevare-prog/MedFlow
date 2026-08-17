"""Preceptor Orchestrator — arquitetura de baixo consumo de tokens.

Responsabilidades:
  1. Classificar intent da pergunta (simples vs complexo) sem chamar LLM
  2. Rotear pro tier certo (fast/structured) via ai_router
  3. L3 cache — perguntas frequentes por (review_id, question_hash)
  4. Memória progressiva — após 5 turnos, sumariza e descarta antigos
  5. Contexto adaptativo — turn 1 = full, turnos 2-5 = compact,
     turno 6+ = summary + last turn only
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from ai_router import AIRouterError, smart_chat
from core import db, logger

# ─── Intent classifier (regex, sem LLM) ─────────────────────────────

_SIMPLE_INTENTS = [
    (r"\bexplique.{0,20}(simples|fácil|resumido)", "simple_explain"),
    (r"\b(resumo|resuma).{0,20}(30\s*segundos|curto)?", "summary"),
    (r"\bmapa\s+mental", "mind_map"),
    (r"\bfluxograma", "flowchart"),
    (r"\bmacete", "mnemonic"),
    (r"\bgere?\s+uma\s+quest[ãa]o.{0,30}(mais\s+f[áa]cil|f[áa]cil|fixa[çc][ãa]o)", "similar_easy"),
    (r"\bgere?\s+uma\s+quest[ãa]o.{0,30}(dificuldade\s+maior|mais\s+dif[íi]cil|dif[íi]cil)", "similar_hard"),
    (r"\bgere?\s+uma\s+quest[ãa]o.{0,30}(semelhante|parecida|similar)", "similar_question"),
    (r"\bfa[çc]a?\s+3.{0,20}perguntas", "quiz_me"),
    (r"\bquais\s+palavras[- ]chave", "keywords"),
    (r"\bquais\s+medicamentos", "meds_list"),
]

_COMPLEX_INTENTS = [
    (r"\bdiferenciar|diferen[çc]a|compar[ae]", "differential"),
    (r"\bdiretriz(es)?\s+(mais\s+)?atuais?", "guidelines"),
    (r"\bcontrov[eé]rsia", "controversy"),
    (r"\bcondut[ao]", "management"),
    (r"\bpaciente\s+apresentasse", "clinical_variation"),
    (r"\bcaso\s+cl[íi]nico\s+semelhante", "case_scenario"),
    (r"\bcomo\s+esse\s+caso\s+acontece", "real_world_case"),
    (r"\bpor\s+que\s+minha\s+resposta", "why_wrong"),
]


def classify_intent(message: str) -> dict:
    """Classificação lightweight por regex. Retorna {tier, category, label}."""
    m = (message or "").lower().strip()
    for pat, label in _SIMPLE_INTENTS:
        if re.search(pat, m):
            return {"tier": "fast", "category": "simple", "label": label}
    for pat, label in _COMPLEX_INTENTS:
        if re.search(pat, m):
            return {"tier": "structured", "category": "complex", "label": label}
    # Default: msg curta e sem sinal → fast; msg longa → structured
    tier = "structured" if len(m) > 180 else "fast"
    return {"tier": tier, "category": "default", "label": "general"}


# ─── L3 Cache — perguntas frequentes ────────────────────────────────

_L3_TTL_DAYS = 60


def _normalize_question(q: str) -> str:
    q = (q or "").lower().strip()
    q = re.sub(r"[^\w\sáéíóúâêôãõç]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q[:220]


def _l3_key(qhash: str, question_norm: str) -> str:
    blob = f"{qhash}::{question_norm}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


async def l3_get(qhash: str, question: str) -> Optional[dict]:
    """Retorna {reply, provider, model} se houver cache válido, senão None."""
    norm = _normalize_question(question)
    if len(norm) < 8:
        return None
    doc = await db.preceptor_qa_cache.find_one({"key": _l3_key(qhash, norm)}, {"_id": 0})
    if not doc:
        return None
    try:
        cached_at = datetime.fromisoformat(doc["cached_at"].replace("Z", "+00:00"))
    except Exception:
        return None
    if datetime.now(timezone.utc) - cached_at > timedelta(days=_L3_TTL_DAYS):
        return None
    return {
        "reply": doc.get("reply"),
        "provider": doc.get("provider"),
        "model": doc.get("model"),
        "cached": True,
    }


async def l3_put(qhash: str, question: str, reply: str,
                 provider: str, model: str) -> None:
    norm = _normalize_question(question)
    if len(norm) < 8:
        return
    key = _l3_key(qhash, norm)
    await db.preceptor_qa_cache.update_one(
        {"key": key},
        {"$set": {
            "key": key, "qhash": qhash, "question_norm": norm,
            "reply": reply, "provider": provider, "model": model,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }, "$inc": {"hit_count": 0}},  # inicia hit_count
        upsert=True,
    )


async def l3_record_hit(qhash: str, question: str) -> None:
    norm = _normalize_question(question)
    await db.preceptor_qa_cache.update_one(
        {"key": _l3_key(qhash, norm)},
        {"$inc": {"hit_count": 1}},
    )


# ─── Contexto adaptativo ────────────────────────────────────────────

def build_full_context(review: dict) -> str:
    """Contexto completo — usado apenas na 1ª interação."""
    llm = review.get("llm_output") or {}
    opts = review.get("options") or []
    letters = [chr(65 + i) for i in range(len(opts))]
    opts_txt = "\n".join(f"  {letters[i]}) {o}" for i, o in enumerate(opts))
    alts = llm.get("alternatives_analysis") or []
    alts_txt = "\n".join(
        f"  {a.get('letter')}) {'CORRETA' if a.get('is_correct') else 'ERRADA'} — {a.get('explanation', '')}"
        for a in alts
    )
    reasoning = "\n".join(llm.get("clinical_reasoning", {}).get("paragraphs") or [])
    pearl = (llm.get("clinical_pearl") or {}).get("content") or "—"
    mistake = (llm.get("common_mistake") or {}).get("content") or "—"

    evidence = review.get("evidence") or {}
    refs = []
    for it in (evidence.get("pubmed") or [])[:2]:
        refs.append(f"  · PubMed: {it.get('title')} ({it.get('journal')}, {it.get('pubdate')})")
    for it in (evidence.get("openalex") or [])[:2]:
        refs.append(f"  · OpenAlex: {it.get('title')} ({it.get('venue')}, {it.get('year')})")
    refs_txt = "\n".join(refs) if refs else "  (sem referências)"

    is_correct = review.get("is_correct")
    result_line = ("ACERTOU" if is_correct is True
                   else "ERROU" if is_correct is False
                   else "não marcou resposta")

    return f"""━━━ CONTEXTO DA QUESTÃO ━━━
Disciplina: {review.get('discipline') or '—'}
Tema: {review.get('topic') or '—'}

ENUNCIADO:
{review.get('question_stem', '')}

ALTERNATIVAS:
{opts_txt}

Gabarito: {review.get('correct_letter')} · Aluno respondeu: {review.get('student_letter') or '—'} ({result_line})

━━━ DEVOLUTIVA (aluno já leu) ━━━
RESUMO: {(llm.get('objective') or {}).get('summary', '—')}

RACIOCÍNIO:
{reasoning}

ANÁLISE DAS ALTERNATIVAS:
{alts_txt}

PÉROLA: {pearl}
ERRO COMUM: {mistake}

REFERÊNCIAS:
{refs_txt}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

O aluno já leu isso. Traga ângulos NOVOS, comparações, casos, macetes ou aprofundamentos — nunca repita a devolutiva."""


def build_compact_context(review: dict) -> str:
    """Contexto compacto — usado nos turnos 2-5.

    Reduz drasticamente os tokens mantendo o essencial. Enunciado, alternativas
    e devolutiva completa NÃO são reenviados (o LLM já viu na 1ª interação
    da conversa, e o histórico curto preserva o fio da meada).
    """
    llm = review.get("llm_output") or {}
    is_correct = review.get("is_correct")
    result = ("acertou" if is_correct is True
              else "errou" if is_correct is False else "não marcou")
    pearl = (llm.get("clinical_pearl") or {}).get("content") or ""
    return f"""━━━ QUESTÃO EM DISCUSSÃO ━━━
Disciplina: {review.get('discipline') or '—'} · Tema: {review.get('topic') or '—'}
Gabarito: {review.get('correct_letter')} · Aluno {result} (respondeu {review.get('student_letter') or '—'})
Pérola-chave: {pearl[:200]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Continue a conversa como preceptor. Não repita a devolutiva completa — o aluno já a leu no início."""


# ─── Memória progressiva (summarization) ────────────────────────────

_MAX_FULL_TURNS = 5  # após isso, sumariza histórico antigo


async def generate_conversation_summary(conversation: list[dict]) -> Optional[str]:
    """Gera resumo curto (2-3 frases) da conversa via Groq (barato).

    Não inclui a última troca — ela permanece explícita no contexto.
    """
    if not conversation or len(conversation) < 4:
        return None
    # Ignora as 2 últimas mensagens (última troca) — mantidas no contexto
    to_summarize = conversation[:-2]
    if not to_summarize:
        return None

    lines = []
    for m in to_summarize:
        role = "Aluno" if m.get("role") == "user" else "Preceptor"
        content = str(m.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content[:400]}")
    convo_txt = "\n".join(lines)

    prompt = (
        "Resuma em 2-3 frases curtas o que já foi discutido nesta conversa "
        "entre um aluno de medicina e o preceptor. Foque em: (a) o que o aluno "
        "já entendeu, (b) o que ainda tem dúvida, (c) quais tópicos já foram "
        "cobertos. Português do Brasil. Sem preâmbulos.\n\n" + convo_txt
    )

    try:
        result = await smart_chat(
            system="Você resume conversas educacionais em 2-3 frases objetivas.",
            user_msg=prompt,
            tier="cheap",
            temperature=0.2,
            max_tokens=200,
        )
        return result["text"].strip()
    except AIRouterError as exc:
        logger.warning("summary generation failed: %s", exc)
        return None


def build_history_block(conversation: list[dict], summary: Optional[str]) -> str:
    """Formata histórico para o user_msg.

    Regra:
      turnos ≤ 5 → últimas 4 mensagens explícitas
      turnos > 5 → summary + última troca (2 msgs)
    """
    if not conversation:
        return ""
    user_msgs = [m for m in conversation if m.get("role") == "user"]
    turn_count = len(user_msgs)

    if turn_count > _MAX_FULL_TURNS and summary:
        # Só a última troca completa (2 mensagens) + summary
        recent = conversation[-2:]
        head = f"━━━ RESUMO DA CONVERSA ATÉ AGORA ━━━\n{summary}\n━━━━━━━━━━━━━━━━━━━\n"
    else:
        recent = conversation[-6:]  # 3 últimas trocas
        head = ""

    lines = []
    for m in recent:
        role = "ALUNO" if m.get("role") == "user" else "PRECEPTOR"
        content = str(m.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return head + "\n".join(lines)


# ─── System prompt do preceptor ─────────────────────────────────────

PRECEPTOR_SYSTEM = """Você é o Tutor Med Flow — preceptor clínico experiente ensinando um aluno de Medicina brasileiro.

Tom: didático, objetivo, calmo, humanizado, incentivador, natural.
Você conversa como médico veterano com residente — NUNCA como chatbot.

Regras:
1. Nunca responda só "sim/não" — sempre explique o raciocínio clínico.
2. Estimule pensamento crítico com perguntas socráticas quando fizer sentido.
3. Baseado em evidências: cite diretrizes/sociedades apenas com certeza; se controverso, diga.
4. Se houver mais de uma conduta possível, diferencie os cenários.
5. Nunca invente referências, anos ou nomes de artigos.
6. Respostas curtas por padrão (3-6 parágrafos). Longas apenas quando pedido (mapa mental, fluxograma, aprofundamento).
7. Se pedirem mapa mental ou fluxograma, use Markdown com listas hierárquicas ou ASCII simples.
8. Se pedirem nova questão, formule completa (enunciado + 4-5 alternativas + gabarito + explicação curta).
9. Português do Brasil, tom natural e humano.
10. Termine estimulando a continuar aprendendo — pergunta ou próximo passo."""


# ─── Orchestrator principal ─────────────────────────────────────────

async def orchestrate_chat(review: dict, message: str) -> dict:
    """Fluxo completo do chat com o Preceptor.

    Retorna {reply, provider, model, latency_ms, cached, intent}
    """
    qhash = review.get("qhash")
    conversation = review.get("conversation") or []
    conversation_summary = review.get("conversation_summary")

    # L3 cache — só na 1ª interação (perguntas frequentes só valem com contexto zero)
    if not conversation:
        cached = await l3_get(qhash, message)
        if cached:
            await l3_record_hit(qhash, message)
            logger.info("preceptor L3 cache HIT qhash=%s", qhash)
            return {
                "reply": cached["reply"],
                "provider": cached["provider"],
                "model": cached["model"],
                "latency_ms": 5,
                "cached": True,
                "intent": {"tier": "cache", "category": "l3", "label": "cache_hit"},
            }

    # Intent classification
    intent = classify_intent(message)

    # Contexto adaptativo
    turn_count = len([m for m in conversation if m.get("role") == "user"])
    if turn_count == 0:
        context = build_full_context(review)
    else:
        context = build_compact_context(review)

    system = f"{PRECEPTOR_SYSTEM}\n\n{context}"

    # Monta user_msg com histórico compactado
    history_block = build_history_block(conversation, conversation_summary)
    user_msg = (
        f"{history_block}\n\nALUNO (agora): {message}"
        if history_block else message
    )

    # Chama LLM roteado pelo tier
    result = await smart_chat(
        system=system,
        user_msg=user_msg,
        tier=intent["tier"],
        temperature=0.4,
        max_tokens=1200,
    )

    # L3 cache write — só na 1ª interação (guarda resposta base pra perguntas frequentes)
    if not conversation:
        try:
            await l3_put(qhash, message, result["text"],
                         result["provider"], result["model"])
        except Exception as exc:
            logger.warning("l3 put failed: %s", exc)

    return {
        "reply": result["text"],
        "provider": result["provider"],
        "model": result["model"],
        "latency_ms": result["latency_ms"],
        "cached": False,
        "intent": intent,
    }


async def maybe_update_summary(review_id: str, user_id: str,
                               conversation: list[dict]) -> Optional[str]:
    """Se o número de turnos ultrapassar 5, gera/atualiza o summary."""
    user_msgs = [m for m in conversation if m.get("role") == "user"]
    if len(user_msgs) < _MAX_FULL_TURNS + 1:
        return None

    summary = await generate_conversation_summary(conversation)
    if not summary:
        return None
    await db.smart_reviews.update_one(
        {"id": review_id, "user_id": user_id},
        {"$set": {"conversation_summary": summary,
                  "summary_updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return summary
