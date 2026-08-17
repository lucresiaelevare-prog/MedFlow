"""Iteration 7 — Retest after fixes: Admin login + daily AI quota + no-cache-pollution.

Covers the review request:
1. POST /api/auth/admin-login OK (200) + wrong password → 401 generic (no leaking pydantic).
2. Authz: admin session hits /api/admin/stats (200) with ai_usage tutor_limit=20,
   feedback_limit=3. QA student session → 403 and no auto-promotion.
3. Tutor quota: seed ai_usage {qa,tutor,today,count=19}. One /api/tutor/chat → 200 (20th).
   Second call → 429 with limit=20 and no new provider hit; counter stays at 20.
4. Feedback quota: seed ai_usage {qa,feedback,today,count=3}. /api/checkin with a fresh
   fingerprint → 200 and recommendation.generation_source == "quota_fallback".
   Also: no ACTIVE content_memory checkin_rec doc with generation_source=quota_fallback
   is created (fallback must NOT be cached and served to other students).
5. Cleanup: remove QA ai_usage docs + test checkins created by this run.
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
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "beta.admin@medflow.local")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"] if os.environ.get("ADMIN_PASSWORD") else "MedFlow-Beta-2026!Q7m4"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


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
        assert "session_token" in r.cookies or data.get("session_token")

    def test_admin_login_wrong_password_401_generic(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/admin-login",
            json={"email": ADMIN_EMAIL, "password": "wrong-password-xyz"},
        )
        assert r.status_code == 401, r.text
        body_text = r.text.lower()
        # Must not leak pydantic/email-validator technical english
        assert "special-use" not in body_text
        assert "value is not a valid email" not in body_text


@pytest.fixture(scope="module")
def admin_session():
    """Use the real admin login endpoint now that EmailStr was replaced by str."""
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/admin-login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if r.status_code != 200:
        pytest.skip(f"Admin login failed ({r.status_code}) — skipping downstream tests: {r.text}")
    yield s


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
        qa_client.get(f"{BASE_URL}/api/admin/stats")
        u = mongo_db.users.find_one({"user_id": QA_USER_ID})
        assert u is not None, "QA user missing"
        assert not u.get("is_admin"), "QA student was promoted to admin!"


# --- 3. Tutor quota (single real call → then 429) ---------------------------

class TestTutorQuota:
    def test_tutor_20th_then_429(self, mongo_db, today_str, qa_client):
        _cleanup_qa_usage(mongo_db, today_str)
        mongo_db.ai_usage.insert_one({
            "user_id": QA_USER_ID,
            "date": today_str,
            "kind": "tutor",
            "count": 19,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        r1 = qa_client.post(
            f"{BASE_URL}/api/tutor/chat",
            json={"message": "oi", "prefer": "groq"},
            timeout=30,
        )
        assert r1.status_code == 200, r1.text

        doc = mongo_db.ai_usage.find_one(
            {"user_id": QA_USER_ID, "date": today_str, "kind": "tutor"}
        )
        assert doc["count"] == 20

        r2 = qa_client.post(
            f"{BASE_URL}/api/tutor/chat",
            json={"message": "oi de novo", "prefer": "groq"},
            timeout=15,
        )
        assert r2.status_code == 429, r2.text
        detail = r2.json().get("detail")
        assert isinstance(detail, dict)
        assert detail.get("limit") == 20

        doc2 = mongo_db.ai_usage.find_one(
            {"user_id": QA_USER_ID, "date": today_str, "kind": "tutor"}
        )
        assert doc2["count"] == 20, "Counter incremented on rejected call"


# --- 4. Feedback quota → quota_fallback, no cache pollution ----------------

class TestFeedbackQuotaNoCachePollution:
    def test_checkin_fallback_and_no_cache_insertion(
        self, mongo_db, today_str, qa_client
    ):
        # Prepare: count=3 (limit reached) for feedback kind
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

        # Clean up any legacy quota_fallback pollution left in content_memory
        # from previous (pre-fix) iterations before validating the current fix.
        mongo_db.content_memory.delete_many(
            {
                "kind": "checkin_rec",
                "$or": [
                    {"payload.generation_source": "quota_fallback"},
                    {"content.payload.generation_source": "quota_fallback"},
                    {"generation_source": "quota_fallback"},
                ],
            }
        )

        # Snapshot of existing checkin_rec content_memory docs (do NOT wipe cache;
        # we want to verify no NEW active quota_fallback doc is inserted).
        existing_ids = set(
            d["id"]
            for d in mongo_db.content_memory.find(
                {"kind": "checkin_rec"}, {"id": 1, "_id": 0}
            )
        )

        # Fresh fingerprint: choose atypical buckets to bypass any prior cache
        payload = {
            "sleep_hours": 6.0,   # sl-mid
            "energy": 4,          # en-mid
            "mood": 4,            # mo-mid
            "stress": 2,          # st-low
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

        # Feedback counter must NOT be incremented (has_ai_quota short-circuits)
        doc = mongo_db.ai_usage.find_one(
            {"user_id": QA_USER_ID, "date": today_str, "kind": "feedback"}
        )
        assert doc["count"] == 3

        # No new ACTIVE checkin_rec document containing generation_source=quota_fallback
        # must have been inserted into content_memory.
        bad = list(mongo_db.content_memory.find(
            {
                "kind": "checkin_rec",
                "$or": [
                    {"payload.generation_source": "quota_fallback"},
                    {"content.payload.generation_source": "quota_fallback"},
                    {"generation_source": "quota_fallback"},
                ],
            },
            {"_id": 0, "id": 1},
        ))
        assert not bad, f"quota_fallback recommendation leaked into content_memory cache: {bad}"

        new_after = set(
            d["id"]
            for d in mongo_db.content_memory.find(
                {"kind": "checkin_rec"}, {"id": 1, "_id": 0}
            )
        )
        newly_added = new_after - existing_ids
        assert not newly_added, (
            f"quota_fallback path added new content_memory checkin_rec docs: {newly_added}"
        )


# --- 5. Cleanup -------------------------------------------------------------

class TestCleanup:
    def test_cleanup(self, mongo_db, today_str):
        _cleanup_qa_usage(mongo_db, today_str)
        # Remove test checkins created in TestFeedbackQuotaNoCachePollution
        mongo_db.checkins.delete_many(
            {
                "user_id": QA_USER_ID,
                "sleep_hours": 6.0,
                "energy": 4,
                "mood": 4,
                "stress": 2,
            }
        )
        mongo_db.recommendations.delete_many(
            {"user_id": QA_USER_ID, "generation_source": "quota_fallback"}
        )
        remaining = mongo_db.ai_usage.count_documents(
            {"user_id": QA_USER_ID, "date": today_str}
        )
        assert remaining == 0
