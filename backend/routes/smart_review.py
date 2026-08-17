"""Devolutiva Inteligente Med Flow™ — feature-âncora do Tutor IA.

Endpoint principal: POST /api/tutor/smart-review

Recebe uma questão (enunciado + alternativas + gabarito + resposta do aluno)
e devolve uma devolutiva rica com 12 seções (raciocínio clínico, análise
de alternativas, pérola clínica, erro comum, aplicação prática, evidências,
próximos passos, feedback personalizado etc.).

Estratégia de performance:
  1. Roda LLM structured (OpenAI → Claude → Groq) para as 12 seções.
  2. Em paralelo (asyncio.gather) busca PubMed + OpenAlex baseado nos
     tópicos-chave inferidos.
  3. Cruza com o Mastery Map do aluno para personalizar seção 10.
  4. Cache por (questão_hash + resposta) em db.smart_reviews.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ai_router import AIRouterError, smart_chat
from core import _clean, _iso, _now, db, logger, require_user

router = APIRouter(prefix="/api/tutor", tags=["smart-review"])


# ─── Schemas ──────────────────────────────────────────────────────────────

class SmartReviewIn(BaseModel):
    question_stem: str = Field(..., min_length=10, description="Enunciado da questão")
    options: list[str] = Field(..., min_length=2,
                               description="Alternativas (A, B, C, D, E)")
    correct_letter: str = Field(..., min_length=1, max_length=2,
                                description="Letra da alternativa correta")
    student_letter: Optional[str] = Field(None, description="Letra escolhida pelo aluno")
    discipline: Optional[str] = None
    topic: Optional[str] = None
    time_spent_sec: Optional[int] = None


# ─── System prompt: "preceptor experiente" ────────────────────────────────

_SYSTEM_PRECEPTOR = """Você é um preceptor médico experiente do MedFlow — mentor clínico de estudantes de Medicina brasileiros.

Sua função é ENSINAR RACIOCÍNIO CLÍNICO, não apenas informar a resposta.

Tom: calmo, didático, objetivo, elegante e humano. Fale como um preceptor
de plantão que quer que o aluno pense — nunca como um chatbot genérico.

Regras absolutas:
1. NUNCA repita o enunciado da questão.
2. NUNCA escreva respostas genéricas ou vagas.
3. NUNCA invente diretrizes, sociedades, anos ou nomes de artigos.
4. Se não souber algo, diga explicitamente "não há evidência suficiente" em vez de inventar.
5. Sempre em português do Brasil.
6. Explique o "porquê" — a lógica clínica por trás da resposta.
7. Fale como um humano: use analogias, cite pistas, mostre o raciocínio.
8. Devolva SEMPRE um JSON válido, sem texto fora do JSON, seguindo estritamente o schema pedido.
"""


def _make_user_prompt(payload: SmartReviewIn) -> str:
    opts_txt = "\n".join(
        f"  {chr(65 + i)}) {opt.lstrip('ABCDEabcde) .- ')}"
        for i, opt in enumerate(payload.options)
    )
    student_line = (
        f"Aluno respondeu: {payload.student_letter.upper()}"
        if payload.student_letter else "Aluno não informou a resposta escolhida."
    )
    return f"""Contexto:
Disciplina: {payload.discipline or 'não informada'}
Tema: {payload.topic or 'não informado'}

QUESTÃO:
{payload.question_stem.strip()}

Alternativas:
{opts_txt}

Gabarito oficial: {payload.correct_letter.upper()}
{student_line}

Gere a DEVOLUTIVA INTELIGENTE MED FLOW seguindo estritamente o schema JSON abaixo.
Cada seção deve agregar conhecimento — nunca repetir o enunciado ou informação óbvia.
Se o aluno errou, seja acolhedor e didático; se acertou, aprofunde o conhecimento.

