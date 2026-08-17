"""P0.2.2 — Learning Memory Engine tests.

Cover: /api/learning/* endpoints, admin research (content-reuse, collective-difficulty),
sanity of /api/home/today with weakest_topic wire-in.
"""
import os
import time
import uuid

import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except FileNotFoundError:
            pass
    return v.rstrip("/")

BASE_URL = _load_backend_url()
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

TIMEOUT = 45  # LLM real generation can take 5-10s

# Unique variant per test-run — forces fresh generation to avoid colliding with prior fingerprints.
VARIANT = f"test-{int(time.time())}"
DISCIPLINE = "Farmacologia"
TOPIC = "Beta bloqueadores"
SUBTOPIC = "Propranolol"
PERIOD = 4


# ─── Fixtures ────────────────────────────────────────────────────
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
def student_a_token():
    return _dev_login(f"test_lm_a_{uuid.uuid4().hex[:6]}@medflow.local", "Test Student A")


@pytest.fixture(scope="module")
def student_b_token():
    return _dev_login(f"test_lm_b_{uuid.uuid4().hex[:6]}@medflow.local", "Test Student B")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/admin-login",
        json={"email": "admin@medflow.app", "password": "MedFlow2026!"},
        timeout=15,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    assert tok
    return tok


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ─── Shared state across ordered tests ───────────────────────────
CTX: dict = {}


