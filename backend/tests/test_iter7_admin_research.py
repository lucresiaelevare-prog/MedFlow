"""Iteration 7 — Admin email/password login + Research bank."""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://medflow-pre-beta.preview.emergentagent.com"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@medflow.app"
ADMIN_PASSWORD = "MedFlow2026!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/admin-login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "session_token" in data
    assert data["user"]["is_admin"] is True
    return data["session_token"]


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


# ─── admin-login ─────────────────────────────────────────────
class TestAdminLogin:
    def test_wrong_password_returns_401(self):
        r = requests.post(f"{API}/auth/admin-login",
                          json={"email": ADMIN_EMAIL, "password": "wrong"},
                          timeout=10)
        assert r.status_code == 401
        assert r.json().get("detail") == "Credenciais inválidas"

    def test_unknown_email_returns_401(self):
        r = requests.post(f"{API}/auth/admin-login",
                          json={"email": "nobody@medflow.app", "password": "x"},
                          timeout=10)
        assert r.status_code == 401

    def test_correct_credentials_returns_session(self, admin_token):
        # relies on fixture success
        assert admin_token.startswith("adm_") or len(admin_token) > 10

    def test_cookie_set_on_success(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/admin-login",
                   json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
        assert r.status_code == 200
        # session_token cookie must be set (samesite=none, secure)
        assert "session_token" in s.cookies.get_dict() or any(c.name == "session_token" for c in s.cookies)


# ─── research endpoints ──────────────────────────────────────
class TestResearchEndpoints:
    def test_cohort_requires_auth(self):
        r = requests.get(f"{API}/admin/research/cohort", timeout=10)
        assert r.status_code == 401

    def test_hypotheses_requires_auth(self):
        r = requests.get(f"{API}/admin/research/hypotheses", timeout=10)
        assert r.status_code == 401

    def test_cohort_shape(self, admin_token):
        r = requests.get(f"{API}/admin/research/cohort", headers=_auth(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("population", "period_distribution", "chronotype_distribution",
                  "focus_technique_distribution", "checkins", "recommendations", "notice"):
            assert k in d, f"missing {k}"
        assert "total_users" in d["population"]

    def test_hypotheses_shape(self, admin_token):
        r = requests.get(f"{API}/admin/research/hypotheses", headers=_auth(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "count" in d and "hypotheses" in d and "vision" in d and "notice" in d
        v = d["vision"]
        for k in ("student", "institution", "research"):
            assert k in v
        assert isinstance(d["hypotheses"], list)


# ─── regression on existing endpoints ────────────────────────
class TestExistingRegression:
    def test_admin_stats(self, admin_token):
        r = requests.get(f"{API}/admin/stats", headers=_auth(admin_token), timeout=10)
        assert r.status_code == 200
        assert "users" in r.json()

    def test_admin_whoami(self, admin_token):
        r = requests.get(f"{API}/admin/whoami", headers=_auth(admin_token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["is_admin"] is True
        assert d["email"] == ADMIN_EMAIL

    def test_home_today(self, admin_token):
        r = requests.get(f"{API}/home/today", headers=_auth(admin_token), timeout=15)
        assert r.status_code == 200


# ─── idempotent seeding ─────────────────────────────────────
class TestSeedIdempotent:
    def test_second_login_still_works(self):
        r = requests.post(f"{API}/auth/admin-login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
        assert r.status_code == 200