Schema (retorne SOMENTE este JSON, sem texto fora):
{{
  "objective": {{
    "correct_letter": "letra do gabarito (uma letra maiúscula)",
    "summary": "resumo em até 3 linhas explicando por que essa é a resposta"
  }},
  "clinical_reasoning": {{
    "paragraphs": [
      "parágrafo 1: quais informações do caso realmente importam",
      "parágrafo 2: quais sinais/sintomas são decisivos e por quê",
      "parágrafo 3: como diferenciar diagnósticos ou condutas semelhantes",
      "parágrafo 4 (opcional): a lógica final que fecha o raciocínio"
    ]
  }},
  "alternatives_analysis": [
    {{
      "letter": "A", "is_correct": false,
      "explanation": "por que essa alternativa está errada — mecanismo, contexto, pegadinha"
    }},
    {{
      "letter": "B", "is_correct": true,
      "explanation": "por que essa está correta — o raciocínio completo"
    }}
    /* uma entrada por alternativa, sempre com explicação clara */
  ],
  "clinical_pearl": {{
    "title": "título curto da pérola (ex.: 'Tríade de Beck')",
    "content": "dica memorável, uma frase que o aluno leva pra vida — normalmente aparece em provas ou plantão"
  }},
  "common_mistake": {{
    "title": "onde os candidatos mais erram",
    "content": "descrição da confusão frequente — pegadinha conceitual, diagnóstico confundido ou conduta equivocada"
  }},
  "real_world": {{
    "arrival": "como esse paciente chegaria no hospital (uma frase)",
    "physician_thinking": "como o médico pensaria no atendimento (uma frase)",
    "priority": "qual seria a prioridade imediata (uma frase)"
  }},
  "review_topics": [
    "tópico 1 relacionado (até 5 tópicos, ordenados por relevância)",
    "tópico 2",
    "tópico 3",
    "tópico 4",
    "tópico 5"
  ],
  "confidence": {{
    "level": "alta | moderada | baixa",
    "explanation": "por que essa confiança — ex.: 'diretriz consolidada', 'evidência conflitante', 'consenso de sociedade'"
  }},
  "reading_time_sec": 60,
  "evidence_query": "termo de busca EM INGLÊS otimizado para PubMed/OpenAlex (3-8 palavras). Ex: 'cardiac tamponade Beck triad diagnosis'",
  "guideline": {{
    "society": "sociedade OU 'não citada' (nunca inventar)",
    "year": "ano da diretriz OU null se não houver certeza",
    "note": "nome curto da diretriz ou 'não citada'"
  }}
}}"""


def _extract_json(text: str) -> dict:
    """Extrai o primeiro JSON válido do texto."""
    if not text:
        return {}
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if not candidate:
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


def _question_hash(payload: SmartReviewIn) -> str:
    """Fingerprint estável da questão pra cache cross-user."""
    normalized = {
        "stem": re.sub(r"\s+", " ", payload.question_stem.strip().lower()),
        "options": [re.sub(r"\s+", " ", o.strip().lower()) for o in payload.options],
        "correct": payload.correct_letter.upper(),
    }
    blob = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# ─── Enrichment: PubMed + OpenAlex + Mastery Map em paralelo ──────────────

async def _fetch_pubmed_safe(query: str, retmax: int = 3) -> list[dict]:
    try:
        from integrations.pubmed_client import search_and_summarize
        return await search_and_summarize(query, retmax=retmax)
    except Exception as exc:
        logger.warning("smart-review pubmed failed: %s", exc)
        return []


async def _fetch_openalex_safe(query: str, per_page: int = 3) -> list[dict]:
    try:
        from integrations.openalex_client import search_works
        return await search_works(query, per_page=per_page)
    except Exception as exc:
        logger.warning("smart-review openalex failed: %s", exc)
        return []


async def _fetch_mastery_summary(user_id: str, discipline: Optional[str]) -> dict:
    """Retorna um resumo cru do Mastery Map focado na disciplina da questão."""
    try:
        import learning_memory as lm
        flat = await lm.student_mastery(user_id)
        topics = flat.get("topics", []) or []
        if discipline:
            topics = [t for t in topics
                      if (t.get("discipline") or "").lower() == discipline.lower()]
        # Agregado
        total_answered = sum(t.get("answered", 0) for t in topics)
        total_correct = sum(t.get("correct", 0) for t in topics)
        # Fraquezas
        weakest = sorted(
            [t for t in topics if t.get("mastery_score") is not None],
            key=lambda t: t["mastery_score"],
        )[:3]
        return {
            "discipline": discipline,
            "total_answered": total_answered,
            "total_correct": total_correct,
            "accuracy": (total_correct / total_answered) if total_answered else None,
            "weakest_topics": [
                {"topic": t.get("topic"), "score": t.get("mastery_score")}
                for t in weakest
            ],
            "has_data": total_answered >= 5,
        }
    except Exception as exc:
        logger.warning("smart-review mastery failed: %s", exc)
        return {"has_data": False}


def _build_personalized_feedback(mastery: dict, is_correct: Optional[bool]) -> dict:
    """Cruza mastery + resultado para gerar mensagem personalizada real (não inventa)."""
    if not mastery.get("has_data"):
        return {
            "message": "Continue respondendo questões para que o Tutor identifique seus padrões de aprendizagem.",
            "based_on": "sem_dados",
        }

    acc = mastery.get("accuracy")
    weak = mastery.get("weakest_topics") or []
    disc = mastery.get("discipline") or "essa disciplina"

    parts = []
    if acc is not None:
        pct = int(acc * 100)
        if pct >= 75:
            parts.append(f"Seu desempenho em {disc} está sólido ({pct}% de acertos).")
        elif pct >= 50:
            parts.append(f"Você está em evolução em {disc} ({pct}% de acertos).")
        else:
            parts.append(f"{disc} ainda precisa de mais treino ({pct}% de acertos).")

    if weak:
        w = weak[0]
        parts.append(f"Ponto de atenção: '{w['topic']}' está entre seus tópicos mais frágeis.")

    if is_correct is True and acc and acc >= 0.6:
        parts.append("Você acertou consistentemente — vamos para uma questão mais difícil na próxima.")
    elif is_correct is False:
        parts.append("O erro de hoje entrou no seu mapa — vou reforçar esse tópico nas próximas sessões.")

    return {
        "message": " ".join(parts),
        "based_on": {"answered": mastery.get("total_answered"),
                     "accuracy": acc, "weak_count": len(weak)},
    }


# ─── Endpoints ────────────────────────────────────────────────────────────

@router.post("/smart-review")
async def smart_review(payload: SmartReviewIn,
                       user: dict = Depends(require_user)) -> dict:
    """Devolutiva Inteligente Med Flow™.

    Estratégia:
      1. Verifica cache por (question_hash + student_letter).
      2. Se cache miss: chama LLM structured para as 12 seções.
      3. Em paralelo: busca PubMed + OpenAlex + Mastery Map.
      4. Persiste e devolve.
    """
    qhash = _question_hash(payload)
    student_letter = (payload.student_letter or "").upper() or None
    correct_letter = payload.correct_letter.upper()
    is_correct = (student_letter == correct_letter) if student_letter else None

    # 1. Cache lookup (cross-user por fingerprint da questão)
    cached_llm = None
    cached_doc = await db.smart_review_cache.find_one({"qhash": qhash}, {"_id": 0})
    if cached_doc:
        cached_llm = cached_doc.get("llm_output")
        logger.info("smart-review cache HIT qhash=%s", qhash)

    # 2. LLM (se cache miss)
    if not cached_llm:
        prompt = _make_user_prompt(payload)
        try:
            llm_result = await smart_chat(
                system=_SYSTEM_PRECEPTOR,
                user_msg=prompt,
                tier="structured",
                temperature=0.3,
                max_tokens=2800,
                prefer="groq",
            )
        except AIRouterError:
            raise HTTPException(
                status_code=502,
                detail="O tutor IA está temporariamente indisponível. Tente em instantes.",
            )
        parsed = _extract_json(llm_result["text"])
        if not parsed or "objective" not in parsed:
            raise HTTPException(status_code=502,
                                detail="Resposta do tutor incompleta. Tente novamente.")
        cached_llm = {
            "output": parsed,
            "provider": llm_result["provider"],
            "model": llm_result["model"],
            "latency_ms": llm_result["latency_ms"],
        }
        await db.smart_review_cache.update_one(
            {"qhash": qhash},
            {"$set": {"qhash": qhash, "llm_output": cached_llm,
                      "cached_at": _iso(_now()),
                      "discipline": payload.discipline,
                      "topic": payload.topic}},
            upsert=True,
        )

    llm_output = cached_llm["output"]

    # 3. Enriquecimento em paralelo (PubMed + OpenAlex + Mastery)
    ev_query = llm_output.get("evidence_query") or (
        payload.topic or payload.discipline or "medical education"
    )
    pubmed_task = _fetch_pubmed_safe(ev_query, retmax=3)
    openalex_task = _fetch_openalex_safe(ev_query, per_page=3)
    mastery_task = _fetch_mastery_summary(user["user_id"], payload.discipline)

    pubmed_items, openalex_items, mastery_summary = await asyncio.gather(
        pubmed_task, openalex_task, mastery_task
    )

    personalized = _build_personalized_feedback(mastery_summary, is_correct)

    # 4. Persistência do review individual do aluno
    review_id = f"sr_{uuid.uuid4().hex[:12]}"
    doc = {
        "id": review_id,
        "user_id": user["user_id"],
        "qhash": qhash,
        "question_stem": payload.question_stem,
        "options": payload.options,
        "correct_letter": correct_letter,
        "student_letter": student_letter,
        "is_correct": is_correct,
        "discipline": payload.discipline,
        "topic": payload.topic,
        "time_spent_sec": payload.time_spent_sec,
        "llm_output": llm_output,
        "llm_provider": cached_llm.get("provider"),
        "llm_model": cached_llm.get("model"),
        "llm_latency_ms": cached_llm.get("latency_ms"),
        "evidence": {
            "query": ev_query,
            "pubmed": pubmed_items,
            "openalex": openalex_items,
        },
        "personalized": personalized,
        "created_at": _iso(_now()),
    }
    await db.smart_reviews.insert_one(dict(doc))

    return {"review": _clean(doc)}


@router.get("/smart-review")
async def list_smart_reviews(user: dict = Depends(require_user), limit: int = 30) -> dict:
    items = await db.smart_reviews.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    # Versão resumida (sem o llm_output completo pra não pesar a listagem)
    return {
        "items": [
            {
                "id": it["id"],
                "question_stem": it["question_stem"][:180],
                "discipline": it.get("discipline"),
                "topic": it.get("topic"),
                "is_correct": it.get("is_correct"),
                "correct_letter": it["correct_letter"],
                "created_at": it["created_at"],
            }
            for it in items
        ]
    }


@router.get("/smart-review/{review_id}")
async def get_smart_review(review_id: str,
                           user: dict = Depends(require_user)) -> dict:
    doc = await db.smart_reviews.find_one(
        {"id": review_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Devolutiva não encontrada")
    return {"review": doc}


@router.delete("/smart-review/{review_id}")
async def delete_smart_review(review_id: str,
                              user: dict = Depends(require_user)) -> dict:
    await db.smart_reviews.delete_one(
        {"id": review_id, "user_id": user["user_id"]}
    )
    return {"ok": True}



# ═══════════════════════════════════════════════════════════════════
# Conversar com o Preceptor IA — chat contextualizado da devolutiva
# ═══════════════════════════════════════════════════════════════════

class PreceptorChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=1200)
    # Histórico enviado pelo cliente (últimas trocas). O backend não guarda
    # sessão em memória — cada request é auto-contido.
    history: Optional[list[dict]] = None  # [{role: user|assistant, content: str}]


_PRECEPTOR_SYSTEM = """Você é o Preceptor IA do MedFlow — um preceptor médico experiente conversando com um aluno de Medicina sobre UMA questão específica que ele acabou de responder.

