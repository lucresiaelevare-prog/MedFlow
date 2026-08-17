"""OpenAI — Tutor IA e geração de conteúdo.

Uso: chat completions (gpt-4o-mini/gpt-4.1) para geração de conteúdo,
resumos e respostas do Tutor IA quando o usuário optar pela OpenAI ao
invés do Claude via EMERGENT_LLM_KEY.

Como obter a chave: https://platform.openai.com/api-keys
Env var: OPENAI_API_KEY
Env var opcional: OPENAI_MODEL (sobrescreve o modelo padrão "gpt-4o-mini";
útil quando o base_url aponta para um proxy compatível que exponha
modelos diferentes).
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional


def is_configured() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def get_client():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY não configurada")
    from openai import AsyncOpenAI
    return AsyncOpenAI(api_key=key, max_retries=0)


async def chat(
    system: str,
    user_msg: str,
    model: Optional[str] = None,
    temperature: float = 0.4,
    max_tokens: Optional[int] = 1024,
    response_format: Optional[dict] = None,
) -> str:
    """Chat completions via OpenAI.

    Aceita ``response_format`` (ex.: {"type": "json_object"}) para a
    geração estruturada usada pelo Preceptor (revisão completa, JSON).
    """
    if model is None:
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client = get_client()
    kwargs: dict = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    resp = await asyncio.wait_for(
        client.chat.completions.create(**kwargs),
        timeout=120,
    )
    choices = getattr(resp, "choices", None)
    if not choices:
        raise RuntimeError("resposta sem choices (proxy indisponível)")
    content = choices[0].message.content
    if not content:
        raise RuntimeError("resposta sem conteúdo (proxy indisponível)")
    return content.strip()
