"""P0 deploy-gate verification (iter 2): dev-login, IEA honesty, Preceptor structured gen."""
import os
import uuid
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://medflow-pre-beta.preview.emergentagent.com").rstrip("/")


def _dev_login(session: requests.Session, email: str, name: str = "QA Student"):
    r = session.post(
        f"{BASE_URL}/api/auth/dev-login",
        json={"email": email, "name": name},
        timeout=30,
    )
    assert r.status_code == 200, f"dev-login failed: {r.status_code} {r.text[:300]}"
    return r


@pytest.fixture
def fresh_session():
    s = requests.Session()
    email = f"qa-{uuid.uuid4().hex[:8]}@medflow.local"
    _dev_login(s, email)
    return s, email


# ─── P0.1 Health ─────────────────────────────────────────────────────
def test_backend_health():
    r = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert r.status_code == 200


# ─── P0.2 IEA honesty for a brand-new user ───────────────────────────
def test_iea_new_user_returns_null_no_60(fresh_session):
    s, email = fresh_session
    r = s.get(f"{BASE_URL}/api/iea", timeout=30)
    assert r.status_code == 200, f"GET /api/iea failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    # Top-level
    assert data.get("iea") is None, f"expected iea=null for new user, got {data.get('iea')}"
    assert data.get("has_data") is False, f"expected has_data=false, got {data.get('has_data')}"
    assert data.get("weakest_pillar") is None, f"expected weakest_pillar=null, got {data.get('weakest_pillar')}"
    # No 60 anywhere in payload
    body_text = r.text
    assert "60" not in body_text or '"score":60' not in body_text.replace(" ", ""), \
        f"payload contains hardcoded 60 fallback: {body_text[:500]}"
    # Pillars: every score null, has_data false
    pillars = data.get("pillars") or data.get("pillar_scores") or {}
    assert pillars, f"expected pillars object, got: {data}"
    if isinstance(pillars, dict):
        for name, p in pillars.items():
            if isinstance(p, dict):
                assert p.get("score") is None, f"pillar {name} score should be null, got {p.get('score')}"
                assert p.get("has_data") is False, f"pillar {name} has_data should be false"
            else:
                # if pillars is flat mapping name->score, all must be None
                assert p is None, f"pillar {name} should be null, got {p}"


# ─── P0.3 Preceptor structured generation (real) ─────────────────────
def test_preceptor_full_review_returns_200(fresh_session):
    s, _ = fresh_session
    r = s.post(
        f"{BASE_URL}/api/tutor/preceptor/full-review",
        json={
            "topic": "ciclo de Krebs",
            "discipline": "Bioquímica",
            "mode": "focused",
            "focus": "questions",
        },
        timeout=180,
    )
    assert r.status_code == 200, f"full-review failed: {r.status_code} {r.text[:500]}"
    data = r.json()
    review = data.get("review")
    assert review, f"expected non-empty 'review' object, got: {str(data)[:400]}"
    assert isinstance(review, (dict, list)) and len(review) > 0


def test_exam_feedback_returns_200_with_diagnosis(fresh_session):
    s, _ = fresh_session
    r = s.post(
        f"{BASE_URL}/api/tutor/exam-feedback",
        json={
            "subject": "Cardiologia",
            "weak_topics": "insuficiencia cardiaca, arritmias",
            "grade": 6.5,
        },
        timeout=180,
    )
    assert r.status_code == 200, f"exam-feedback failed: {r.status_code} {r.text[:500]}"
    data = r.json()
    fb = data.get("feedback")
    assert fb and isinstance(fb, dict), f"expected feedback dict, got: {str(data)[:400]}"
    diag = fb.get("diagnosis")
    assert diag and isinstance(diag, str) and len(diag.strip()) > 0, \
        f"expected non-empty diagnosis, got: {diag!r}"
