"""Fase 2 do MIP/PIE — Event Store, cache observacional e isolamento legado."""
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


@pytest.fixture(scope="module")
def qa_client() -> requests.Session:
    client = requests.Session()
    client.headers.update(
        {"Content-Type": "application/json", "Authorization": f"Bearer {QA_TOKEN}"}
    )
    return client


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def phase1_trace(qa_client) -> str:
    response = qa_client.post(
        f"{API}/mip/phase1/assess",
        json={"text": "Explique a anemia ferropriva."},
    )
    assert response.status_code == 200, response.text
    return response.json()["trace"]["trace_id"]


def _payload(
    trace_id: str,
    idempotency_key: str,
    outcome: str = "unknown",
    topic_seed: str = "anemia-ferropriva",
) -> dict:
    return {
        "trace_id": trace_id,
        "idempotency_key": idempotency_key,
        "event_type": "answer_recorded",
        "topic_hash": hashlib.sha256(topic_seed.encode("utf-8")).hexdigest(),
        "curriculum_source": "legacy_faminas_bh",
        "curriculum_version": "legacy-unvalidated",
        "period": 2,
        "module_id": "bases-biologicas",
        "content_mode": "review",
        "learning_outcome": outcome,
    }


def test_phase2_observe_persists_only_new_collections(qa_client, mongo_db, phase1_trace):
    legacy = [
        "content_memory",
        "student_content_events",
        "full_reviews",
        "preceptor_interpretations",
    ]
    before = {name: mongo_db[name].count_documents({}) for name in legacy}
    payload = _payload(
        phase1_trace,
        f"phase2-{uuid.uuid4().hex[:20]}",
        topic_seed=f"isolated-{uuid.uuid4().hex}",
    )
    response = qa_client.post(f"{API}/mip/phase2/observe", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["persisted"] is True
    assert data["idempotent"] is False
    assert data["cache"]["status"] == "candidate_created"
    assert data["cache"]["actual_reuse"] is False
    assert data["shadow_recommendation"]["applies_to_legacy_flow"] is False
    doc = mongo_db.mip_phase2_events.find_one({"event_id": data["event_id"]}, {"_id": 0})
    assert doc is not None
    assert "anemia ferropriva" not in str(doc).lower()
    after = {name: mongo_db[name].count_documents({}) for name in legacy}
    assert before == after


def test_phase2_idempotency_and_observed_cache_hit(qa_client, phase1_trace):
    key = f"phase2-{uuid.uuid4().hex[:20]}"
    topic_seed = f"cache-{uuid.uuid4().hex}"
    payload = _payload(phase1_trace, key, topic_seed=topic_seed)
    first = qa_client.post(f"{API}/mip/phase2/observe", json=payload)
    second = qa_client.post(f"{API}/mip/phase2/observe", json=payload)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["event_id"] == second.json()["event_id"]
    assert second.json()["idempotent"] is True
    next_payload = _payload(
        phase1_trace,
        f"phase2-{uuid.uuid4().hex[:20]}",
        topic_seed=topic_seed,
    )
    next_payload["event_type"] = "content_viewed"
    observed = qa_client.post(f"{API}/mip/phase2/observe", json=next_payload)
    assert observed.status_code == 200, observed.text
    assert observed.json()["cache"]["status"] == "candidate_hit"
    assert observed.json()["cache"]["estimated_generation_avoidable"] is True


def test_phase2_adaptive_recommendation_stays_shadow_only(qa_client, phase1_trace):
    topic_seed = f"adaptive-{uuid.uuid4().hex}"
    for _ in range(2):
        response = qa_client.post(
            f"{API}/mip/phase2/observe",
            json=_payload(
                phase1_trace,
                f"phase2-{uuid.uuid4().hex[:20]}",
                "incorrect",
                topic_seed,
            ),
        )
        assert response.status_code == 200, response.text
    data = response.json()
    assert data["shadow_recommendation"]["code"] == "reinforce_before_advancing"
    assert data["shadow_recommendation"]["applies_to_legacy_flow"] is False


def test_phase2_rejects_unknown_phase1_trace(qa_client):
    payload = _payload(f"mip_{'0' * 32}", f"phase2-{uuid.uuid4().hex[:20]}")
    response = qa_client.post(f"{API}/mip/phase2/observe", json=payload)
    assert response.status_code == 400


def test_phase2_requires_session():
    payload = _payload(f"mip_{'0' * 32}", f"phase2-{uuid.uuid4().hex[:20]}")
    response = requests.post(f"{API}/mip/phase2/observe", json=payload)
    assert response.status_code == 401


def test_phase2_metrics_require_admin_and_state_actuals(qa_client):
    forbidden = qa_client.get(f"{API}/mip/phase2/metrics")
    assert forbidden.status_code == 403
    login = requests.post(
        f"{API}/auth/admin-login",
        json={
            "email": os.environ["ADMIN_EMAIL"],
            "password": os.environ["ADMIN_PASSWORD"],
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["session_token"]
    response = requests.get(
        f"{API}/mip/phase2/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["events_persisted"] >= 1
    assert data["cache_hits"] >= 1
    assert data["actual_reuses"] == 0
    assert data["actual_generations_avoided"] == 0
    assert data["estimated_generations_avoidable"] >= 1
    assert "idempotency" in data
    assert "cost_estimates" in data
    assert "isolation" in data
    assert "operations" in data
    assert "timeline" in data
    assert "recent_events" in data
    assert data["idempotency"]["blocks"] >= 1
    assert data["operations"]["availability_pct"] >= 0