# ─── Tests ───────────────────────────────────────────────────────
class TestLearningRequestFlow:
    def test_01_first_request_generates(self, student_a_token):
        body = {
            "kind": "flashcard",
            "discipline": DISCIPLINE,
            "topic": TOPIC,
            "subtopic": SUBTOPIC,
            "period": PERIOD,
            "variant": VARIANT,
        }
        r = requests.post(
            f"{BASE_URL}/api/learning/request",
            json=body,
            headers=_h(student_a_token),
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert data["source"] == "generated", f"expected generated, got {data['source']}"
        assert "content" in data and data["content"].get("id")
        assert "payload" in data["content"]
        assert data["content"]["kind"] == "flashcard"
        payload = data["content"]["payload"]
        # flashcard schema — front/back OR raw fallback
        assert isinstance(payload, dict)
        CTX["content_id"] = data["content"]["id"]
        CTX["event_id_a_shown"] = data.get("event_id")

    def test_02_second_request_reuses(self, student_b_token):
        body = {
            "kind": "flashcard",
            "discipline": DISCIPLINE,
            "topic": TOPIC,
            "subtopic": SUBTOPIC,
            "period": PERIOD,
            "variant": VARIANT,
        }
        r = requests.post(
            f"{BASE_URL}/api/learning/request",
            json=body,
            headers=_h(student_b_token),
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["source"] == "reused", f"expected reused, got {data['source']}"
        assert data["content"]["id"] == CTX["content_id"]

    def test_03_answered_three_times(self, student_a_token):
        cid = CTX["content_id"]
        for _ in range(3):
            r = requests.post(
                f"{BASE_URL}/api/learning/content/{cid}/answered",
                json={"correct": False, "time_spent_sec": 30},
                headers=_h(student_a_token),
                timeout=15,
            )
            assert r.status_code == 202, r.text
            j = r.json()
            assert j.get("ok") is True
            assert j.get("event_id")

    def test_04_mastery_present(self, student_a_token):
        r = requests.get(
            f"{BASE_URL}/api/learning/me/mastery",
            headers=_h(student_a_token),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["topics_count"] >= 1
        # find our subtopic
        subs = [t for t in data["topics"] if SUBTOPIC.lower() in (t.get("subtopic") or "").lower()]
        assert subs, f"subtopic not found in mastery topics: {data['topics']}"
        t = subs[0]
        assert t["answered"] >= 3
        assert t["mastery_score"] is not None
        assert 0.0 <= t["mastery_score"] <= 1.0

    def test_05_mastery_discipline_filter(self, student_a_token):
        r = requests.get(
            f"{BASE_URL}/api/learning/me/mastery",
            params={"discipline": DISCIPLINE},
            headers=_h(student_a_token),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["discipline"] is not None
        # every topic should match discipline slug
        for t in data["topics"]:
            assert "farmacologia" in t["discipline"].lower()

    def test_06_weakest_returns_topic_or_null(self, student_a_token):
        r = requests.get(
            f"{BASE_URL}/api/learning/me/weakest",
            headers=_h(student_a_token),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        w = r.json().get("weakest")
        # 3 wrong answers → mastery=0 → should be weakest, not null
        assert w is not None, "expected a weakest topic (all wrong)"
        assert w["mastery_score"] < 0.75

    def test_07_reviewed_event(self, student_a_token):
        cid = CTX["content_id"]
        r = requests.post(
            f"{BASE_URL}/api/learning/content/{cid}/reviewed",
            json={"time_spent_sec": 10},
            headers=_h(student_a_token),
            timeout=15,
        )
        assert r.status_code == 202, r.text
        assert r.json().get("ok") is True

    def test_08_completed_event(self, student_a_token):
        cid = CTX["content_id"]
        r = requests.post(
            f"{BASE_URL}/api/learning/content/{cid}/completed",
            headers=_h(student_a_token),
            timeout=15,
        )
        assert r.status_code == 202, r.text
        assert r.json().get("ok") is True

    def test_09_reported_error_event(self, student_a_token):
        cid = CTX["content_id"]
        r = requests.post(
            f"{BASE_URL}/api/learning/content/{cid}/reported-error",
            json={"note": "test report"},
            headers=_h(student_a_token),
            timeout=15,
        )
        assert r.status_code == 202, r.text
        assert r.json().get("ok") is True


class TestLearningAuthAndValidation:
    def test_no_auth_returns_401(self):
        r = requests.post(
            f"{BASE_URL}/api/learning/request",
            json={"kind": "flashcard", "discipline": "X", "topic": "Y"},
            timeout=15,
        )
        assert r.status_code in (401, 403), r.status_code

    def test_invalid_kind_returns_400_or_422(self, student_a_token):
        r = requests.post(
            f"{BASE_URL}/api/learning/request",
            json={"kind": "poem", "discipline": "X", "topic": "Y"},
            headers=_h(student_a_token),
            timeout=15,
        )
        # Pydantic pattern validation → 422; ValueError inside → 400.
        assert r.status_code in (400, 422), r.text
        assert "detail" in r.json()

    def test_answered_content_not_found_404(self, student_a_token):
        r = requests.post(
            f"{BASE_URL}/api/learning/content/cm_doesnotexist/answered",
            json={"correct": True, "time_spent_sec": 10},
            headers=_h(student_a_token),
            timeout=15,
        )
        assert r.status_code == 404, r.text


class TestAdminResearch:
    def test_content_reuse_metrics(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/research/content-reuse",
            headers=_h(admin_token),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("content_count", "total_usage", "reuses", "reuse_ratio", "generator_distribution", "events"):
            assert k in d, f"missing {k}"
        assert "total" in d["events"] and "shown" in d["events"]
        assert isinstance(d["content_count"], int)
        assert isinstance(d["reuse_ratio"], (int, float))

    def test_collective_difficulty(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/research/collective-difficulty",
            params={"min_sample": 3},
            headers=_h(admin_token),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d
        items = d["items"]
        # verify ordering desc + fields
        prev = 1.1
        for it in items:
            for k in ("discipline", "topic", "subtopic", "attempts", "difficulty"):
                assert k in it, f"missing {k} in item"
            assert 0.0 <= it["difficulty"] <= 1.0
            assert it["difficulty"] <= prev + 1e-9
            prev = it["difficulty"]

    def test_collective_difficulty_requires_admin(self, student_a_token):
        # student (non-admin) should be denied
        r = requests.get(
            f"{BASE_URL}/api/admin/research/collective-difficulty",
            headers=_h(student_a_token),
            timeout=15,
        )
        assert r.status_code in (401, 403), r.status_code

    def test_collective_difficulty_no_auth(self):
        r = requests.get(
            f"{BASE_URL}/api/admin/research/collective-difficulty",
            timeout=15,
        )
        assert r.status_code in (401, 403), r.status_code


class TestSanityHomeToday:
    def test_home_today_still_200(self, student_a_token):
        r = requests.get(
            f"{BASE_URL}/api/home/today",
            headers=_h(student_a_token),
            timeout=20,
        )
        assert r.status_code == 200, r.text
