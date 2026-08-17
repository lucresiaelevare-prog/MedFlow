"""Iteration 3 — Controlled Beta validation.

Covers:
- New endpoint GET /api/admin/business/beta-metrics (admin-only, read-only)
- Access control (student -> 403, unauth -> 401)
- P0 regressions: IEA honesty, Preceptor chat, Preceptor exam-feedback, health
"""
import os
import uuid
import pytest
import requests

def _load_base_url() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except FileNotFoundError:
            pass
    return v.rstrip("/")


BASE_URL = _load_base_url()
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

ADMIN_EMAIL = "admin@medflow.local"
ADMIN_PASSWORD = "Admin123!"


# ─── fixtures ────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/admin-login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"admin-login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    assert tok, f"no session_token in admin-login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def student_token():
    email = f"iter3-{uuid.uuid4().hex[:8]}@medflow.local"
    r = requests.post(
        f"{BASE_URL}/api/auth/dev-login",
        json={"email": email, "name": "Iter3 Student"},
        timeout=30,
    )
    assert r.status_code == 200, f"dev-login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    assert tok
    return tok


# ─── health ──────────────────────────────────────────────────
def test_health_ok():
    r = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok", body


# ─── beta-metrics endpoint ───────────────────────────────────
def test_beta_metrics_admin_success(admin_token):
    r = requests.get(
        f"{BASE_URL}/api/admin/business/beta-metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=60,
    )
    assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text}"
    body = r.json()

    # Top-level keys
    for key in ("activation", "adoption", "retention", "notice"):
        assert key in body, f"missing key: {key}"

    # Activation
    a = body["activation"]
    assert "total_students" in a
    assert isinstance(a["total_students"], int)
    for sub in ("logged_in", "onboarding_done", "first_checkin",
                "first_preceptor", "first_study_session"):
        assert sub in a, f"activation missing {sub}"
        assert "count" in a[sub] and "rate" in a[sub], f"{sub} shape wrong"
        assert isinstance(a[sub]["count"], int)
        rate = a[sub]["rate"]
        assert isinstance(rate, (int, float))
        assert 0.0 <= float(rate) <= 1.0, f"activation.{sub}.rate out of range: {rate}"

    # Adoption
    ad = body["adoption"]
    for k in ("recommendations_shown", "recommendations_started",
              "recommendations_completed", "recommendations_abandoned",
              "adoption_rate", "completion_rate"):
        assert k in ad, f"adoption missing {k}"
    for k in ("adoption_rate", "completion_rate"):
        v = ad[k]
        assert isinstance(v, (int, float))
        assert 0.0 <= float(v) <= 1.0, f"adoption.{k} out of range: {v}"

    # Retention
    ret = body["retention"]
    for w in ("d1", "d3", "d7"):
        assert w in ret, f"retention missing {w}"
        assert "eligible" in ret[w] and "retained" in ret[w] and "rate" in ret[w]
        assert isinstance(ret[w]["eligible"], int)
        assert isinstance(ret[w]["retained"], int)
        rate = ret[w]["rate"]
        assert rate is None or (isinstance(rate, (int, float)) and 0.0 <= float(rate) <= 1.0), \
            f"retention.{w}.rate invalid: {rate}"

    assert isinstance(body["notice"], str) and body["notice"]


def test_beta_metrics_student_forbidden(student_token):
    r = requests.get(
        f"{BASE_URL}/api/admin/business/beta-metrics",
        headers={"Authorization": f"Bearer {student_token}"},
        timeout=30,
    )
    assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"


def test_beta_metrics_unauth_401():
    r = requests.get(f"{BASE_URL}/api/admin/business/beta-metrics", timeout=30)
    assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"


# ─── P0 regressions ──────────────────────────────────────────
def test_iea_honesty_fresh_user():
    email = f"iter3-iea-{uuid.uuid4().hex[:8]}@medflow.local"
    r = requests.post(
        f"{BASE_URL}/api/auth/dev-login",
        json={"email": email, "name": "Iter3 IEA"},
        timeout=30,
    )
    assert r.status_code == 200
    tok = r.json()["session_token"]

    r2 = requests.get(
        f"{BASE_URL}/api/iea",
        headers={"Authorization": f"Bearer {tok}"},
        timeout=30,
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body.get("iea") is None, f"expected iea=null got {body.get('iea')}"
    assert body.get("has_data") is False, f"expected has_data=false got {body.get('has_data')}"
    pillars = body.get("pillars") or body.get("pillar_scores") or {}
    # Look for any pillar-like dict of scores and assert nulls
    if isinstance(pillars, dict):
        for k, v in pillars.items():
            if isinstance(v, dict) and "score" in v:
                assert v["score"] is None, f"pillar {k} score should be null, got {v['score']}"
            elif isinstance(v, (int, float)):
                pytest.fail(f"pillar {k} should be null for fresh user, got {v}")


def test_preceptor_chat(student_token):
    r = requests.post(
        f"{BASE_URL}/api/tutor/chat",
        json={"message": "O que e insuficiencia cardiaca em uma frase?"},
        headers={"Authorization": f"Bearer {student_token}"},
        timeout=60,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:500]}"
    body = r.json()
    text = body.get("text") or body.get("message") or body.get("response") or ""
    assert isinstance(text, str) and len(text.strip()) > 0, f"empty chat text: {body}"


def test_preceptor_exam_feedback(student_token):
    r = requests.post(
        f"{BASE_URL}/api/tutor/exam-feedback",
        json={"subject": "Cardiologia",
              "weak_topics": "insuficiencia cardiaca",
              "grade": 6.5},
        headers={"Authorization": f"Bearer {student_token}"},
        timeout=150,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:500]}"
    body = r.json()
    assert isinstance(body, dict) and body, f"empty feedback body: {body}"
