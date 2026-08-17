"""Iteration 6 — Admin login + daily AI quota (tutor=20, feedback=3).

Covers the review request:
1. Admin login OK (200) + wrong password → 401
2. Authz: admin session hits /api/admin/stats (200) with ai_usage tutor_limit=20,
   feedback_limit=3. QA student session → 403 and no auto-promotion.
3. Tutor quota: seed ai_usage {qa,tutor,today,count=19}. One /api/tutor/chat → 200 (uses #20).
   Second call → 429 with limit=20 and no new provider hit.
4. Feedback quota: seed ai_usage {qa,feedback,today,count=3}. /api/checkin with a fresh key →
   200 and recommendation.generation_source == "quota_fallback".
5. Cleanup: remove QA ai_usage docs created by this run.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

QA_SESSION = "medflow_qa_session_20260805"
QA_USER_ID = "qa-student-medflow"
ADMIN_EMAIL = "beta.admin@medflow.local"
ADMIN_PASSWORD = "MedFlow-Beta-2026!Q7m4"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def mongo_db():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    client.close()


@pytest.fixture(scope="module")
def today_str():
    return datetime.now(timezone.utc).date().isoformat()


@pytest.fixture(scope="module")
def qa_client():
    s = requests.Session()
    s.cookies.set("session_token", QA_SESSION)
    return s


def _cleanup_qa_usage(db, today):
    db.ai_usage.delete_many(
        {"user_id": QA_USER_ID, "date": today, "kind": {"$in": ["tutor", "feedback"]}}
    )


# --- 1. Admin login ---------------------------------------------------------

class TestAdminLogin:
    def test_admin_login_success(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/admin-login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["is_admin"] is True
        assert data["user"]["email"] == ADMIN_EMAIL
        # Cookie set
        assert "session_token" in r.cookies

    def test_admin_login_wrong_password(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/admin-login",
            json={"email": ADMIN_EMAIL, "password": "wrong-password-xyz"},
        )
        assert r.status_code == 401


@pytest.fixture(scope="module")
def admin_session(mongo_db):
    """Workaround for pydantic EmailStr rejecting .local TLD (see report).

    Inserts a user_sessions doc directly for the seeded admin user so we can
    still exercise /api/admin/stats authz + shape.
    """
    admin_user = mongo_db.users.find_one({"email": ADMIN_EMAIL})
    if not admin_user:
        pytest.skip("Admin user not seeded — cannot verify /api/admin/stats")
    from datetime import timedelta
    tok = "TEST_iter6_admin_session"
    mongo_db.user_sessions.update_one(
        {"session_token": tok},
        {"$set": {
            "user_id": admin_user["user_id"],
            "session_token": tok,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        }},
        upsert=True,
    )
    s = requests.Session()
    s.cookies.set("session_token", tok)
    yield s
    mongo_db.user_sessions.delete_one({"session_token": tok})


# --- 2. Authz on /api/admin/stats -------------------------------------------

class TestAdminAuthz:
    def test_admin_stats_ok(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/stats")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "ai_usage" in data
        assert data["ai_usage"]["tutor_limit"] == 20
        assert data["ai_usage"]["feedback_limit"] == 3
        assert "tutor_messages" in data["ai_usage"]
        assert "feedback_generations" in data["ai_usage"]

    def test_qa_student_forbidden(self, qa_client):
        r = qa_client.get(f"{BASE_URL}/api/admin/stats")
        assert r.status_code == 403

    def test_qa_not_auto_promoted(self, qa_client, mongo_db):
        # After hitting admin stats above, QA must remain non-admin
        qa_client.get(f"{BASE_URL}/api/admin/stats")
        u = mongo_db.users.find_one({"user_id": QA_USER_ID})
        assert not u.get("is_admin"), "QA student was promoted to admin!"


# --- 3. Tutor quota (single real call → then 429) ---------------------------

class TestTutorQuota:
    def test_tutor_20th_then_429(self, mongo_db, today_str, qa_client):
        # Prepare: exactly count=19 for today/kind=tutor
        _cleanup_qa_usage(mongo_db, today_str)
        mongo_db.ai_usage.insert_one({
            "user_id": QA_USER_ID,
            "date": today_str,
            "kind": "tutor",
            "count": 19,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # One real, short call — must succeed (20th)
        r1 = qa_client.post(
            f"{BASE_URL}/api/tutor/chat",
            json={"message": "oi", "prefer": "groq"},
            timeout=30,
        )
        assert r1.status_code == 200, r1.text

        # Verify counter now at 20
        doc = mongo_db.ai_usage.find_one(
            {"user_id": QA_USER_ID, "date": today_str, "kind": "tutor"}
        )
        assert doc["count"] == 20

        # Second call must return 429 without hitting provider
        r2 = qa_client.post(
            f"{BASE_URL}/api/tutor/chat",
            json={"message": "oi de novo", "prefer": "groq"},
            timeout=15,
        )
        assert r2.status_code == 429, r2.text
        detail = r2.json().get("detail")
        # detail can be dict per HTTPException
        assert isinstance(detail, dict)
        assert detail.get("limit") == 20

        # Counter must remain 20 (no increment on rejection)
        doc2 = mongo_db.ai_usage.find_one(
            {"user_id": QA_USER_ID, "date": today_str, "kind": "tutor"}
        )
        assert doc2["count"] == 20, "Counter incremented on rejected call"


# --- 4. Feedback quota → quota_fallback keeps check-in working --------------

class TestFeedbackQuota:
    def test_checkin_returns_quota_fallback_when_feedback_exhausted(
        self, mongo_db, today_str, qa_client
    ):
        # Prepare: count=3 for today/kind=feedback (limit reached)
        mongo_db.ai_usage.delete_many(
            {"user_id": QA_USER_ID, "date": today_str, "kind": "feedback"}
        )
        mongo_db.ai_usage.insert_one({
            "user_id": QA_USER_ID,
            "date": today_str,
            "kind": "feedback",
            "count": 3,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Force fresh generation path: clear any cached checkin_rec content_memory
        # so remember_or_generate must call generator (which then hits the quota
        # fallback branch).
        try:
            mongo_db.content_memory.delete_many({"kind": "checkin_rec"})
        except Exception:
            pass

        payload = {
            "sleep_hours": 5.5,
            "energy": 3,
            "mood": 3,
            "stress": 3,
            "upcoming_exam": False,
            "on_call_today": False,
        }
        r = qa_client.post(f"{BASE_URL}/api/checkin", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        rec = data.get("recommendation") or {}
        assert rec.get("generation_source") == "quota_fallback", (
            f"Expected quota_fallback, got: {rec.get('generation_source')} — full rec: {rec}"
        )

        # Counter for feedback should remain at 3 (no increment on quota-exhausted)
        doc = mongo_db.ai_usage.find_one(
            {"user_id": QA_USER_ID, "date": today_str, "kind": "feedback"}
        )
        assert doc["count"] == 3


# --- 5. Cleanup -------------------------------------------------------------

class TestCleanup:
    def test_cleanup(self, mongo_db, today_str):
        _cleanup_qa_usage(mongo_db, today_str)
        remaining = mongo_db.ai_usage.count_documents(
            {"user_id": QA_USER_ID, "date": today_str}
        )
        assert remaining == 0
