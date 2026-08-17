"""Relatório Beta de inteligência: agregados, transparência e nenhuma decisão automática."""
from __future__ import annotations

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
QA_HEADERS = {"Authorization": f"Bearer {QA_TOKEN}"}


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def admin_headers():
    response = requests.post(
        f"{API}/auth/admin-login",
        json={
            "email": os.environ["ADMIN_CARINE_EMAIL"],
            "password": os.environ["ADMIN_CARINE_PASSWORD"],
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['session_token']}"}


def test_recommendation_lifecycle_tracks_display_start_and_why(mongo_db):
    user = mongo_db.user_sessions.find_one({"session_token": QA_TOKEN}, {"_id": 0})
    assert user is not None
    rec_id = f"rec_observe_{uuid.uuid4().hex[:12]}"
    mongo_db.recommendation_events.insert_one(
        {
            "id": rec_id,
            "user_id": user["user_id"],
            "shown_at": None,
            "why_expanded_at": None,
            "started_at": None,
            "completed_at": None,
            "abandoned_at": None,
            "outcome": None,
            "recommended_at": "2026-08-06T00:00:00+00:00",
        }
    )
    for endpoint in ("shown", "why-expanded", "started"):
        response = requests.post(f"{API}/recommendations/{rec_id}/{endpoint}", headers=QA_HEADERS)
        assert response.status_code == 202, response.text
    document = mongo_db.recommendation_events.find_one({"id": rec_id}, {"_id": 0})
    assert document["shown_at"] is not None
    assert document["why_expanded_at"] is not None
    assert document["started_at"] is not None
    assert document["outcome"] is None
    mongo_db.recommendation_events.delete_one({"id": rec_id})


def test_intelligence_report_is_aggregated_and_observational(mongo_db, admin_headers):
    user = mongo_db.user_sessions.find_one({"session_token": QA_TOKEN}, {"_id": 0})
    assert user is not None
    suffix = uuid.uuid4().hex[:12]
    rec_id = f"rec_report_{suffix}"
    confidence_id = f"conf_report_{suffix}"
    mongo_db.recommendation_events.insert_one(
        {
            "id": rec_id,
            "user_id": user["user_id"],
            "shown_at": "2026-08-06T00:00:00+00:00",
            "why_expanded_at": "2026-08-06T00:01:00+00:00",
            "started_at": "2026-08-06T00:02:00+00:00",
            "completed_at": "2026-08-06T00:03:00+00:00",
            "abandoned_at": None,
            "outcome": "completed",
            "recommended_at": "2026-08-06T00:00:00+00:00",
        }
    )
    mongo_db.confidence_shadow_events.insert_one(
        {
            "event_id": confidence_id,
            "idempotency_hash": f"hash_{suffix}",
            "user_id": user["user_id"],
            "discipline": "Cardiologia",
            "topic": "Insuficiência cardíaca",
            "confidence_level": 2,
            "shadow_mode": True,
            "created_at": "2026-08-06T00:00:00+00:00",
        }
    )
    response = requests.get(f"{API}/admin/business/beta-intelligence", headers=admin_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["observation_only"] is True
    assert {"active_users", "recommendations", "confidence", "insights"} <= set(data)
    assert data["recommendations"]["displayed"] >= 1
    assert data["recommendations"]["why_expanded"] >= 1
    assert data["confidence"]["sample_size"] >= 1
    assert "user_id" not in str(data)
    assert "email" not in str(data)
    mongo_db.recommendation_events.delete_one({"id": rec_id})
    mongo_db.confidence_shadow_events.delete_one({"event_id": confidence_id})


def test_student_cannot_read_beta_intelligence_report():
    response = requests.get(f"{API}/admin/business/beta-intelligence", headers=QA_HEADERS)
    assert response.status_code == 403, response.text