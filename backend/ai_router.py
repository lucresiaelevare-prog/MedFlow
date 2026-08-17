"""AI Router — despacho inteligente entre Groq / OpenAI / Claude (Emergent).

Objetivo: minimizar custo mantendo qualidade.

Tiers de roteamento:
  fast       → chat rápido, respostas curtas (Tutor conversacional).
               Ordem: Groq → OpenAI → Claude(Emergent).
  structured → JSON estruturado, geração longa (exam-feedback, planos).
               Ordem: OpenAI → Claude(Emergent) → Groq.
  cheap      → tarefas simples (categorização, respostas fixas).
               Ordem: Groq → OpenAI → Claude(Emergent).

Cada provider é tentado; se falhar (chave ausente, quota, timeout, 5xx)
cai automaticamente pro próximo. Registra qual provedor de fato respondeu.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Optional

from core import logger

# ── Ordens de preferência por tier ──────────────────────────────────────────
_TIER_ORDER: dict[str, list[str]] = {
    "fast":       ["groq", "openai", "emergent"],
    # FASE 2: geração longa/estruturada prioriza a cadeia Emergent, que começa
    # no modelo mais rápido (Gemini Flash) e cai para Claude como fallback de
    # qualidade — sem trocar a Universal Key.
    "structured": ["emergent", "openai", "groq"],
    "cheap":      ["groq", "openai", "emergent"],
}

# Cadeia de modelos servida pela chave universal Emergent (OpenAI/Anthropic/
# Gemini). Garante um fallback REAL mesmo quando só a chave Emergent está
# configurada: se um modelo cair (rate-limit/timeout), tenta o próximo.
# Latência: gemini-2.5-flash primeiro (muito mais rápido em JSON longo), com
# Claude como fallback de qualidade. Mantém a Universal Key (sem Groq). A
# política Preceptor v1.1 é passada via system_message e independe do modelo.
_EMERGENT_MODEL_CHAIN = [
    ("gemini", "gemini-2.5-flash"),
    ("anthropic", "claude-sonnet-4-5-20250929"),
    ("openai", "gpt-4o"),
]

# Modelos padrão por provedor
_DEFAULT_MODELS = {
    "groq":     "llama-3.3-70b-versatile",
    "openai":   os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
    "emergent": _EMERGENT_MODEL_CHAIN,
}

# Timeout por tier (segundos). Geração estruturada/longa precisa de mais tempo;
# chat rápido responde curto. Aplicado por tentativa de modelo.
_TIER_TIMEOUT: dict[str, int] = {
    "fast": 25,
    "structured": 45,
    "cheap": 20,
}


def _rate_limited(exc: Exception) -> bool:
    m = str(exc).lower()
    return any(t in m for t in ("rate", "429", "overload", "quota", "timeout"))


class AIRouterError(RuntimeError):
    """Todos os providers falharam."""


def _provider_configured(provider: str) -> bool:
    if provider == "groq":
        return bool(os.environ.get("GROQ_API_KEY"))
    if provider == "openai":
        return bool(os.environ.get("OPENAI_API_KEY"))
    if provider == "emergent":
        return bool(os.environ.get("EMERGENT_LLM_KEY"))
    return False


async def _call_groq(system: str, user_msg: str, model: str,
                     temperature: float, max_tokens: int,
                     response_format: Optional[dict] = None) -> str:
    from integrations.groq_client import chat as groq_chat
    return await groq_chat(system, user_msg, model=model,
                           temperature=temperature, max_tokens=max_tokens,
                           response_format=response_format)


async def _call_openai(system: str, user_msg: str, model: str,
                       temperature: float, max_tokens: int,
                       response_format: Optional[dict] = None) -> str:
    from integrations.openai_client import chat as openai_chat
    return await openai_chat(system, user_msg, model=model,
                             temperature=temperature, max_tokens=max_tokens,
                             response_format=response_format)


async def _call_emergent(system: str, user_msg: str,
                         models: list, temperature: float,
                         max_tokens: int, per_model_timeout: int) -> tuple:
    """Tenta a cadeia de modelos via chave universal Emergent.

    Retorna (texto, model_str). Em rate-limit/timeout, faz 1 retry com backoff
    e depois passa ao próximo modelo. Levanta a última exceção se todos caírem.
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY não configurada")

    last_exc = None
    for provider_name, model_name in models:
        for attempt in range(2):  # 1 tentativa + 1 retry
            try:
                chat = (
                    LlmChat(api_key=key, session_id=f"router-{uuid.uuid4().hex[:8]}",
                            system_message=system)
                    .with_model(provider_name, model_name)
                )
                text = await asyncio.wait_for(
                    chat.send_message(UserMessage(text=user_msg)),
                    timeout=per_model_timeout,
                )
                return text, f"emergent:{provider_name}:{model_name}"
            except (Exception, asyncio.TimeoutError) as exc:  # noqa: BLE001
                last_exc = exc
                if _rate_limited(exc) and attempt == 0:
                    await asyncio.sleep(1.5)
                    continue
                break  # erro não-transitório → próximo modelo
    raise last_exc or RuntimeError("cadeia Emergent esgotada")


async def smart_chat(
    system: str,
    user_msg: str,
    tier: str = "fast",
    temperature: float = 0.3,
    max_tokens: int = 800,
    prefer: Optional[str] = None,
    response_format: Optional[dict] = None,
) -> dict:
    """Roteia entre providers conforme o tier.

    Retorna dict com {text, provider, model, latency_ms, attempts}.
    Levanta AIRouterError se TODOS os providers configurados falharem.
    """
    order = _TIER_ORDER.get(tier, _TIER_ORDER["fast"])
    if prefer and prefer in order:
        # Coloca o preferido no início
        order = [prefer] + [p for p in order if p != prefer]

    attempts: list[dict] = []
    timeout = _TIER_TIMEOUT.get(tier, 30)
    for provider in order:
        if not _provider_configured(provider):
            attempts.append({"provider": provider, "skipped": "not_configured"})
            continue

        model = _DEFAULT_MODELS[provider]
        model_str = model if isinstance(model, str) else "emergent-chain"
        t0 = time.perf_counter()
        try:
            if provider == "groq":
                text = await asyncio.wait_for(
                    _call_groq(system, user_msg, model, temperature,
                               max_tokens, response_format),
                    timeout=timeout,
                )
            elif provider == "openai":
                text = await asyncio.wait_for(
                    _call_openai(system, user_msg, model, temperature, max_tokens,
                                 response_format),
                    timeout=timeout,
                )
            else:  # emergent — a própria cadeia já aplica timeout por modelo
                text, model_str = await _call_emergent(
                    system, user_msg, model, temperature, max_tokens,
                    per_model_timeout=timeout,
                )
            latency_ms = int((time.perf_counter() - t0) * 1000)
            attempts.append({"provider": provider, "model": model_str, "ok": True,
                             "latency_ms": latency_ms})
            logger.info("ai_router: provider=%s model=%s tier=%s latency_ms=%s",
                        provider, model_str, tier, latency_ms)
            return {
                "text": text,
                "provider": provider,
                "model": model_str,
                "latency_ms": latency_ms,
                "tier": tier,
                "attempts": attempts,
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            attempts.append({"provider": provider, "model": model_str,
                             "ok": False, "error": str(exc)[:200],
                             "latency_ms": latency_ms})
            logger.warning("ai_router: provider=%s failed (%.60s), falling back",
                           provider, str(exc))
            continue

    raise AIRouterError(f"todos os providers falharam ({tier}): {attempts}")
