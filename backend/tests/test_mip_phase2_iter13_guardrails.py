"""Guardrails complementares da Fase 2 do MIP/PIE (shadow mode).

Escopo desta bateria:
- Ausência de PII, user_id, e-mail, token e texto clínico nos eventos persistidos.
- actual_reuses / actual_generations_avoided sempre 0 nas métricas.
- Coleções legadas intocadas durante a bateria inteira.
- Regressão: /api/ raiz e uma rota legada do Tutor não emitem 5xx.
- Diferenciação: mesma cache_key com observação distinta é candidate_hit, sem reuso.
"""
from __future__ import annotations

import hashlib
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
QA_TOKEN = "medflow_qa_session_20260805"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
API = f"{BASE_URL}/api"

LEGACY_COLLECTIONS = [
    "content_memory",
    "student_content_events",
    "full_reviews",
    "preceptor_interpretations",
]


@pytest.fixture(scope="module")
def qa_client() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {"Content-Type": "application/json", "Authorization": f"Bearer {QA_TOKEN}"}
    )
    return session


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def phase1_trace(qa_client) -> str:
    response = qa_client.post(
        f"{API}/mip/phase1/assess",
        json={"text": "Descreva a hipertensão arterial sistêmica."},
    )
    assert response.status_code == 200, response.text
    return response.json()["trace"]["trace_id"]


@pytest.fixture(scope="module")
def legacy_snapshot_before(mongo_db):
    return {name: mongo_db[name].count_documents({}) for name in LEGACY_COLLECTIONS}


def _payload(
    trace_id: str,
    idempotency_key: str,
    outcome: str = "unknown",
    topic_seed: str = "guardrail-topic",
    curriculum_source: str = "legacy_faminas_bh",
    event_type: str = "answer_recorded",
) -> dict:
    return {
        "trace_id": trace_id,
        "idempotency_key": idempotency_key,
        "event_type": event_type,
        "topic_hash": hashlib.sha256(topic_seed.encode("utf-8")).hexdigest(),
        "curriculum_source": curriculum_source,
        "curriculum_version": "legacy-unvalidated",
        "period": 3,
        "module_id": "bases-clinicas",
        "content_mode": "review",
        "learning_outcome": outcome,
    }


# --- Guardrail: nenhum dado sensível persistido no Event Store ---
def test_events_do_not_leak_pii_or_clinical_text(qa_client, mongo_db, phase1_trace):
    topic_seed = f"pii-{uuid.uuid4().hex}"
    payload = _payload(
        phase1_trace,
        f"phase2-{uuid.uuid4().hex[:20]}",
        topic_seed=topic_seed,
    )
    response = qa_client.post(f"{API}/mip/phase2/observe", json=payload)
    assert response.status_code == 200, response.text
    event_id = response.json()["event_id"]

    doc = mongo_db.mip_phase2_events.find_one({"event_id": event_id}, {"_id": 0})
    assert doc is not None
    raw = str(doc).lower()

    forbidden_substrings = [
        "@medflow.local",         # e-mail
        "qa.student",             # user id local
        "beta.admin",             # admin
        QA_TOKEN.lower(),         # token
        "medflow_qa",             # prefixo de token
        "hipertens",              # texto clínico
        "anemia",                 # texto clínico
        "ferropriva",             # texto clínico
    ]
    for needle in forbidden_substrings:
        assert needle not in raw, f"Evento vazou substring proibida: {needle}"

    # Estruturalmente, o documento não deve conter chaves que carreguem PII bruta.
    forbidden_keys = {"user_id", "email", "token", "session_token", "raw_text", "prompt"}
    assert not (forbidden_keys & set(doc.keys())), f"Chaves proibidas encontradas: {doc.keys()}"

    # Deve manter apenas o pseudônimo user_hash (sha256 = 64 hex chars).
    assert "user_hash" in doc
    assert len(doc["user_hash"]) == 64
    assert all(c in "0123456789abcdef" for c in doc["user_hash"])
    assert doc.get("shadow_mode") is True


