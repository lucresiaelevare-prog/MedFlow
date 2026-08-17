"""Iteration 10 — Preceptor pedagogy (premium/memorize) + Free/Premium plans.

All scenarios placed inside a single class so pytest-xdist loadscope keeps
them on the SAME worker and executes them in file order (they share state:
QA subscription plan and daily preceptor_review usage).

Only TWO real IA calls in this file (premium free + memorize).
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from routes import preceptor_router  # noqa: E402

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

QA_SESSION = "medflow_qa_session_20260805"
QA_USER_ID = "qa-student-medflow"
ADMIN_EMAIL = "beta.admin@medflow.local"
ADMIN_PASSWORD = "MedFlow-Beta-2026!Q7m4"


# ── module-scope helpers (kept minimal — no fixtures for state) ─────
def _mongo():
    return MongoClient(MONGO_URL)[DB_NAME]


def _today():
    return datetime.now(timezone.utc).date().isoformat()


def _preceptor_count(db, today):
    doc = db.ai_usage.find_one(
        {"user_id": QA_USER_ID, "date": today, "kind": "preceptor_review"}
    )
    return int((doc or {}).get("count", 0))


class TestPreceptorPedagogyIter10:
    """Serialized end-to-end flow: reset → free premium → 429 → memorize
    → admin plan → smart_compact → cleanup."""

    @classmethod
    def setup_class(cls):
        cls.db = _mongo()
        cls.today = _today()
        cls.qa = requests.Session()
        cls.qa.cookies.set("session_token", QA_SESSION)
        cls.admin = requests.Session()
        r = cls.admin.post(
            f"{BASE_URL}/api/auth/admin-login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200, f"admin login: {r.status_code} {r.text[:200]}"
        cls.loop = asyncio.new_event_loop()

    @classmethod
    def teardown_class(cls):
        try:
            cls.loop.close()
        except Exception:
            pass

    # ── 0. reset state ─────────────────────────────────────────────
    def test_00_reset_qa_to_free_and_clean_quota(self):
        self.db.users.update_one(
            {"user_id": QA_USER_ID}, {"$set": {"subscription_plan": "free"}},
        )
        self.db.ai_usage.delete_many(
            {"user_id": QA_USER_ID, "kind": "preceptor_review", "date": self.today}
        )
        self.db.full_reviews.delete_many({"user_id": QA_USER_ID})
        u = self.db.users.find_one({"user_id": QA_USER_ID}, {"_id": 0})
        assert u and u.get("subscription_plan") == "free"
        assert _preceptor_count(self.db, self.today) == 0

    # ── 1. Real premium review, Free plan ─────────────────────────
    def test_01_premium_review_free_real_call(self):
        payload = {
            "topic": "Tríade de Beck",
            "discipline": "Cardiologia",
            "mode": "premium_review",
        }
        t0 = time.perf_counter()
        r = self.qa.post(
            f"{BASE_URL}/api/tutor/preceptor/full-review",
            json=payload, timeout=45,
        )
        wall = time.perf_counter() - t0
        print(f"[iter10] premium wall={wall:.2f}s status={r.status_code}")
        assert r.status_code == 200, f"body={r.text[:400]}"
        data = r.json()
        assert data.get("subscription_plan") == "free"
        assert data.get("delivery_mode") in ("premium_review", "smart_compact")
        review = data.get("review")
        assert isinstance(review, dict)
        expected = ["why_it_matters", "detailed_explanation", "high_yield_points",
                    "flashcards", "practice_questions"]
        missing = [k for k in expected if k not in review]
        assert not missing, f"missing premium modules: {missing} — got={list(review.keys())}"
        fc = review.get("flashcards") or []
        pq = review.get("practice_questions") or []
        print(f"[iter10] premium flashcards={len(fc)} pq={len(pq)}")
        assert isinstance(fc, list) and len(fc) >= 5, f"flashcards low: {len(fc)}"
        assert isinstance(pq, list) and len(pq) >= 2, f"pq low: {len(pq)}"
        # Bonus pedagogical modules (soft — inform if missing)
        extras = {k: (k in review) for k in
                  ("memory_technique", "exam_strategy", "smart_summary", "clinical_case")}
        print(f"[iter10] premium extras={extras}")
        assert _preceptor_count(self.db, self.today) == 1

    # ── 2. Free plan blocked on 2nd premium call ───────────────────
    def test_02_second_premium_free_blocked_429(self):
        r = self.qa.post(
            f"{BASE_URL}/api/tutor/preceptor/full-review",
            json={"topic": "Tríade de Beck", "discipline": "Cardiologia",
                  "mode": "premium_review"},
            timeout=15,
        )
        assert r.status_code == 429, r.text[:300]
        detail = r.json().get("detail")
        assert isinstance(detail, dict)
        msg = (detail.get("message") or "").lower()
        assert "revis" in msg and "premium" in msg, msg
        assert detail.get("limit") == 1
        assert _preceptor_count(self.db, self.today) == 1

    # ── 3. Memorize real call ──────────────────────────────────────
    def test_03_memorize_real_call(self):
        payload = {
            "topic": "Síndrome nefrótica",
            "discipline": "Nefrologia",
            "mode": "memorize",
        }
        t0 = time.perf_counter()
        r = self.qa.post(
            f"{BASE_URL}/api/tutor/preceptor/full-review",
            json=payload, timeout=45,
        )
        wall = time.perf_counter() - t0
        print(f"[iter10] memorize wall={wall:.2f}s status={r.status_code}")
        assert r.status_code == 200, f"body={r.text[:400]}"
        data = r.json()
        assert data.get("delivery_mode") == "memorization"
        review = data.get("review")
        assert isinstance(review, dict)
        for k in ("flashcards", "memory_technique",
                  "common_mistakes", "practice_questions"):
            assert k in review, f"memorize missing {k}: keys={list(review.keys())}"
        fc = review.get("flashcards") or []
        pq_raw = review.get("practice_questions")
        # Prompt asks for "uma vinheta" — model sometimes returns a dict; accept both.
        if isinstance(pq_raw, dict):
            pq = [pq_raw]
        else:
            pq = pq_raw or []
        print(f"[iter10] memorize flashcards={len(fc)} pq={len(pq)} pq_type={type(pq_raw).__name__}")
        assert isinstance(fc, list) and len(fc) >= 5, f"flashcards low: {len(fc)}"
        assert len(pq) >= 1, "no final question in memorize"
        # Premium quota untouched by memorize.
        assert _preceptor_count(self.db, self.today) == 1

    # ── 4. Admin promotes QA to premium ────────────────────────────
    def test_04_admin_sets_premium_and_student_forbidden(self):
        r = self.admin.patch(
            f"{BASE_URL}/api/admin/users/{QA_USER_ID}/subscription-plan",
            json={"subscription_plan": "premium"}, timeout=10,
        )
        assert r.status_code == 200, r.text[:200]
        assert r.json().get("subscription_plan") == "premium"

        me = self.qa.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert me.status_code == 200
        assert me.json()["user"].get("subscription_plan") == "premium"

        # Student is not admin → 403 on PATCH.
        r2 = self.qa.patch(
            f"{BASE_URL}/api/admin/users/{QA_USER_ID}/subscription-plan",
            json={"subscription_plan": "free"}, timeout=10,
        )
        assert r2.status_code == 403, r2.text[:200]

    # ── 5. Premium smart_compact via monkeypatch ───────────────────
    def test_05_premium_smart_compact_prompt(self, monkeypatch):
        # Seed count=5 → next consume → 6 > quality_limit(5) → smart_compact
        self.db.ai_usage.update_one(
            {"user_id": QA_USER_ID, "date": self.today, "kind": "preceptor_review"},
            {"$set": {
                "user_id": QA_USER_ID, "date": self.today,
                "kind": "preceptor_review", "count": 5,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        captured = {}

        async def fake_smart_chat(**kwargs):
            captured.update(kwargs)
            return {
                "text": (
                    '{"topic":"Ciclo de Krebs","discipline":"Bioquímica",'
                    '"review_type":"premium_review","why_it_matters":"x",'
                    '"detailed_explanation":{"paragraphs":["p"]},'
                    '"high_yield_points":["a"],'
                    '"flashcards":[{"front":"q","back":"a"}],'
                    '"practice_questions":[{"stem":"s","options":["A","B","C","D"],'
                    '"answer":"A","explanation":"e"}],'
                    '"common_mistakes":["m"],"memory_technique":"mnemo",'
                    '"smart_summary":{"one_line":"ok","bullets":["b"]}}'
                ),
                "provider": "groq", "model": "mock", "latency_ms": 5,
            }

        monkeypatch.setattr(preceptor_router, "smart_chat", fake_smart_chat)
        body = preceptor_router.FullReviewIn(
            topic="Ciclo de Krebs", discipline="Bioquímica", mode="premium_review",
        )
        user = {"user_id": QA_USER_ID, "subscription_plan": "premium"}
        result = self.loop.run_until_complete(preceptor_router.full_review(body, user))

        assert result["delivery_mode"] == "smart_compact"
        assert result["subscription_plan"] == "premium"
        prompt = captured.get("user_msg", "")
        assert "consolidação inteligente" in prompt.lower(), prompt[:400]
        assert "várias revisões longas" in prompt.lower()
        assert "AULA PREMIUM" not in prompt

    # ── 6. Cleanup: restore free + wipe QA test artifacts ─────────
    def test_06_cleanup_restore_free(self):
        r = self.admin.patch(
            f"{BASE_URL}/api/admin/users/{QA_USER_ID}/subscription-plan",
            json={"subscription_plan": "free"}, timeout=10,
        )
        assert r.status_code == 200
        me = self.qa.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert me.json()["user"].get("subscription_plan") == "free"

        self.db.ai_usage.delete_many(
            {"user_id": QA_USER_ID, "kind": "preceptor_review", "date": self.today}
        )
        self.db.full_reviews.delete_many({"user_id": QA_USER_ID})
        assert _preceptor_count(self.db, self.today) == 0
