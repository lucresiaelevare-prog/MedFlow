"""Etapa 1 — teste unitário da política central + integração na Devolutiva.

Não faz chamada externa à IA. Verifica apenas o código/composição.
"""
from content_policy import MEDFLOW_CONTENT_POLICY, MEDFLOW_CONTENT_POLICY_VERSION
from routes.tutor import DEVOLUTIVA_SYSTEM, SYSTEM_PROMPT


def test_policy_exists_and_versioned():
    assert isinstance(MEDFLOW_CONTENT_POLICY, str)
    assert MEDFLOW_CONTENT_POLICY.strip()
    assert len(MEDFLOW_CONTENT_POLICY) > 300
    assert MEDFLOW_CONTENT_POLICY_VERSION == "1.1"


def test_policy_contains_core_invariants():
    p = MEDFLOW_CONTENT_POLICY.lower()
    # anti-alucinação
    assert "nunca invente" in p
    assert "diretrizes" in p and "sociedades" in p and "referências" in p
    # evidência / incerteza
    assert "evidência" in p or "evidencia" in p
    assert "limitação" in p or "limitacao" in p
    assert "hipótese" in p or "hipotese" in p
    # segurança epistemológica + prioridade
    assert "fato estabelecido" in p
    assert "não devem ser enfraquecidas" in p or "nao devem ser enfraquecidas" in p


def test_devolutiva_incorporates_policy_and_operation_prompt():
    # política central presente no system final da Devolutiva
    assert MEDFLOW_CONTENT_POLICY in DEVOLUTIVA_SYSTEM
    # prompt específico da operação preservado
    assert SYSTEM_PROMPT in DEVOLUTIVA_SYSTEM
    # política vem ANTES do prompt específico (prioridade)
    assert DEVOLUTIVA_SYSTEM.index(MEDFLOW_CONTENT_POLICY) < DEVOLUTIVA_SYSTEM.index(SYSTEM_PROMPT)


def test_policy_covers_unknown_clinical_entity():
    # Gap do item 9 (v1.1): entidade clínica desconhecida não deve ser tratada como real.
    p = MEDFLOW_CONTENT_POLICY.lower()
    assert "não for reconhecido" in p or "nao for reconhecido" in p
    assert "não presuma que existe" in p or "nao presuma que existe" in p
    assert "questões como se fosse real" in p or "questoes como se fosse real" in p
