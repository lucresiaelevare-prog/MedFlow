"""Rotas de integração — Pilar de Evolução Acadêmica.

Endpoints:
  GET  /api/integrations/status                — status de cada API (chave configurada?)
  POST /api/integrations/openai/chat           — chat rápido via OpenAI (requer OPENAI_API_KEY)
  POST /api/integrations/groq/chat             — chat rápido via Groq (requer GROQ_API_KEY)
  POST /api/integrations/hf/summarize          — resumo de texto via HuggingFace
  POST /api/integrations/hf/classify           — classificação zero-shot via HuggingFace
  GET  /api/integrations/pubmed/search?q=...   — busca artigos no PubMed
  GET  /api/integrations/openalex/search?q=... — busca trabalhos no OpenAlex

Todos os endpoints exigem sessão válida (require_user).
"""
from __future__ import annotations

from typing import Optional

import os
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core import logger, require_user
from integrations import (
    groq_client,
    huggingface_client,
    openai_client,
    openalex_client,
    pubmed_client,
)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])
_OPENAI_RATE_LIMIT_UNTIL = 0.0


@router.get("/status")
async def status(user: dict = Depends(require_user)) -> dict:
    return {
        "openai":       {"configured": openai_client.is_configured()},
        "groq":         {"configured": groq_client.is_configured()},
        "huggingface":  {"configured": huggingface_client.is_configured()},
        "pubmed":       {"configured": True,  # funciona sem chave
                         "api_key": bool(os.environ.get("PUBMED_API_KEY"))},
        "openalex":     {"configured": True},  # funciona sem chave (polite pool com email)
    }


# ── OpenAI / Groq ────────────────────────────────────────────────────────────

class ChatIn(BaseModel):
    system: str = "Você é o Tutor IA do MedFlow. Responda em português do Brasil, direto ao ponto."
    message: str
    model: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 800


async def _groq_fallback(body: ChatIn, reason: str) -> dict:
    if not groq_client.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Tutor temporariamente indisponível. Tente novamente em instantes.",
        )
    try:
        text = await groq_client.chat(
            body.system,
            body.message,
            model="llama-3.3-70b-versatile",
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
    except Exception as groq_error:
        logger.error("Groq também indisponível: %s", str(groq_error)[:200])
        raise HTTPException(
            status_code=503,
            detail="Tutor temporariamente indisponível. Tente novamente em instantes.",
        )
    return {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "text": text,
        "fallback_from": reason,
    }


@router.post("/openai/chat")
async def openai_chat(body: ChatIn, user: dict = Depends(require_user)) -> dict:
    global _OPENAI_RATE_LIMIT_UNTIL
    from ai_quota import consume_ai_quota

    await consume_ai_quota(user["user_id"], "tutor")

    if time.monotonic() < _OPENAI_RATE_LIMIT_UNTIL:
        return await _groq_fallback(body, "openai")
    if not openai_client.is_configured():
        return await _groq_fallback(body, "openai")
    try:
        text = await openai_client.chat(
            body.system, body.message,
            model=body.model or "gpt-4o-mini",
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
    except Exception as openai_error:
        logger.warning("OpenAI indisponível; tentando Groq: %s", type(openai_error).__name__)
        if getattr(openai_error, "status_code", None) == 429:
            _OPENAI_RATE_LIMIT_UNTIL = time.monotonic() + 300
        return await _groq_fallback(body, "openai")
    return {"provider": "openai", "model": body.model or "gpt-4o-mini", "text": text}


@router.post("/groq/chat")
async def groq_chat(body: ChatIn, user: dict = Depends(require_user)) -> dict:
    if not groq_client.is_configured():
        raise HTTPException(status_code=503, detail="GROQ_API_KEY não configurada")
    try:
        text = await groq_client.chat(
            body.system, body.message,
            model=body.model or "llama-3.3-70b-versatile",
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Groq: {exc}")
    return {"provider": "groq", "model": body.model or "llama-3.3-70b-versatile", "text": text}


# ── HuggingFace ──────────────────────────────────────────────────────────────

class SummarizeIn(BaseModel):
    text: str
    model: str = "facebook/bart-large-cnn"
    max_length: int = 180
    min_length: int = 40


@router.post("/hf/summarize")
async def hf_summarize(body: SummarizeIn, user: dict = Depends(require_user)) -> dict:
    if not huggingface_client.is_configured():
        raise HTTPException(status_code=503, detail="HUGGINGFACE_API_KEY não configurada")
    try:
        summary = await huggingface_client.summarize(
            body.text, model=body.model,
            max_length=body.max_length, min_length=body.min_length,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HuggingFace: {exc}")
    return {"summary": summary, "model": body.model}


class ClassifyIn(BaseModel):
    text: str
    labels: list[str]
    model: str = "facebook/bart-large-mnli"


@router.post("/hf/classify")
async def hf_classify(body: ClassifyIn, user: dict = Depends(require_user)) -> dict:
    if not huggingface_client.is_configured():
        raise HTTPException(status_code=503, detail="HUGGINGFACE_API_KEY não configurada")
    if not body.labels:
        raise HTTPException(status_code=400, detail="Informe ao menos 1 label")
    try:
        result = await huggingface_client.zero_shot_classify(
            body.text, body.labels, model=body.model,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HuggingFace: {exc}")
    return {"result": result, "model": body.model}


# ── PubMed ───────────────────────────────────────────────────────────────────

@router.get("/pubmed/search")
async def pubmed_search(
    q: str = Query(..., min_length=2, description="Termo de busca"),
    retmax: int = Query(10, ge=1, le=50),
    user: dict = Depends(require_user),
) -> dict:
    try:
        items = await pubmed_client.search_and_summarize(q, retmax=retmax)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"PubMed: {exc}")
    return {"query": q, "count": len(items), "items": items}


# ── OpenAlex ─────────────────────────────────────────────────────────────────

@router.get("/openalex/search")
async def openalex_search(
    q: str = Query(..., min_length=2, description="Termo de busca"),
    per_page: int = Query(10, ge=1, le=50),
    filter_: Optional[str] = Query(None, alias="filter"),
    user: dict = Depends(require_user),
) -> dict:
    try:
        items = await openalex_client.search_works(q, per_page=per_page, filter_=filter_)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenAlex: {exc}")
    return {"query": q, "count": len(items), "items": items}


@router.get("/openalex/concepts")
async def openalex_concepts(
    q: str = Query(..., min_length=2),
    per_page: int = Query(5, ge=1, le=20),
    user: dict = Depends(require_user),
) -> dict:
    try:
        items = await openalex_client.concept_lookup(q, per_page=per_page)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenAlex: {exc}")
    return {"query": q, "items": items}
