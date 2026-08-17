"""Iter14 — Painel administrativo MIP/PIE Fase 2 (somente leitura).

Cobertura:
- GET /api/mip/phase2/metrics exige admin (estudante -> 403, sem sessão -> 401/403).
- Resposta expõe extensões idempotency/cost_estimates/isolation/operations/
  timeline/recent_events/anomalies, sem PII/email/user_id/token/hash individual.
- Repetir observação com mesma idempotency_key gera bloqueio (blocks aumenta,
  events_persisted não aumenta, coleções legadas intactas).
- Regressão: /api/ e rota Tutor não retornam 5xx.
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
LEGACY = [
    "content_memory",
    "student_content_events",
    "full_reviews",
    "preceptor_interpretations",
]


@pytest.fixture(scope="module")
def qa_client():
    s = requests.Session()
    s.headers.update(
        {"Content-Type": "application/json", "Authorization": f"Bearer {QA_TOKEN}"}
    )
    return s


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{API}/auth/admin-login",
        json={
            "email": os.environ["ADMIN_EMAIL"],
            "password": os.environ["ADMIN_PASSWORD"],
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def admin_client(admin_token):
    s = requests.Session()
    s.headers.update(
        {"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"}
    )
    return s


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def phase1_trace(qa_client):
    r = qa_client.post(f"{API}/mip/phase1/assess", json={"text": "Iter14 dashboard."})
    assert r.status_code == 200, r.text
    return r.json()["trace"]["trace_id"]


def _payload(trace_id, key, seed="iter14"):
    return {
        "trace_id": trace_id,
        "idempotency_key": key,
        "event_type": "answer_recorded",
        "topic_hash": hashlib.sha256(seed.encode()).hexdigest(),
        "curriculum_source": "legacy_faminas_bh",
        "curriculum_version": "legacy-unvalidated",
        "period": 2,
        "module_id": "iter14-mod",
        "content_mode": "review",
        "learning_outcome": "unknown",
    }


# --- Autorização ---
def test_metrics_forbid_student(qa_client):
    r = qa_client.get(f"{API}/mip/phase2/metrics")
    assert r.status_code == 403


def test_metrics_require_auth():
    r = requests.get(f"{API}/mip/phase2/metrics")
    assert r.status_code in (401, 403)


# --- Extensões e ausência de PII no payload de métricas ---
def test_metrics_shape_has_dashboard_extensions(admin_client):
    r = admin_client.get(f"{API}/mip/phase2/metrics")
    assert r.status_code == 200, r.text
    data = r.json()

    # Extensões obrigatórias.
    for key in (
        "idempotency",
        "cost_estimates",
        "isolation",
        "operations",
        "timeline",
        "recent_events",
        "anomalies",
    ):
        assert key in data, f"faltando campo: {key}"

    # Structure detail
    assert "blocks" in data["idempotency"]
    assert "block_rate" in data["idempotency"]
    assert "availability_pct" in data["operations"]
    assert isinstance(data["timeline"], list)
    assert isinstance(data["recent_events"], list)
    assert isinstance(data["anomalies"], list)

    # Nenhum vazamento de PII/tokens/hashes individuais.
    raw = str(data).lower()
    for needle in [
        "@medflow.local",
        "qa.student",
        "beta.admin",
        QA_TOKEN.lower(),
        "medflow_qa",
        "user_id",
        "user_hash",  # crítico: hashes individuais NÃO devem sair no payload agregado
        "session_token",
        "raw_text",
        "prompt",
    ]:
        assert needle not in raw, f"payload de métricas vazou: {needle}"

    # recent_events não podem carregar user_hash/user_id.
    for ev in data["recent_events"]:
        forbidden = {"user_hash", "user_id", "email", "token", "raw_text"}
        assert not (forbidden & set(ev.keys())), f"recent_events vazou chaves: {ev.keys()}"


# --- Idempotência: repetir observação incrementa APENAS blocks ---
def test_idempotency_replay_only_increments_blocks(qa_client, admin_client, mongo_db, phase1_trace):
    before_legacy = {n: mongo_db[n].count_documents({}) for n in LEGACY}
    m_before = admin_client.get(f"{API}/mip/phase2/metrics").json()

    key = f"phase2-{uuid.uuid4().hex[:20]}"
    seed = f"iter14-idem-{uuid.uuid4().hex}"
    p = _payload(phase1_trace, key, seed=seed)

    first = qa_client.post(f"{API}/mip/phase2/observe", json=p)
    second = qa_client.post(f"{API}/mip/phase2/observe", json=p)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["event_id"] == second.json()["event_id"]
    assert first.json()["idempotent"] is False
    assert second.json()["idempotent"] is True

    m_after = admin_client.get(f"{API}/mip/phase2/metrics").json()

    # Bloqueio aumentou em pelo menos 1.
    assert m_after["idempotency"]["blocks"] >= m_before["idempotency"]["blocks"] + 1

    # Events persisted aumentou no máximo 1 (apenas o primeiro POST).
    assert m_after["events_persisted"] - m_before["events_persisted"] <= 1

    # Contagem física no Event Store: exatamente um documento com este event_id.
    event_id = first.json()["event_id"]
    docs = mongo_db.mip_phase2_events.count_documents({"event_id": event_id})
    assert docs == 1, f"Event Store duplicou! docs={docs}"

    # Coleções legadas intactas.
    after_legacy = {n: mongo_db[n].count_documents({}) for n in LEGACY}
    assert before_legacy == after_legacy

    # Actuals permanecem 0 (shadow).
    assert m_after["actual_reuses"] == 0
    assert m_after["actual_generations_avoided"] == 0


# --- Regressão ---
def test_api_root_no_5xx():
    r = requests.get(f"{API}/")
    assert r.status_code < 500


def test_tutor_legacy_no_5xx(qa_client):
    r = qa_client.get(f"{API}/tutor/exam-feedback")
    assert r.status_code < 500
