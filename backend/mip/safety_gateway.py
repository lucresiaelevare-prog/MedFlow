"""Safety Gateway determinístico da Fase 1, executado em modo de observação."""
from __future__ import annotations

import re

from mip.contracts import SafetyDecision


_PROMPT_INJECTION = re.compile(
    r"(?:ignore|ignore todas|ignore os)\s+(?:as )?(?:instruções|instructions)|"
    r"reveal.*(?:prompt|sistema)|mostre.*(?:prompt|sistema)",
    re.IGNORECASE,
)
_PERSONAL_DATA = re.compile(
    r"\b\d{3}[.\s-]?\d{3}[.\s-]?\d{3}[-\s]?\d{2}\b|"
    r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",
    re.IGNORECASE,
)
_PATIENT_SPECIFIC = re.compile(
    r"(?:meu|minha)\s+paciente|diagnostique\s+(?:me|o paciente)|"
    r"prescreva|qual\s+dose|receita\s+para",
    re.IGNORECASE,
)
_EMERGENCY = re.compile(r"emerg[êe]ncia|risco\s+imediato|socorro", re.IGNORECASE)


def assess_pre_generation(text: str) -> SafetyDecision:
    """Classifica risco de entrada; não muda o comportamento de nenhuma rota legada."""
    reasons: list[str] = []
    if _PROMPT_INJECTION.search(text):
        reasons.append("prompt_injection_signal")
    if _PERSONAL_DATA.search(text):
        reasons.append("personal_data_signal")
    if reasons:
        return SafetyDecision(
            stage="pre_generation",
            action="block",
            reason_codes=reasons,
            critical_failure=True,
        )
    if _PATIENT_SPECIFIC.search(text):
        return SafetyDecision(
            stage="pre_generation",
            action="transform_to_educational",
            reason_codes=["personal_clinical_request"],
        )
    if _EMERGENCY.search(text):
        return SafetyDecision(
            stage="pre_generation",
            action="require_clarification",
            reason_codes=["urgent_context_signal"],
        )
    return SafetyDecision(stage="pre_generation", action="allow")


def assess_post_generation(text: str) -> SafetyDecision:
    """Sinaliza saída sensível sem editar nem bloquear resposta nesta fase de shadow mode."""
    if _PERSONAL_DATA.search(text):
        return SafetyDecision(
            stage="post_generation",
            action="block",
            reason_codes=["personal_data_in_output"],
            critical_failure=True,
        )
    if _PATIENT_SPECIFIC.search(text):
        return SafetyDecision(
            stage="post_generation",
            action="transform_to_educational",
            reason_codes=["personal_clinical_language_in_output"],
        )
    return SafetyDecision(stage="post_generation", action="allow")