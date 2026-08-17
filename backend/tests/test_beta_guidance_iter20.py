"""Camadas explicativas do Beta e coleta de confiança estritamente shadow."""
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
HEADERS = {"Authorization": f"Bearer {QA_TOKEN}"}


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


def test_home_summary_uses_existing_actions_and_reasons_only():
    response = requests.get(f"{API}/home/today", headers=HEADERS)
    assert response.status_code == 200, response.text
    data = response.json()
    summary = data["summary"]
    assert 1 <= len(summary["actions"]) <= 3
    assert summary["estimated_minutes"] == sum(item["duration_min"] for item in summary["actions"])
    recommendation = data["recommendation"]
    assert "why_now" in recommendation
    assert "why_signals" in recommendation
    assert "consistency" in data
    assert 0 <= data["consistency"]["active_days_last5"] <= 5


def test_confidence_is_collected_without_modifying_recommendations(mongo_db):
    session = mongo_db.user_sessions.find_one({"session_token": QA_TOKEN}, {"_id": 0})
    assert session is not None
    user_id = session["user_id"]
    review_id = f"sr_confidence_{uuid.uuid4().hex[:12]}"
    key = f"confidence-{uuid.uuid4().hex[:20]}"
    mongo_db.smart_reviews.insert_one(
        {
            "id": review_id,
            "user_id": user_id,
            "discipline": "Cardiologia",
            "topic": "Insuficiência cardíaca",
            "is_correct": False,
            "time_spent_sec": 74,
            "created_at": "2026-08-06T00:00:00+00:00",
        }
    )
    payload = {
        "context_id": review_id,
        "context_type": "smart_review",
        "confidence_level": 4,
        "idempotency_key": key,
    }
    first = requests.post(f"{API}/learning/confidence", headers=HEADERS, json=payload)
    second = requests.post(f"{API}/learning/confidence", headers=HEADERS, json=payload)
    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert first.json()["applied_to_recommendations"] is False
    assert second.json()["duplicate"] is True
    event = mongo_db.confidence_shadow_events.find_one(
        {"event_id": first.json()["event_id"]},
        {"_id": 0},
    )
    assert event is not None
    assert event["shadow_mode"] is True
    assert event["answer_outcome"] is False
    mongo_db.confidence_shadow_events.delete_many({"event_id": first.json()["event_id"]})
    mongo_db.smart_reviews.delete_many({"id": review_id})


def test_confidence_rejects_review_owned_by_another_student(mongo_db):
    response = requests.post(
        f"{API}/learning/confidence",
        headers=HEADERS,
        json={
            "context_id": "sr_missing_review",
            "context_type": "smart_review",
            "confidence_level": 3,
            "idempotency_key": f"confidence-{uuid.uuid4().hex[:20]}",
        },
    )
    assert response.status_code == 404, response.text