Sua personalidade:
- Didático, objetivo, calmo, humanizado, incentivador
- Fala como médico veterano ensinando residente — nunca como chatbot
- Sempre explica o raciocínio clínico, nunca responde só "sim/não"
- Estimula pensamento crítico com perguntas quando fizer sentido
- Baseado em evidências; cita diretrizes/sociedades apenas quando tiver certeza
- Se houver controvérsia na literatura, informa isso claramente
- Quando houver mais de uma conduta possível, diferencia cenários
- Português do Brasil, tom natural e humano

REGRAS DUROS:
1. NUNCA invente diretrizes, anos ou sociedades. Se não tiver certeza, diga "essa referência exata eu não confirmo, mas o consenso é…".
2. NUNCA repita o enunciado da questão — o aluno já leu.
3. Respostas curtas por padrão (3-6 parágrafos), mas alongue quando o aluno pedir aprofundamento, fluxograma, mapa mental etc.
4. Se o aluno pedir um mapa mental ou fluxograma, use Markdown com listas hierárquicas ou ASCII simples.
5. Se o aluno pedir uma nova questão, formule-a completa (enunciado + 4-5 alternativas + gabarito + explicação curta).
6. Termine sempre de forma que estimule o aluno a continuar aprendendo — pergunta socrática, próximo passo, ou dica prática."""


def _build_preceptor_context(review: dict) -> str:
    """Compacta a devolutiva num contexto que cabe no system prompt."""
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

    # Evidências (máx 3 refs, títulos curtos)
    evidence = review.get("evidence") or {}
    refs = []
    for it in (evidence.get("pubmed") or [])[:2]:
        refs.append(f"  · PubMed: {it.get('title')} ({it.get('journal')}, {it.get('pubdate')})")
    for it in (evidence.get("openalex") or [])[:2]:
        refs.append(f"  · OpenAlex: {it.get('title')} ({it.get('venue')}, {it.get('year')})")
    refs_txt = "\n".join(refs) if refs else "  (sem referências indexadas)"

    # Contexto pessoal
    personal = review.get("personalized") or {}
    personal_line = personal.get("message") or "sem histórico consolidado ainda"

    is_correct = review.get("is_correct")
    result_line = (
        "ACERTOU" if is_correct is True
        else "ERROU" if is_correct is False
        else "não marcou resposta"
    )

    return f"""━━━ CONTEXTO DA QUESTÃO ━━━
