"""Feature flags e configurações isoladas do MIP/PIE."""
from __future__ import annotations

import os


def _enabled(name: str) -> bool:
    return os.environ.get(name, "false").strip().lower() in {"1", "true", "yes"}


def phase1_enabled() -> bool:
    """Ativa somente a rota isolada da Fase 1."""
    return _enabled("MIP_PHASE1_ENABLED")


def phase1_shadow_write_enabled() -> bool:
    """Permite persistir traces novos sem tocar em coleções legadas."""
    return _enabled("MIP_PHASE1_SHADOW_WRITE")


def phase2_enabled() -> bool:
    """Ativa somente as rotas isoladas de observação da Fase 2."""
    return _enabled("MIP_PHASE2_ENABLED")


def phase2_shadow_write_enabled() -> bool:
    """Permite Event Store e cache novos, sem tocar em coleções legadas."""
    return _enabled("MIP_PHASE2_SHADOW_WRITE")


def phase2_estimated_generation_usd() -> float:
    """Custo unitário apenas para estimar potencial de reuso, nunca para cobrança."""
    return float(os.environ["MIP_PHASE2_ESTIMATED_GENERATION_USD"])