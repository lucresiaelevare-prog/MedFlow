"""Onda 3.2 — Mental health alert detection in /checkin + /mental-health endpoints."""
import os
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://medflow-pre-beta.preview.emergentagent.com").rstrip("/")
TOKEN = "test_session_support_1783445454477"
USER_ID = "test-user-support-1783445454477"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


@pytest.fixture
def mongo():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


@pytest.fixture(autouse=True)
def cleanup(mongo):
    mongo.mental_health_alerts.delete_many({"user_id": USER_ID})
    yield
    mongo.mental_health_alerts.delete_many({"user_id": USER_ID})


def _checkin(payload):
    return requests.post(f"{BASE_URL}/api/checkin", headers=HEADERS, json=payload, timeout=60)


def _base_payload(**overrides):
    p = {
        "sleep_hours": 7,
        "energy": 3,
        "mood": 3,
        "stress": 3,
        "upcoming_exam": False,
        "on_call_today": False,
        "commitments": "",
        "free_text": "",
    }
    p.update(overrides)
    return p


class TestCheckinMentalHealth:
    def test_high_risk_keyword(self, mongo):
        r = _checkin(_base_payload(mood=2, stress=4, free_text="não aguento mais, quero morrer"))
        assert r.status_code == 200, r.text
        alert = r.json().get("mental_health_alert")
        assert alert is not None, "expected alert"
        assert alert["level"] == "high"
        assert alert["suggested_contacts"] == ["cvv", "samu", "caps"]
        # persistence
        doc = mongo.mental_health_alerts.find_one({"user_id": USER_ID, "id": alert["id"]})
        assert doc is not None
        assert doc["active_until"] > doc["created_at"]

    def test_scale_only_medium(self):
        r = _checkin(_base_payload(mood=1, stress=5, free_text=""))
        assert r.status_code == 200, r.text
        alert = r.json().get("mental_health_alert")
        assert alert is not None
        assert alert["level"] == "medium"
        assert "sobrecarga" in alert["tags"]
        assert alert["suggested_contacts"] == ["cvv", "caps", "mapa-saude-mental"]

    def test_neutral_no_alert(self):
        r = _checkin(_base_payload(mood=4, stress=2, free_text="dia produtivo, sinto que estou avançando"))
        assert r.status_code == 200, r.text
        assert r.json().get("mental_health_alert") is None

    def test_medium_keywords_soft_signals(self):
        r = _checkin(_base_payload(
            mood=2, stress=4,
            free_text="me sinto sem esperança, ninguém se importa comigo, não durmo há dias"
        ))
        assert r.status_code == 200, r.text
        alert = r.json().get("mental_health_alert")
        assert alert is not None
        assert alert["level"] in {"medium", "high"}


class TestMentalHealthEndpoints:
    def test_get_alert_returns_most_recent(self, mongo):
        r = _checkin(_base_payload(mood=2, stress=4, free_text="quero morrer, não vale mais a pena"))
        assert r.status_code == 200
        alert_id = r.json()["mental_health_alert"]["id"]
        g = requests.get(f"{BASE_URL}/api/mental-health/alert", headers=HEADERS, timeout=30)
        assert g.status_code == 200
        got = g.json()["alert"]
        assert got is not None
        assert got["id"] == alert_id
        assert got["level"] == "high"
        assert got["acknowledged"] is False

    def test_get_alert_null_when_expired(self, mongo):
        # Insert an already-expired alert directly
        from datetime import datetime, timezone, timedelta
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        mongo.mental_health_alerts.insert_one({
            "id": "mha_expired1", "user_id": USER_ID, "level": "high",
            "tags": [], "summary": "", "source": "checkin_free_text",
            "source_ref": "chk_x", "suggested_contacts": ["cvv"],
            "active_until": past, "acknowledged": False,
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
        })
        g = requests.get(f"{BASE_URL}/api/mental-health/alert", headers=HEADERS, timeout=30)
        assert g.status_code == 200
        assert g.json()["alert"] is None

    def test_ack_valid(self, mongo):
        r = _checkin(_base_payload(mood=1, stress=5))
        alert_id = r.json()["mental_health_alert"]["id"]
        a = requests.post(f"{BASE_URL}/api/mental-health/alert/ack",
                          headers=HEADERS, json={"alert_id": alert_id}, timeout=30)
        assert a.status_code == 200
        assert a.json()["ok"] is True
        doc = mongo.mental_health_alerts.find_one({"id": alert_id})
        assert doc["acknowledged"] is True

    def test_ack_invalid_404(self):
        a = requests.post(f"{BASE_URL}/api/mental-health/alert/ack",
                          headers=HEADERS, json={"alert_id": "mha_doesnotexist"}, timeout=30)
        assert a.status_code == 404


class TestRegression:
    def test_support_contacts(self):
        r = requests.get(f"{BASE_URL}/api/support-contacts", headers=HEADERS, timeout=30)
        assert r.status_code == 200
        contacts = r.json()["contacts"]
        assert len(contacts) == 6

    def test_support_log_invalid(self):
        r = requests.post(f"{BASE_URL}/api/support-contacts/log", headers=HEADERS,
                          json={"contact_slug": "not-real", "method": "call"}, timeout=30)
        assert r.status_code == 400

    def test_iea(self):
        r = requests.get(f"{BASE_URL}/api/iea", headers=HEADERS, timeout=30)
        assert r.status_code == 200
        assert "iea" in r.json() or "score" in r.json()

    def test_badges(self):
        r = requests.get(f"{BASE_URL}/api/badges", headers=HEADERS, timeout=30)
        assert r.status_code == 200
