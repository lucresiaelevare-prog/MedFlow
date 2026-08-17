"""FASE 1 P0 — E2E cross-user isolation gate for /api/tutor/exam-feedback.

Two authenticated users (A, B) post the SAME payload. They MUST receive
different `feedback.content_id` (no cache leak). Then user A reposts and
MUST get `content_source == 'reused'` with the same content_id.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # Fallback: read from /app/frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"')
                    break
    except Exception:
        pass
BASE_URL = (BASE_URL or "").rstrip("/")

PAYLOAD = {
    "subject": "Cardiologia",
    "exam_name": "Prova 1",
    "grade": 4.5,
    "weak_topics": "arritmias, insuficiência cardíaca",
    "strong_topics": "anatomia",
    "notes": "revisar ECG",
}
TIMEOUT = 120


def _dev_login(email: str, name: str) -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/dev-login",
        json={"email": email, "name": name},
        timeout=30,
    )
    assert r.status_code == 200, f"dev-login failed {r.status_code}: {r.text}"
    tok = r.json().get("session_token")
    assert tok, f"no session_token in dev-login response: {r.json()}"
    return tok


def _post_feedback(token: str):
    r = requests.post(
        f"{BASE_URL}/api/tutor/exam-feedback",
        json=PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    return r


@pytest.fixture(scope="module")
def tokens():
    a = _dev_login("phase1_userA@medflow.local", "User A")
    b = _dev_login("phase1_userB@medflow.local", "User B")
    return {"A": a, "B": b}


@pytest.fixture(scope="module")
def resp_a(tokens):
    return _post_feedback(tokens["A"])


@pytest.fixture(scope="module")
def resp_b(tokens):
    return _post_feedback(tokens["B"])


def test_user_a_first_call_ok(resp_a):
    assert resp_a.status_code == 200, f"A: {resp_a.status_code} {resp_a.text[:400]}"
    body = resp_a.json()
    fb = body.get("feedback") or {}
    assert isinstance(fb.get("questions"), list) and len(fb["questions"]) >= 1, (
        f"A: missing questions: {body}"
    )
    assert fb.get("content_id"), f"A: missing content_id: {body}"


def test_user_b_first_call_ok(resp_b):
    assert resp_b.status_code == 200, f"B: {resp_b.status_code} {resp_b.text[:400]}"
    body = resp_b.json()
    fb = body.get("feedback") or {}
    assert isinstance(fb.get("questions"), list) and len(fb["questions"]) >= 1, (
        f"B: missing questions: {body}"
    )
    assert fb.get("content_id"), f"B: missing content_id: {body}"


def test_cross_user_no_cache_leak(resp_a, resp_b):
    """GO/NO-GO: content_id for A and B MUST differ."""
    fb_a = resp_a.json()["feedback"]
    fb_b = resp_b.json()["feedback"]
    cid_a = fb_a["content_id"]
    cid_b = fb_b["content_id"]
    assert cid_a != cid_b, (
        f"CROSS-USER LEAK: same content_id={cid_a} for A and B "
        f"(A.source={fb_a.get('content_source')}, B.source={fb_b.get('content_source')})"
    )
    # user B must not be flagged as reusing (would only reuse if same fingerprint existed)
    # Note: 'reused' by itself is not the issue — the issue is reusing A's content_id.
    # We already assert cid_a != cid_b, which is the true gate.


def test_ten_questions_kept(resp_a):
    """Devolutiva must retain 10 questions."""
    qs = resp_a.json()["feedback"]["questions"]
    assert len(qs) == 10, f"expected 10 questions, got {len(qs)}"


def test_intra_user_reuse_same_content_id(tokens, resp_a):
    """Same user A repost identical payload → reuse same content_id."""
    time.sleep(1)
    r2 = _post_feedback(tokens["A"])
    assert r2.status_code == 200, f"A2: {r2.status_code} {r2.text[:400]}"
    fb2 = r2.json()["feedback"]
    cid_a1 = resp_a.json()["feedback"]["content_id"]
    assert fb2.get("content_id") == cid_a1, (
        f"intra-user reuse broken: first cid={cid_a1}, second cid={fb2.get('content_id')}"
    )
    assert fb2.get("content_source") == "reused", (
        f"expected content_source='reused' on 2nd call, got {fb2.get('content_source')}"
    )


def test_response_shape(resp_a):
    fb = resp_a.json()["feedback"]
    for key in ("diagnosis", "focus_areas", "questions", "content_id", "content_source"):
        assert key in fb, f"missing feedback.{key}"
    assert isinstance(fb["focus_areas"], list)
