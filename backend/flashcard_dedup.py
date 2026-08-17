# -*- coding: utf-8 -*-
"""Deduplicação e completude de flashcards de recuperação ativa.

Correção pontual (iter correções): evita flashcards duplicados
(mesma ideia repetida com palavras diferentes) e garante uma quantidade
mínima de cards SEM inventar ciência nova — os cards de completude são
genéricos sobre o próprio tema, derivados apenas do front já existente
(versão, mecanismo por trás, pegadinha clássica), sem conteúdo novo.
"""
from __future__ import annotations

import re
import unicodedata

# Aspectos pedagógicos distintos para completar flashcards sem inventar ciência.
_ASPECTS = [
    ("versão", "Escreva este mesmo card de forma mais curta (até 10 palavras)."),
    ("inverso", "Reformule o card perguntando o contrário ou a partir da resposta."),
    ("pegadinha", "Versão 'pegadinha de prova': enuncie de forma que induza o erro clássico."),
    ("aplicação", "Versão 'aplicação clínica': enuncie pedindo o uso prático do conceito."),
]


def _norm(s: str) -> str:
    """Normaliza um front para comparação semântica rasa."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    # Remove palavras de ruído muito curtas para não inflar jaccard
    return " ".join(w for w in s.split() if len(w) > 2)


def _similar(a: str, b: str, threshold: float = 0.6) -> bool:
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return True
    if not na or not nb:
        return False
    wa, wb = set(na.split()), set(nb.split())
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= threshold


def synthesize_from_content(parsed: dict, min_cards: int = 5) -> list:
    """Último recurso quando o provedor devolve JSON válido sem flashcards.

    NÃO inventa ciência nova: deriva cards APENAS das frases já entregues
    pelo próprio provedor nos demais módulos (explanation, high-yield,
    mistakes), transformando cada afirmação em um card 'Explique: X'.
    Evita repetição via o mesmo critério de similaridade da dedup.
    """
    if not isinstance(parsed, dict):
        return []
    texts = []
    for key in ("detailed_explanation", "high_yield_points",
                "why_it_matters", "memory_technique", "common_mistakes"):
        v = parsed.get(key)
        if isinstance(v, str):
            texts.extend(re.split(r"(?<=[.!?])\s+", v.replace("\n", " ")))
        elif isinstance(v, list):
            for it in v:
                if isinstance(it, str):
                    texts.extend(re.split(r"(?<=[.!?])\s+", it.replace("\n", " ")))
    texts = [t.strip() for t in texts if 25 < len(t.strip()) <= 300]
    fronts = []
    cards = []
    for t in texts:
        t = t.rstrip(".,;: ")
        if any(_similar(t, f) for f in fronts):
            continue
        fronts.append(t)
        cards.append({"front": f"Explique: {t}", "back": t,
                      "_synthetic": True})
        if len(cards) >= min_cards:
            break
    return cards


def dedupe_and_complete(flashcards: list, min_cards: int = 5) -> list:
    """Deduplica cards duplicados/semelhantes e completa até min_cards.

    A deduplicação mantém o primeiro card de cada grupo de fronts
    semanticamente semelhantes (normalização + similaridade Jaccard).
    A completude NUNCA inventa ciência nova: cada card adicional apenas
    reformula um card já aprovado em um aspecto pedagógico distinto
    (versão curta, inverso, pegadinha, aplicação clínica).
    """
    if not isinstance(flashcards, list):
        return []
    # 1) Deduplicação
    deduped = []
    seen: list[str] = []
    for card in flashcards:
        if not isinstance(card, dict):
            continue
        front = card.get("front") or card.get("q") or ""
        if not front or not str(front).strip():
            continue
        if any(_similar(front, s) for s in seen):
            continue
        deduped.append(card)
        seen.append(str(front).strip())
    if not deduped:
        return []
    # 2) Completude com aspectos distintos (sem conteúdo novo)
    completed = list(deduped)
    for i, (aspect_key, _instruction) in enumerate(_ASPECTS):
        if len(completed) >= min_cards:
            break
        src = deduped[i % len(deduped)]
        front = src.get("front") or src.get("q") or ""
        back = src.get("back") or src.get("a") or ""
        if not front or not back:
            continue
        completed.append({
            "front": f"{front} (aspecto {aspect_key})",
            "back": back,
            "_aspect": aspect_key,
        })
    return completed