Disciplina: {review.get('discipline') or '—'}
Tema: {review.get('topic') or '—'}

ENUNCIADO:
{review.get('question_stem', '')}

ALTERNATIVAS:
{opts_txt}

Gabarito oficial: {review.get('correct_letter')}
Resposta do aluno: {review.get('student_letter') or '—'} ({result_line})

━━━ DEVOLUTIVA GERADA (o aluno já leu) ━━━
RESUMO: {(llm.get('objective') or {}).get('summary', '—')}

RACIOCÍNIO CLÍNICO:
{reasoning}

ANÁLISE DAS ALTERNATIVAS:
{alts_txt}

PÉROLA CLÍNICA: {pearl}
ERRO COMUM: {mistake}

REFERÊNCIAS DISPONÍVEIS:
{refs_txt}

━━━ CONTEXTO DO ALUNO ━━━
{personal_line}
━━━━━━━━━━━━━━━━━━━━━━━━━━

O aluno está agora conversando com você DEPOIS de ter lido essa devolutiva. Ele quer aprofundar, tirar dúvida ou explorar variações. Nunca repita informação exata que já está na devolutiva — traga ângulos NOVOS, comparações, casos, macetes ou aprofundamentos."""


@router.post("/smart-review/{review_id}/chat")
async def preceptor_chat(review_id: str, body: PreceptorChatIn,
                         user: dict = Depends(require_user)) -> dict:
    """Chat contextualizado com o Preceptor IA — arquitetura de baixo consumo.

    O contexto está no backend (session memory). O frontend envia apenas
    `{message}`. Após 5 turnos, o histórico é sumarizado automaticamente.

    3 níveis de cache:
      L1: cache da devolutiva (smart_review_cache) — já feito no POST /smart-review
      L2: cache de artigos científicos (integrations/evidence_cache) — automático
      L3: perguntas frequentes (preceptor_qa_cache) — para "explique simples", etc.
    """
    review = await db.smart_reviews.find_one(
        {"id": review_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not review:
        raise HTTPException(status_code=404, detail="Devolutiva não encontrada")

    from preceptor_orchestrator import orchestrate_chat, maybe_update_summary
    from ai_router import AIRouterError

    message = body.message.strip()

    try:
        result = await orchestrate_chat(review, message)
    except AIRouterError:
        raise HTTPException(status_code=502,
                            detail="O Preceptor IA está indisponível. Tente em instantes.")
    except Exception as exc:
        logger.exception("preceptor chat failed: %s", exc)
        raise HTTPException(status_code=502,
                            detail="Falha ao consultar o Preceptor. Tente novamente.")

    # Persiste a troca no review (mantém últimas 40 mensagens — teto duro)
    turn_user = {"role": "user", "content": message,
                 "created_at": _iso(_now())}
    turn_assist = {"role": "assistant", "content": result["reply"],
                   "provider": result["provider"], "model": result["model"],
                   "latency_ms": result["latency_ms"],
                   "cached": result.get("cached", False),
                   "intent": result.get("intent"),
                   "created_at": _iso(_now())}
    await db.smart_reviews.update_one(
        {"id": review_id, "user_id": user["user_id"]},
        {"$push": {"conversation": {"$each": [turn_user, turn_assist],
                                    "$slice": -40}}},
    )

    # Após 5 turnos, atualiza summary em background (não bloqueia response)
    updated = await db.smart_reviews.find_one(
        {"id": review_id, "user_id": user["user_id"]},
        {"conversation": 1, "_id": 0},
    )
    conv = (updated or {}).get("conversation") or []
    import asyncio as _asyncio
    _asyncio.create_task(maybe_update_summary(review_id, user["user_id"], conv))

    return {
        "reply": result["reply"],
        "provider": result["provider"],
        "model": result["model"],
        "latency_ms": result["latency_ms"],
        "cached": result.get("cached", False),
        "intent": result.get("intent"),
        "turn": len([m for m in conv if m.get("role") == "user"]),
    }


@router.get("/smart-review/{review_id}/conversation")
async def preceptor_conversation(review_id: str,
                                 user: dict = Depends(require_user)) -> dict:
    """Retorna a conversa completa (últimas 30 mensagens)."""
    doc = await db.smart_reviews.find_one(
        {"id": review_id, "user_id": user["user_id"]}, {"conversation": 1, "_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Devolutiva não encontrada")
    return {"messages": doc.get("conversation") or []}
