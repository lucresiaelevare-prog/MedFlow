"""Iteration 6 — Landing v9 + dev-login smoke tests.

Focus:
- /api/ health
- POST /api/auth/dev-login (student + admin) and cookie-set on Response
- GET /api/auth/me via Bearer session token
- Confirms is_admin flag is honored for admin dev-login
"""
import os
import time
import uuid

import pytest
import requests

# Read backend URL from frontend .env (mirrors main app usage)
def _load_backend_url() -> str:
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    return os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


BASE = _load_backend_url()
API = f"{BASE}/api"


@pytest.fixture(scope="module")
def student_email():
    return f"iter6-student-{uuid.uuid4().hex[:8]}@medflow.local"


@pytest.fixture(scope="module")
def admin_email():
    return f"iter6-admin-{uuid.uuid4().hex[:8]}@medflow.local"


# --- Health ---
class TestHealth:
    def test_root_api_ok(self):
        r = requests.get(f"{API}/", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "service" in body
        assert body.get("status") == "ok"


# --- Dev-login: student ---
class TestDevLoginStudent:
    def test_dev_login_creates_user_and_returns_session(self, student_email):
        r = requests.post(
            f"{API}/auth/dev-login",
            json={"email": student_email, "name": "Iter6 Student"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "user" in data and "session_token" in data
        assert data["user"]["email"] == student_email
        assert data["user"].get("is_admin") in (False, None)
        # cookie should be set
        assert "session_token" in r.cookies or "Set-Cookie" in {k.title() for k in r.headers.keys()}
        # store for next test
        TestDevLoginStudent.token = data["session_token"]
        TestDevLoginStudent.user_id = data["user"]["user_id"]

    def test_auth_me_with_bearer(self, student_email):
        token = getattr(TestDevLoginStudent, "token", None)
        assert token, "no session token from prior test"
        r = requests.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        me = r.json()["user"]
        assert me["email"] == student_email
        assert me["user_id"] == TestDevLoginStudent.user_id
        # ensure no mongo _id leaks
        assert "_id" not in me

    def test_auth_me_with_cookie(self, student_email):
        # Re-login using a session (cookie jar)
        s = requests.Session()
        r = s.post(
            f"{API}/auth/dev-login",
            json={"email": student_email, "name": "Iter6 Student"},
            timeout=15,
        )
        assert r.status_code == 200
        # cookie-based /auth/me should also work
        r2 = s.get(f"{API}/auth/me", timeout=15)
        assert r2.status_code == 200, r2.text
        assert r2.json()["user"]["email"] == student_email

    def test_auth_me_unauth_401(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401


# --- Dev-login: admin ---
class TestDevLoginAdmin:
    def test_dev_login_admin(self, admin_email):
        r = requests.post(
            f"{API}/auth/dev-login",
            json={"email": admin_email, "name": "Iter6 Admin", "is_admin": True},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["is_admin"] is True
        assert data["user"]["email"] == admin_email
        assert isinstance(data["session_token"], str) and data["session_token"].startswith("dev_")
