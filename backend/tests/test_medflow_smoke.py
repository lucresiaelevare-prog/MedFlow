"""Smoke tests for MedFlow public API + QA student session validation."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://medflow-pre-beta.preview.emergentagent.com").rstrip("/")
QA_TOKEN = "medflow_qa_session_20260805"


def test_api_root_ok():
    r = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data.get("service") == "medflow-copiloto-academico"
    assert data.get("status") == "ok"


def test_auth_me_with_bearer_no_underscore_id():
    r = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {QA_TOKEN}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "user" in body
    user = body["user"]
    assert user.get("email") == "qa.student@medflow.local"
    assert "_id" not in user
    assert "password_hash" not in user


def test_auth_me_with_cookie():
    r = requests.get(
        f"{BASE_URL}/api/auth/me",
        cookies={"session_token": QA_TOKEN},
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "qa.student@medflow.local"


def test_auth_me_without_token_401():
    r = requests.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert r.status_code == 401


def test_dev_login_disabled_returns_404():
    r = requests.post(
        f"{BASE_URL}/api/auth/dev-login",
        json={"email": "dev@medflow.local"},
        timeout=15,
    )
    assert r.status_code == 404, r.text
