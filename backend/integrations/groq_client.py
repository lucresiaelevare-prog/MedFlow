"""Groq — inferência ultrarrápida (Llama 3.3, Mixtral, Gemma).

Uso: respostas do Tutor IA em milissegundos, mantendo o aluno no fluxo.
API compatível com OpenAI (base_url diferente).

Como obter a chave: https://console.groq.com/keys
Env var: GROQ_API_KEY
Docs: https://console.groq.com/docs/quickstart
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional


def is_configured() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def get_client():
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY não configurada")
    from groq import AsyncGroq
    return AsyncGroq(api_key=key)


async def chat(
    system: str,
    user_msg: str,
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.3,
    max_tokens: Optional[int] = 1024,
    response_format: Optional[dict] = None,
) -> str:
    """Chat rápido via Groq. Modelos: llama-3.3-70b-versatile, mixtral-8x7b, gemma2-9b-it."""
    client = get_client()
    request = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    }
    if response_format is not None:
        request["response_format"] = response_format
    resp = await asyncio.wait_for(
        client.chat.completions.create(**request),
        timeout=15,
    )
    return (resp.choices[0].message.content or "").strip()
