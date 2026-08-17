"""MedFlow backend tests — end-to-end API coverage using seeded session_token."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://medflow-pre-beta.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
TOKEN = "test_session_medflow_123"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def rec_id_holder():
    return {}


# --- Auth ---
class TestAuth:
    def test_me_unauth(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_with_bearer(self):
        r = requests.get(f"{API}/auth/me", headers=HEADERS)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["user_id"] == "test-user-medflow"
        assert data["user"]["email"] == "test.medflow@example.com"


# --- Modes (do these BEFORE checkin so they get applied) ---
class TestModes:
    def test_exam_mode_set_get_clear(self):
        payload = {"exam_name": "TEST_Cardio", "exam_date": "2026-12-31"}
        r = requests.post(f"{API}/mode/exam", json=payload, headers=HEADERS)
        assert r.status_code == 200, r.text
        assert r.json()["exam_mode"]["exam_name"] == "TEST_Cardio"

        r = requests.get(f"{API}/mode/exam", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["exam_mode"]["exam_name"] == "TEST_Cardio"

        r = requests.delete(f"{API}/mode/exam", headers=HEADERS)
        assert r.status_code == 200

        r = requests.get(f"{API}/mode/exam", headers=HEADERS)
        assert r.json()["exam_mode"] is None

    def test_oncall_toggle(self):
        r = requests.post(f"{API}/mode/oncall", json={"active": True}, headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["on_call"] is True
        r = requests.get(f"{API}/mode/oncall", headers=HEADERS)
        assert r.json()["on_call"] is True
        r = requests.post(f"{API}/mode/oncall", json={"active": False}, headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["on_call"] is False


# --- Checkin + Recommendation (LLM call — limited to 1) ---
class TestCheckinAndRecommendation:
    def test_submit_checkin_generates_recommendation(self, rec_id_holder):
        payload = {
            "sleep_hours": 6.5, "energy": 3, "mood": 3, "stress": 3,
            "upcoming_exam": False, "on_call_today": False,
            "commitments": "aula 14h",
        }
        r = requests.post(f"{API}/checkin", json=payload, headers=HEADERS, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "checkin_id" in data
        rec = data["recommendation"]
        assert rec["id"].startswith("rec_")
        assert isinstance(rec["action"], str) and len(rec["action"]) > 3
        assert rec["category"]
        rec_id_holder["id"] = rec["id"]

    def test_latest_recommendation(self, rec_id_holder):
        r = requests.get(f"{API}/recommendation/latest", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["recommendation"] is not None
        assert data["recommendation"]["id"] == rec_id_holder.get("id")

    def test_feedback_persists(self, rec_id_holder):
        rid = rec_id_holder.get("id")
        assert rid, "No rec id from prior test"
        r = requests.post(f"{API}/feedback",
                          json={"recommendation_id": rid, "followed": True, "helped": True, "reason": "ok"},
                          headers=HEADERS)
        assert r.status_code == 200, r.text
        assert r.json()["feedback"]["followed"] is True

        # verify persisted on latest
        r = requests.get(f"{API}/recommendation/latest", headers=HEADERS)
        assert r.json()["feedback"]["followed"] is True

    def test_feedback_wrong_id(self):
        r = requests.post(f"{API}/feedback",
                          json={"recommendation_id": "rec_nope", "followed": False},
                          headers=HEADERS)
        assert r.status_code == 404


# --- Mood / History / Streak ---
class TestMoodHistoryStreak:
    def test_mood_log(self):
        r = requests.post(f"{API}/mood", json={"value": 4, "note": "TEST"}, headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["mood"]["value"] == 4

    def test_history(self):
        r = requests.get(f"{API}/history?days=14", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "checkins" in data and "mood_logs" in data and "adherence_pct" in data
        assert len(data["checkins"]) >= 1
        assert len(data["mood_logs"]) >= 1
        assert isinstance(data["adherence_pct"], int)

    def test_streak(self):
        r = requests.get(f"{API}/streak", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["streak"] >= 1


# --- Mindfulness ---
class TestMindfulness:
    def test_list_sessions(self):
        r = requests.get(f"{API}/mindfulness/sessions", headers=HEADERS)
        assert r.status_code == 200
        sess = r.json()["sessions"]
        assert len(sess) == 3
        slugs = {s["slug"] for s in sess}
        assert {"breath-4-7-8", "body-scan-2min", "grounding-5-4-3-2-1"} <= slugs

    def test_log_mindfulness(self):
        r = requests.post(f"{API}/mindfulness/log",
                          json={"session_slug": "breath-4-7-8", "duration_seconds": 60},
                          headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["log"]["session_slug"] == "breath-4-7-8"


# --- Logout ---
# Note: logout deletes the session by cookie only; skip to preserve token for other runs.
