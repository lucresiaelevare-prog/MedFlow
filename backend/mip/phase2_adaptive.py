"""Recomendação adaptativa observacional da Fase 2, sem alterar trilhas legadas."""
from __future__ import annotations

from mip.contracts import ShadowRecommendation


def recommend_shadow(history: dict[str, int]) -> ShadowRecommendation:
    """Produz somente hipótese reversível a partir do Event Store isolado."""
    evidence_count = int(history.get("total") or 0)
    incorrect = int(history.get("incorrect") or 0)
    completed = int(history.get("completed") or 0)
    if incorrect >= 2:
        return ShadowRecommendation(
            code="reinforce_before_advancing",
            confidence="observational",
            evidence_count=evidence_count,
        )
    if completed >= 2:
        return ShadowRecommendation(
            code="keep_current_path",
            confidence="low",
            evidence_count=evidence_count,
        )
    return ShadowRecommendation(
        code="collect_more_data",
        confidence="insufficient" if evidence_count < 2 else "low",
        evidence_count=evidence_count,
    )