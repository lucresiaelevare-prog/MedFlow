"""Iter20 extras — cobrem casos ainda não exercitados por test_beta_guidance_iter20."""
from __future__ import annotations

import copy
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
QA_TOKEN = "medflow_qa_session_20260805"
HEADERS = {"Authorization": f"Bearer {QA_TOKEN}"}


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _get_qa_user_id(mongo_db) -> str:
    session = mongo_db.user_sessions.find_one({"session_token": QA_TOKEN}, {"_id": 0})
    assert session, "QA session missing"
    return session["user_id"]


# ── Regressão leve: home/today shape estável e sem 5xx ──
def test_home_today_returns_summary_consistency_and_recommendation_with_why():
    r = requests.get(f"{API}/home/today", headers=HEADERS, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    for key in ("summary", "recommendation", "consistency", "date"):
        assert key in data, f"missing {key}"
    summary = data["summary"]
    assert 1 <= len(summary["actions"]) <= 3
    assert summary["estimated_minutes"] == sum(a["duration_min"] for a in summary["actions"])
    for a in summary["actions"]:
        assert a["duration_min"] > 0
        assert a.get("title")
        assert a.get("action_route")
    rec = data["recommendation"]
    assert isinstance(rec.get("why_signals"), list)
    assert isinstance(rec.get("why_now"), (str, type(None))) or rec["why_now"]
    cons = data["consistency"]
    assert cons["window_days"] == 5
    assert 0 <= cons["active_days_last5"] <= 5


# ── Confidence: valida bounds do Pydantic ──
@pytest.mark.parametrize("level", [0, 6, -1, 99])
def test_confidence_rejects_out_of_range_level(level):
    r = requests.post(
        f"{API}/learning/confidence",
        headers=HEADERS,
        json={
            "context_id": "sr_any",
            "context_type": "smart_review",
            "confidence_level": level,
            "idempotency_key": f"key-{uuid.uuid4().hex[:16]}",
        },
        timeout=10,
    )
    assert r.status_code == 422, r.text


def test_confidence_rejects_bad_context_type():
    r = requests.post(
        f"{API}/learning/confidence",
        headers=HEADERS,
        json={
            "context_id": "sr_any",
            "context_type": "flashcard",
            "confidence_level": 3,
            "idempotency_key": f"key-{uuid.uuid4().hex[:16]}",
        },
        timeout=10,
    )
    assert r.status_code == 422


def test_confidence_requires_auth():
    r = requests.post(
        f"{API}/learning/confidence",
        json={
            "context_id": "sr_x",
            "context_type": "smart_review",
            "confidence_level": 3,
            "idempotency_key": f"key-{uuid.uuid4().hex[:16]}",
        },
        timeout=10,
    )
    assert r.status_code in (401, 403), r.text


# ── Isolamento: revisão de outro aluno retorna 404 (não vaza) ──
def test_confidence_does_not_leak_to_another_students_review(mongo_db):
    other_user = f"user_other_{uuid.uuid4().hex[:8]}"
    review_id = f"sr_other_{uuid.uuid4().hex[:12]}"
    mongo_db.smart_reviews.insert_one({
        "id": review_id,
        "user_id": other_user,
        "discipline": "X",
        "topic": "Y",
        "is_correct": True,
        "time_spent_sec": 10,
        "created_at": "2026-08-06T00:00:00+00:00",
    })
    try:
        r = requests.post(
            f"{API}/learning/confidence",
            headers=HEADERS,
            json={
                "context_id": review_id,
                "context_type": "smart_review",
                "confidence_level": 3,
                "idempotency_key": f"key-{uuid.uuid4().hex[:16]}",
            },
            timeout=10,
        )
        assert r.status_code == 404, r.text
    finally:
        mongo_db.smart_reviews.delete_many({"id": review_id})


# ── Passividade: gravar confidence NÃO altera recomendação/plano/priority ──
def test_confidence_event_does_not_mutate_recommendations_or_priority(mongo_db):
    user_id = _get_qa_user_id(mongo_db)

    before_home = requests.get(f"{API}/home/today", headers=HEADERS, timeout=15).json()
    before_priority = requests.get(f"{API}/priority/today", headers=HEADERS, timeout=15)
    assert before_priority.status_code == 200
    before_prio = before_priority.json()

    review_id = f"sr_passive_{uuid.uuid4().hex[:12]}"
    key = f"passive-{uuid.uuid4().hex[:20]}"
    mongo_db.smart_reviews.insert_one({
        "id": review_id,
        "user_id": user_id,
        "discipline": "Cardiologia",
        "topic": "IC",
        "is_correct": False,
        "time_spent_sec": 60,
        "created_at": "2026-08-06T00:00:00+00:00",
    })
    try:
        r = requests.post(
            f"{API}/learning/confidence",
            headers=HEADERS,
            json={
                "context_id": review_id,
                "context_type": "smart_review",
                "confidence_level": 2,
                "idempotency_key": key,
            },
            timeout=10,
        )
        assert r.status_code == 202
        body = r.json()
        assert body["shadow_mode"] is True
        assert body["applied_to_recommendations"] is False

        after_home = requests.get(f"{API}/home/today", headers=HEADERS, timeout=15).json()
        after_prio = requests.get(f"{API}/priority/today", headers=HEADERS, timeout=15).json()

        # Prioridade não muda por causa do shadow event
        assert [i.get("id") for i in before_prio.get("items", [])] == \
               [i.get("id") for i in after_prio.get("items", [])]

        # Recomendação stateful: id pode variar por ser persistida a cada request,
        # mas action_route + title devem permanecer coerentes (motor não considera confidence)
        # Compara "why_signals" — não devem ter novas fontes provenientes do shadow event.
        before_signals = {s.get("source") if isinstance(s, dict) else s for s in before_home["recommendation"].get("why_signals", [])}
        after_signals = {s.get("source") if isinstance(s, dict) else s for s in after_home["recommendation"].get("why_signals", [])}
        assert "confidence_shadow" not in after_signals
        assert "confidence" not in after_signals
        # Sanity: mesma "kind" da recomendação
        assert before_home["recommendation"].get("kind") == after_home["recommendation"].get("kind")

        # MIP Phase 3 continua bloqueada/inexistente
        mip3 = requests.get(f"{API}/mip/phase3/metrics", headers=HEADERS, timeout=10)
        assert mip3.status_code in (403, 404), f"Phase3 should be blocked, got {mip3.status_code}"

        # Nenhum registro em coleções que representam decisões ativas — event fica só em confidence_shadow_events
        assert mongo_db.confidence_shadow_events.count_documents({"context_id": review_id}) == 1
    finally:
        mongo_db.confidence_shadow_events.delete_many({"context_id": review_id})
        mongo_db.smart_reviews.delete_many({"id": review_id})


# ── Regressão leve — endpoints core não retornam 5xx ──
@pytest.mark.parametrize("path", [
    "/home/today",
    "/priority/today",
    "/experience/state",
    "/dashboard/summary",
    "/mip/phase2/metrics",
])
def test_regression_no_5xx_on_core_endpoints(path):
    r = requests.get(f"{API}{path}", headers=HEADERS, timeout=15)
    assert r.status_code < 500, f"{path} -> {r.status_code}: {r.text[:200]}"
