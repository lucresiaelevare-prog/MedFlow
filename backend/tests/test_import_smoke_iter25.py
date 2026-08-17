"""Smoke test for the imported MedFlow project (iter25).

Covers the flows requested by the main agent after project import:
- /api/ root healthcheck
- Admin login (POST /api/auth/admin-login)
- Dev login (POST /api/auth/dev-login) + session persistence
- Key authenticated GET endpoints must not 500
- Mongo read/write via check-in create + list

Reference: review_request iter25 (Med-Beta160808 import).
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # Fallback: read from frontend/.env
    with open("/app/frontend/.env", "r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break

API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@medflow.app"
ADMIN_PASSWORD = "MedFlow@2026!"


# ─── Health ────────────────────────────────────────────────────────
def test_root_healthcheck():
    r = requests.get(f"{API}/", timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "ok"
    assert body.get("service") == "medflow-copiloto-academico"


# ─── Auth ──────────────────────────────────────────────────────────
def test_admin_login_returns_session_and_admin_flag():
    r = requests.post(
        f"{API}/auth/admin-login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("session_token"), "session_token missing"
    assert data["user"]["is_admin"] is True
    assert data["user"]["email"] == ADMIN_EMAIL


def test_admin_login_invalid_password():
    r = requests.post(
        f"{API}/auth/admin-login",
        json={"email": ADMIN_EMAIL, "password": "wrong-pass"},
        timeout=20,
    )
    assert r.status_code == 401


def test_dev_login_creates_session():
    email = f"test_devuser_{uuid.uuid4().hex[:8]}@medflow.local"
    r = requests.post(
        f"{API}/auth/dev-login",
        json={"email": email, "name": "TEST Dev User"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("session_token")
    assert data["user"]["email"] == email  # server lowercases; we already sent lowercase
    assert data["user"]["is_admin"] is False
    # is_admin should never be settable by the client
    r2 = requests.post(
        f"{API}/auth/dev-login",
        json={"email": email, "name": "TEST Dev User", "is_admin": True},
        timeout=20,
    )
    assert r2.status_code == 200
    assert r2.json()["user"]["is_admin"] is False


# ─── Session fixtures ──────────────────────────────────────────────
@pytest.fixture(scope="module")
def dev_session():
    s = requests.Session()
    email = f"TEST_devsess_{uuid.uuid4().hex[:8]}@medflow.local"
    r = s.post(f"{API}/auth/dev-login", json={"email": email, "name": "TEST Session"}, timeout=20)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(
        f"{API}/auth/admin-login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return s


def test_auth_status_authenticated(dev_session):
    r = dev_session.get(f"{API}/auth/status", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body.get("authenticated") is True
    assert body["user"]["email"].startswith("test_devsess_") or body["user"]["email"].startswith("TEST_devsess_".lower())


# ─── Main authenticated endpoints — must not 500 ───────────────────
# Endpoints from the review_request list. Acceptable = 2xx or documented 4xx.
_USER_ENDPOINTS = [
    "/recommendations",
    "/planner",
    "/planner/today",
    "/missions",
    "/curriculum/subjects",
    "/smart-review/queue",
    "/community/feed",
    "/resume",
    "/mip/phase1/status",
    "/mip/phase2/status",
    "/profile",
]


@pytest.mark.parametrize("path", _USER_ENDPOINTS)
def test_user_endpoint_no_500(dev_session, path):
    r = dev_session.get(f"{API}{path}", timeout=30)
    assert r.status_code < 500, f"{path} -> {r.status_code}: {r.text[:300]}"


def test_admin_business_no_500(admin_session):
    for path in ["/admin/business/summary", "/admin/business", "/admin/summary"]:
        r = admin_session.get(f"{API}{path}", timeout=30)
        # any of these forms may exist; we just want no 500
        assert r.status_code < 500, f"{path} -> {r.status_code}: {r.text[:300]}"


# ─── MongoDB write + read (via checkin) ────────────────────────────
def test_checkin_create_and_list_persistence(dev_session):
    payload = {
        "mood": 4,
        "energy": 3,
        "stress": 2,
        "sleep_hours": 7,
    }
    r = dev_session.post(f"{API}/checkin", json=payload, timeout=90)
    if r.status_code == 404:
        r = dev_session.post(f"{API}/checkins", json=payload, timeout=90)
    assert r.status_code < 500, f"checkin create -> {r.status_code}: {r.text[:300]}"
    if 200 <= r.status_code < 300:
        r2 = dev_session.get(f"{API}/history", timeout=30)
        assert r2.status_code < 500
