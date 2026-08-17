"""Iteration 8 — Preceptor full-review speed/provider + quota response shape.

Review request goals:
- One real POST /api/tutor/preceptor/full-review should return within <25s wall-clock
  and provider=groq, latency_ms<18000 (server-side).
- With ai_usage feedback count=3 seeded, /api/tutor/preceptor/full-review must
  return 429 with detail.message (readable pt-BR) and NOT hit the provider.
- Cleanup: remove QA ai_usage docs and any full_reviews created by this run.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
QA_SESSION = "medflow_qa_session_20260805"
QA_USER_ID = "qa-student-medflow"
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


def _cleanup_qa_feedback(db, today):
    db.ai_usage.delete_many(
        {"user_id": QA_USER_ID, "date": today, "kind": "feedback"}
    )


# ── 1) Real full-review speed + provider ─────────────────────────────
class TestFullReviewSpeedProvider:
    """Single authorized real generation. Must be groq and < 25s wall / 18s server."""

    review_id_created: str | None = None
    server_latency_ms: int | None = None
    wall_seconds: float | None = None

    def test_full_review_returns_fast_via_groq(self, qa_client, mongo_db, today_str):
        # Ensure NO seeded quota block for this call.
        _cleanup_qa_feedback(mongo_db, today_str)

        payload = {"topic": "Anatomia do sistema respiratório"}
        t0 = time.perf_counter()
        r = qa_client.post(
            f"{BASE_URL}/api/tutor/preceptor/full-review",
            json=payload,
            timeout=60,
        )
        wall = time.perf_counter() - t0
        TestFullReviewSpeedProvider.wall_seconds = wall
        print(f"[iter8] full-review wall_seconds={wall:.2f}")

        assert r.status_code == 200, f"status={r.status_code} body={r.text[:300]}"
        data = r.json()
        assert "id" in data and data["id"].startswith("fr_"), data
        assert "review" in data and isinstance(data["review"], dict)

        provider = data.get("provider")
        latency_ms = data.get("latency_ms")
        print(f"[iter8] provider={provider} latency_ms={latency_ms}")

        assert provider == "groq", f"expected provider=groq, got {provider}"
        assert isinstance(latency_ms, int) and latency_ms < 18000, (
            f"latency_ms must be <18000, got {latency_ms}"
        )
        assert wall < 25.0, f"wall time must be <25s, got {wall:.2f}s"

        TestFullReviewSpeedProvider.review_id_created = data["id"]
        TestFullReviewSpeedProvider.server_latency_ms = latency_ms

        # Sanity of returned review shape (concise)
        rv = data["review"]
        assert isinstance(rv.get("topic"), str)


# ── 2) Quota exhausted returns 429 with detail.message ───────────────
class TestFullReviewQuota:
    def test_full_review_429_when_quota_exhausted(self, qa_client, mongo_db, today_str):
        # Seed count=3 to hit AI_FEEDBACK_DAILY_LIMIT
        mongo_db.ai_usage.update_one(
            {"user_id": QA_USER_ID, "date": today_str, "kind": "feedback"},
            {"$set": {
                "user_id": QA_USER_ID,
                "date": today_str,
                "kind": "feedback",
                "count": 3,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

        r = qa_client.post(
            f"{BASE_URL}/api/tutor/preceptor/full-review",
            json={"topic": "Ciclo de Krebs"},
            timeout=15,
        )
        assert r.status_code == 429, f"status={r.status_code} body={r.text[:300]}"
        body = r.json()
        detail = body.get("detail")
        assert isinstance(detail, dict), f"detail should be object, got: {detail!r}"
        assert isinstance(detail.get("message"), str) and len(detail["message"]) > 10
        assert "limit" in detail
        assert detail["limit"] == 3
        # Count remains at 3 (no provider call was made).
        doc = mongo_db.ai_usage.find_one(
            {"user_id": QA_USER_ID, "date": today_str, "kind": "feedback"}
        )
        assert doc and doc.get("count") == 3, doc


# ── 3) Cleanup ───────────────────────────────────────────────────────
class TestCleanup:
    def test_cleanup(self, mongo_db, today_str):
        _cleanup_qa_feedback(mongo_db, today_str)
        # Remove full_reviews created by QA during this iteration
        mongo_db.full_reviews.delete_many({"user_id": QA_USER_ID})
        # sanity
        remaining = mongo_db.ai_usage.count_documents(
            {"user_id": QA_USER_ID, "date": today_str, "kind": "feedback"}
        )
        assert remaining == 0
