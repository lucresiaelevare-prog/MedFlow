"""Iteration 9 — Preceptor full-review parse + refund + real call + quota.

Runs actual scenarios (not just inspection):
  1. Unit `_parse_full_review` accepts markdown fenced + backtick multi-line strings.
  2. AIRouterError → 502 and ai_usage feedback count unchanged (refund).
  3. Parse failure ("not json") → 502 and count unchanged (refund).
  4. Single authorized real call: provider=groq, latency<18s, wall<25s, review
     contains smart_summary/flashcards/practice_questions.
  5. Quota exhausted (count=3) → 429 with readable detail.message; provider not called.
  6. Cleanup ai_usage + full_reviews QA docs.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone

import pytest
import requests
from fastapi import HTTPException
from pymongo import MongoClient

# Enable in-process import of the router module for monkeypatch scenarios.
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from ai_router import AIRouterError  # noqa: E402
from routes import preceptor_router  # noqa: E402


BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
QA_SESSION = "medflow_qa_session_20260805"
QA_USER_ID = "qa-student-medflow"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def mongo_db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def today_str():
    return datetime.now(timezone.utc).date().isoformat()


@pytest.fixture(scope="module")
def qa_client():
    s = requests.Session()
    s.cookies.set("session_token", QA_SESSION)
    return s


def _cleanup_feedback(db, today):
    db.ai_usage.delete_many(
        {"user_id": QA_USER_ID, "date": today, "kind": "feedback"}
    )


def _seed_feedback_count(db, today, count):
    db.ai_usage.update_one(
        {"user_id": QA_USER_ID, "date": today, "kind": "feedback"},
        {"$set": {
            "user_id": QA_USER_ID,
            "date": today,
            "kind": "feedback",
            "count": count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


def _feedback_count(db, today):
    doc = db.ai_usage.find_one(
        {"user_id": QA_USER_ID, "date": today, "kind": "feedback"}
    )
    return int((doc or {}).get("count", 0))


# ── 1) Unit: _parse_full_review tolerates markdown + backticks ───────
class TestParseFullReview:
    def test_parse_accepts_markdown_and_backtick_mindmap(self):
        payload = (
            "```json\n"
            "{\n"
            "  \"topic\": \"Anatomia\",\n"
            "  \"mind_map\": `- Sistema Respiratório\n"
            "  - Vias Aéreas\n"
            "    - Superiores\n"
            "    - Inferiores`,\n"
            "  \"smart_summary\": {\"one_line\": \"x\", \"bullets\": [\"a\"]}\n"
            "}\n"
            "```"
        )
        parsed = preceptor_router._parse_full_review(payload)
        assert isinstance(parsed, dict), parsed
        assert parsed["topic"] == "Anatomia"
        assert isinstance(parsed["mind_map"], str)
        assert "Sistema Respiratório" in parsed["mind_map"]
        assert "\n" in parsed["mind_map"]  # multiline preserved
        assert parsed["smart_summary"]["one_line"] == "x"


# ── 2) & 3) Refund on failure via monkeypatch (in-process) ───────────
@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _run(loop, coro):
    return loop.run_until_complete(coro)


class TestRefundOnFailure:
    def test_refund_when_provider_raises(self, monkeypatch, mongo_db, today_str, event_loop):
        _cleanup_feedback(mongo_db, today_str)
        _seed_feedback_count(mongo_db, today_str, 1)
        initial = _feedback_count(mongo_db, today_str)
        assert initial == 1

        async def fake_smart_chat(**_kwargs):
            raise AIRouterError("simulated provider failure")

        monkeypatch.setattr(preceptor_router, "smart_chat", fake_smart_chat)

        body = preceptor_router.FullReviewIn(topic="Teste refund provider")
        user = {"user_id": QA_USER_ID}
        with pytest.raises(HTTPException) as exc:
            _run(event_loop, preceptor_router.full_review(body, user))
        assert exc.value.status_code == 502

        after = _feedback_count(mongo_db, today_str)
        assert after == initial, f"count changed: {initial} -> {after}"
        _cleanup_feedback(mongo_db, today_str)

    def test_refund_when_parse_fails(self, monkeypatch, mongo_db, today_str, event_loop):
        _cleanup_feedback(mongo_db, today_str)
        _seed_feedback_count(mongo_db, today_str, 0)
        initial = _feedback_count(mongo_db, today_str)
        assert initial == 0

        async def fake_smart_chat(**_kwargs):
            return {"text": "not json at all",
                    "provider": "groq", "model": "x", "latency_ms": 1}

        monkeypatch.setattr(preceptor_router, "smart_chat", fake_smart_chat)

        body = preceptor_router.FullReviewIn(topic="Teste refund parse")
        user = {"user_id": QA_USER_ID}
        with pytest.raises(HTTPException) as exc:
            _run(event_loop, preceptor_router.full_review(body, user))
        assert exc.value.status_code == 502

        after = _feedback_count(mongo_db, today_str)
        assert after == initial, f"count changed: {initial} -> {after}"
        _cleanup_feedback(mongo_db, today_str)


# ── 4) Single authorized real Groq call ──────────────────────────────
class TestRealFullReview:
    def test_real_call_groq_and_shape(self, qa_client, mongo_db, today_str):
        _cleanup_feedback(mongo_db, today_str)  # ensure quota available
        payload = {"topic": "Anatomia do sistema respiratório",
                   "discipline": "Anatomia"}
        t0 = time.perf_counter()
        r = qa_client.post(
            f"{BASE_URL}/api/tutor/preceptor/full-review",
            json=payload, timeout=30,
        )
        wall = time.perf_counter() - t0
        print(f"[iter9] real wall={wall:.2f}s status={r.status_code}")

        assert r.status_code == 200, f"body={r.text[:400]}"
        data = r.json()
        assert data.get("provider") == "groq", data.get("provider")
        latency = data.get("latency_ms")
        assert isinstance(latency, int) and latency < 18000, latency
        assert wall < 25.0, f"wall={wall:.2f}s"

        review = data.get("review")
        assert isinstance(review, dict)
        assert isinstance(review.get("smart_summary"), dict), review.keys()
        assert isinstance(review.get("flashcards"), list) and len(review["flashcards"]) >= 1
        assert isinstance(review.get("practice_questions"), list) and len(review["practice_questions"]) >= 1


# ── 5) Quota exhausted → 429 with readable detail.message ────────────
class TestQuotaExhausted:
    def test_429_when_count_equals_limit(self, qa_client, mongo_db, today_str, monkeypatch):
        _seed_feedback_count(mongo_db, today_str, 3)
        # Sentinel to detect any accidental provider hit while quota is full
        called = {"n": 0}

        async def sentinel(**_kwargs):
            called["n"] += 1
            return {"text": "{}", "provider": "groq", "model": "x", "latency_ms": 1}

        monkeypatch.setattr(preceptor_router, "smart_chat", sentinel)

        r = qa_client.post(
            f"{BASE_URL}/api/tutor/preceptor/full-review",
            json={"topic": "Ciclo de Krebs"}, timeout=15,
        )
        assert r.status_code == 429, r.text[:300]
        detail = r.json().get("detail")
        assert isinstance(detail, dict), detail
        msg = detail.get("message")
        assert isinstance(msg, str) and len(msg) > 10, msg
        assert "limite" in msg.lower(), msg
        assert detail.get("limit") == 3

        # count untouched at 3
        assert _feedback_count(mongo_db, today_str) == 3
        # sentinel monkeypatch is on the test process, not the server process:
        # the assertion below is informational only.
        print(f"[iter9] sentinel calls (in-process, informational): {called['n']}")


# ── 6) Final cleanup ─────────────────────────────────────────────────
class TestCleanup:
    def test_cleanup(self, mongo_db, today_str):
        _cleanup_feedback(mongo_db, today_str)
        mongo_db.full_reviews.delete_many({"user_id": QA_USER_ID})
        assert _feedback_count(mongo_db, today_str) == 0