# --- Guardrail: cache é apenas candidato observacional, jamais reuso real ---
def test_same_cache_key_second_observation_is_only_candidate_hit(qa_client, mongo_db, phase1_trace):
    topic_seed = f"cache-guard-{uuid.uuid4().hex}"
    first = qa_client.post(
        f"{API}/mip/phase2/observe",
        json=_payload(phase1_trace, f"phase2-{uuid.uuid4().hex[:20]}", topic_seed=topic_seed),
    )
    assert first.status_code == 200
    assert first.json()["cache"]["status"] == "candidate_created"
    assert first.json()["cache"]["actual_reuse"] is False

    # Observação distinta (event_type diferente) sobre a mesma cache_key.
    second = qa_client.post(
        f"{API}/mip/phase2/observe",
        json=_payload(
            phase1_trace,
            f"phase2-{uuid.uuid4().hex[:20]}",
            topic_seed=topic_seed,
            event_type="content_viewed",
        ),
    )
    assert second.status_code == 200
    body = second.json()
    assert body["cache"]["status"] == "candidate_hit"
    assert body["cache"]["actual_reuse"] is False  # jamais reuso real em shadow
    assert body["cache"]["estimated_generation_avoidable"] is True

    # Registry mantém actual_reuse_count = 0 (nunca é incrementado em shadow).
    reg = mongo_db.mip_phase2_reuse_registry.find_one(
        {"cache_key": body["cache"]["cache_key"]}, {"_id": 0}
    )
    assert reg is not None
    assert reg.get("actual_reuse_count", 0) == 0
    assert reg.get("shadow_mode") is True


# --- Guardrail: matrizes legadas separadas (isolamento entre fontes) ---
def test_legacy_namespaces_stay_separated(qa_client, mongo_db, phase1_trace):
    topic_seed = f"iso-{uuid.uuid4().hex}"
    faminas = qa_client.post(
        f"{API}/mip/phase2/observe",
        json=_payload(
            phase1_trace,
            f"phase2-{uuid.uuid4().hex[:20]}",
            topic_seed=topic_seed,
            curriculum_source="legacy_faminas_bh",
        ),
    )
    fcmmg = qa_client.post(
        f"{API}/mip/phase2/observe",
        json=_payload(
            phase1_trace,
            f"phase2-{uuid.uuid4().hex[:20]}",
            topic_seed=topic_seed,
            curriculum_source="legacy_fcmmg",
        ),
    )
    assert faminas.status_code == 200 and fcmmg.status_code == 200
    key_faminas = faminas.json()["cache"]["cache_key"]
    key_fcmmg = fcmmg.json()["cache"]["cache_key"]
    assert key_faminas != key_fcmmg, "cache_key não pode colidir entre matrizes legadas"

    # Ambas devem ser candidate_created (não hit) porque as matrizes são isoladas.
    assert faminas.json()["cache"]["status"] == "candidate_created"
    assert fcmmg.json()["cache"]["status"] == "candidate_created"


# --- Guardrail: métricas administrativas — actuals sempre 0 ---
def test_metrics_actuals_remain_zero_after_battery():
    login = requests.post(
        f"{API}/auth/admin-login",
        json={
            "email": os.environ["ADMIN_EMAIL"],
            "password": os.environ["ADMIN_PASSWORD"],
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["session_token"]
    resp = requests.get(
        f"{API}/mip/phase2/metrics", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Actuals nunca crescem em shadow mode.
    assert data["actual_reuses"] == 0
    assert data["actual_generations_avoided"] == 0

    # Estimadas devem ser >= actuals e distinguíveis.
    assert data["estimated_generations_avoidable"] >= data["actual_generations_avoided"]
    assert data["estimated_cost_avoidable_usd"] >= 0

    # Nenhum campo deve expor lista de user_ids ou e-mails.
    raw = str(data).lower()
    assert "@medflow.local" not in raw
    assert "qa.student" not in raw


# --- Guardrail: coleções legadas continuam intocadas depois da bateria ---
def test_legacy_collections_untouched_after_full_battery(
    mongo_db,
    legacy_snapshot_before,
    phase1_trace,
    qa_client,
):
    # Executa uma última observação para reforçar a bateria e recontar.
    qa_client.post(
        f"{API}/mip/phase2/observe",
        json=_payload(
            phase1_trace,
            f"phase2-{uuid.uuid4().hex[:20]}",
            topic_seed=f"final-{uuid.uuid4().hex}",
        ),
    )
    after = {name: mongo_db[name].count_documents({}) for name in LEGACY_COLLECTIONS}
    assert after == legacy_snapshot_before, (
        f"Coleções legadas foram alteradas! antes={legacy_snapshot_before} depois={after}"
    )


# --- Regressão: /api/ raiz e rota legada do Tutor não retornam 5xx ---
def test_api_root_no_5xx():
    resp = requests.get(f"{API}/")
    assert resp.status_code < 500, f"/api/ retornou {resp.status_code}: {resp.text[:200]}"


def test_legacy_tutor_route_no_5xx(qa_client):
    # GET /api/tutor/exam-feedback existe (rota legada). Deve responder sem 5xx.
    resp = qa_client.get(f"{API}/tutor/exam-feedback")
    assert resp.status_code < 500, (
        f"/api/tutor/exam-feedback 5xx: {resp.status_code} {resp.text[:200]}"
    )
