"""Hugging Face — resumos, classificação, flashcards e NLP.

Uso no MedFlow:
- Resumo de artigos e materiais de estudo (facebook/bart-large-cnn)
- Análise de sentimento (para detectar estado "Crítico" do aluno)
- NER médico (Clinical-AI-Apollo/Medical-NER, dslim/bert-base-NER)
- Classificação zero-shot (facebook/bart-large-mnli)
- Tradução PT<->EN de artigos internacionais (Helsinki-NLP/opus-mt-*)

Como obter o token: https://huggingface.co/settings/tokens (gratuito)
Env var: HUGGINGFACE_API_KEY
Docs: https://huggingface.co/docs/api-inference/index
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

_BASE_URL = "https://router.huggingface.co/hf-inference/models"


def is_configured() -> bool:
    return bool(os.environ.get("HUGGINGFACE_API_KEY"))


def _headers() -> dict:
    key = os.environ.get("HUGGINGFACE_API_KEY")
    if not key:
        raise RuntimeError("HUGGINGFACE_API_KEY não configurada")
    return {"Authorization": f"Bearer {key}"}


async def infer(model: str, payload: dict, timeout: float = 60.0) -> Any:
    """Chama a Inference API de um modelo específico do HF."""
    url = f"{_BASE_URL}/{model}"
    async with httpx.AsyncClient(timeout=timeout) as http:
        r = await http.post(url, json=payload, headers=_headers())
        r.raise_for_status()
        return r.json()


async def summarize(text: str, model: str = "facebook/bart-large-cnn",
                    max_length: int = 180, min_length: int = 40) -> str:
    """Resumo abstrativo. Para PT use `csebuetnlp/mT5_multilingual_XLSum`."""
    out = await infer(model, {
        "inputs": text,
        "parameters": {"max_length": max_length, "min_length": min_length},
    })
    if isinstance(out, list) and out and "summary_text" in out[0]:
        return out[0]["summary_text"]
    return ""


async def zero_shot_classify(text: str, candidate_labels: list[str],
                             model: str = "facebook/bart-large-mnli") -> dict:
    """Classifica um texto entre labels arbitrárias (útil pra categorizar materiais)."""
    return await infer(model, {
        "inputs": text,
        "parameters": {"candidate_labels": candidate_labels},
    })


async def sentiment(text: str,
                    model: str = "cardiffnlp/twitter-xlm-roberta-base-sentiment") -> Any:
    """Análise de sentimento (multilíngue, funciona em PT)."""
    return await infer(model, {"inputs": text})


async def medical_ner(text: str,
                      model: str = "Clinical-AI-Apollo/Medical-NER") -> Any:
    """NER médico — extrai doenças, medicamentos, sintomas."""
    return await infer(model, {"inputs": text})
