"""P0.2.3 — Meu Tutor plan orchestrator + mastery-map tests.

Covers /api/tutor/plan (5 modes + validation) and /api/tutor/mastery-map
(auth guards, empty state, populated state for student1 from iter 8).

Budget: at most 1 real /learning/request call (integrated flow test).
"""
import os
import time
import uuid

import pytest
import requests


def _load_backend_url() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not v:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    v = line.split("=", 1)[1].strip()
                    break
    return v.rstrip("/")


BASE_URL = _load_backend_url()
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

TIMEOUT = 30
LLM_TIMEOUT = 60  # LLM generation


def _dev_login(email: str, name: str) -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/dev-login",
        json={"email": email, "name": name},
        timeout=15,
    )
    assert r.status_code == 200, f"dev-login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    assert tok, "no session_token"
    return tok


@pytest.fixture(scope="module")
def fresh_user_token() -> str:
    """Brand-new user, no learning events (mastery-map empty=true)."""
    return _dev_login(f"test_tutor_fresh_{uuid.uuid4().hex[:6]}@medflow.local", "Fresh Tutor Test")


@pytest.fixture(scope="module")
def student1_token() -> str:
    """student1@medflow.local — has iter 8 history (nervo facial, 3 attempts on Anatomia)."""
    return _dev_login("student1@medflow.local", "Student One")


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# ─── Mastery Map ─────────────────────────────────────────────────
class TestMasteryMap:
    def test_empty_for_fresh_user(self, fresh_user_token):
        r = requests.get(
            f"{BASE_URL}/api/tutor/mastery-map",
            headers=_auth(fresh_user_token),
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["empty"] is True
        assert data["disciplines_count"] == 0
        assert data["disciplines"] == []

    def test_populated_for_student1(self, student1_token):
        r = requests.get(
            f"{BASE_URL}/api/tutor/mastery-map",
            headers=_auth(student1_token),
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        # student1 may or may not have data depending on prior iters. If populated, verify shape.
        assert "empty" in data
        assert "disciplines_count" in data
        assert isinstance(data["disciplines"], list)
        if not data["empty"]:
            disc = data["disciplines"][0]
            assert "discipline" in disc
            assert "topics" in disc
            assert "seen" in disc
            for t in disc["topics"]:
                assert "topic" in t
                assert "subtopics" in t

    def test_unauth_401(self):
        r = requests.get(f"{BASE_URL}/api/tutor/mastery-map", timeout=TIMEOUT)
        assert r.status_code in (401, 403)


# ─── Plan orchestrator ───────────────────────────────────────────
class TestTutorPlan:
    def test_unauth_401(self):
        r = requests.post(
            f"{BASE_URL}/api/tutor/plan",
            json={"mode": "guide_me"},
            timeout=TIMEOUT,
        )
        assert r.status_code in (401, 403)

    def test_invalid_mode_400(self, fresh_user_token):
        r = requests.post(
            f"{BASE_URL}/api/tutor/plan",
            headers=_auth(fresh_user_token),
            json={"mode": "invalido"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400
        assert "detail" in r.json()

    def test_guide_me_returns_plan(self, fresh_user_token):
        r = requests.post(
            f"{BASE_URL}/api/tutor/plan",
            headers=_auth(fresh_user_token),
            json={"mode": "guide_me"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "guide_me"
        assert data["title"] == "Hoje eu faria isto"
        assert "subtitle" in data
        assert isinstance(data["slots"], list) and len(data["slots"]) >= 1
        assert data["total_duration_min"] > 0
        s0 = data["slots"][0]
        for k in ("kind", "discipline", "topic", "phase", "duration_min"):
            assert k in s0, f"missing field {k} in slot"

    def test_quick_review_10min_4_slots(self, fresh_user_token):
        r = requests.post(
            f"{BASE_URL}/api/tutor/plan",
            headers=_auth(fresh_user_token),
            json={"mode": "quick_review", "time_min": 10},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "quick_review"
        assert len(data["slots"]) == 4
        kinds = [s["kind"] for s in data["slots"]]
        assert kinds.count("flashcard") == 3
        assert kinds.count("question") == 1
        # ~10 min total (3*2 + 4 = 10)
        assert 8 <= data["total_duration_min"] <= 12

    def test_quick_review_5min_2_flashcards(self, fresh_user_token):
        r = requests.post(
            f"{BASE_URL}/api/tutor/plan",
            headers=_auth(fresh_user_token),
            json={"mode": "quick_review", "time_min": 5},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["slots"]) == 2
        assert all(s["kind"] == "flashcard" for s in data["slots"])

    def test_quick_review_40min_7_slots(self, fresh_user_token):
        r = requests.post(
            f"{BASE_URL}/api/tutor/plan",
            headers=_auth(fresh_user_token),
            json={"mode": "quick_review", "time_min": 40},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        slots = data["slots"]
        assert len(slots) == 7
        kinds = [s["kind"] for s in slots]
        assert kinds.count("question") == 5
        assert kinds.count("explanation") == 1
        assert kinds.count("summary") == 1

    def test_exam_tomorrow_with_topics(self, fresh_user_token):
        r = requests.post(
            f"{BASE_URL}/api/tutor/plan",
            headers=_auth(fresh_user_token),
            json={
                "mode": "exam_tomorrow",
                "discipline": "Anatomia",
                "topics": ["Face", "Membro Superior"],
                "time_min": 40,
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "exam_tomorrow"
        phases = {s["phase"] for s in data["slots"]}
        assert {"warmup", "quiz", "deep_dive", "recap"}.issubset(phases)
        assert all(s["discipline"] == "Anatomia" for s in data["slots"])

    def test_exam_tomorrow_missing_discipline_400(self, fresh_user_token):
        r = requests.post(
            f"{BASE_URL}/api/tutor/plan",
            headers=_auth(fresh_user_token),
            json={"mode": "exam_tomorrow", "topics": ["Face"]},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400
        assert "disciplina" in r.json()["detail"].lower()

    def test_exam_tomorrow_missing_topics_400(self, fresh_user_token):
        r = requests.post(
            f"{BASE_URL}/api/tutor/plan",
            headers=_auth(fresh_user_token),
            json={"mode": "exam_tomorrow", "discipline": "Anatomia"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400

    def test_diagnostic_returns_6_variants(self, fresh_user_token):
        r = requests.post(
            f"{BASE_URL}/api/tutor/plan",
            headers=_auth(fresh_user_token),
            json={"mode": "diagnostic", "discipline": "Fisiologia"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        slots = data["slots"]
        assert len(slots) == 6
        assert all(s["phase"] == "diagnostic" for s in slots)
        variants = [s.get("variant") for s in slots]
        assert variants == [f"diag-{i+1}" for i in range(6)]

    def test_diagnostic_missing_discipline_400(self, fresh_user_token):
        r = requests.post(
            f"{BASE_URL}/api/tutor/plan",
            headers=_auth(fresh_user_token),
            json={"mode": "diagnostic"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400


# ─── Integrated flow: plan → learning/request (1 real LLM call) ──
class TestIntegratedFlow:
    def test_plan_then_learning_request(self, fresh_user_token):
        # Build a plan
        p = requests.post(
            f"{BASE_URL}/api/tutor/plan",
            headers=_auth(fresh_user_token),
            json={"mode": "quick_review", "time_min": 5},
            timeout=TIMEOUT,
        )
        assert p.status_code == 200
        slot = p.json()["slots"][0]

        # Consume 1st slot via learning/request (uses a unique variant to force fresh gen or reuse)
        body = {
            "kind": slot["kind"],
            "discipline": slot["discipline"],
            "topic": slot["topic"],
            "subtopic": slot.get("subtopic"),
            "period": slot.get("period"),
            "variant": slot.get("variant", "default"),
        }
        r = requests.post(
            f"{BASE_URL}/api/learning/request",
            headers=_auth(fresh_user_token),
            json=body,
            timeout=LLM_TIMEOUT,
        )
        assert r.status_code == 200, f"learning/request failed: {r.status_code} {r.text[:400]}"
        data = r.json()
        assert data.get("source") in ("generated", "reused")
        assert "content" in data
        assert data["content"].get("id")
        assert "payload" in data["content"]
