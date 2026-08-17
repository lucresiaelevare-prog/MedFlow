"""Regressão iter21: endpoints principais não devem retornar 5xx e Beta segue observacional."""
from __future__ import annotations

import os

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
QA_TOKEN = "medflow_qa_session_20260805"
HEADERS = {"Authorization": f"Bearer {QA_TOKEN}"}


@pytest.fixture(scope="module")
def admin_headers():
    response = requests.post(
        f"{API}/auth/admin-login",
        json={
            "email": os.environ["ADMIN_CARINE_EMAIL"],
            "password": os.environ["ADMIN_CARINE_PASSWORD"],
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['session_token']}"}


# Home / Today / Dashboard / Priority regressão
@pytest.mark.parametrize(
    "path",
    ["/home/today", "/priority/today", "/experience/state", "/dashboard/summary"],
)
def test_student_endpoints_do_not_5xx(path):
    r = requests.get(f"{API}{path}", headers=HEADERS)
    assert r.status_code < 500, f"{path} -> {r.status_code}: {r.text[:200]}"


# Admin business regressão
@pytest.mark.parametrize(
    "path",
    ["/admin/business/overview", "/admin/business/beta-intelligence"],
)
def test_admin_business_endpoints(admin_headers, path):
    r = requests.get(f"{API}{path}", headers=admin_headers)
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"


def test_beta_intelligence_has_no_pii(admin_headers):
    r = requests.get(f"{API}/admin/business/beta-intelligence", headers=admin_headers)
    assert r.status_code == 200
    body = r.text
    # nenhuma PII de aluno
    assert "user_id" not in body
    assert "@" not in body  # e-mail
    data = r.json()
    assert data["observation_only"] is True


def test_business_overview_refresh_returns_updated_at(admin_headers):
    r1 = requests.get(f"{API}/admin/business/overview", headers=admin_headers)
    r2 = requests.get(f"{API}/admin/business/overview", headers=admin_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert "updated_at" in r1.json()
    assert "updated_at" in r2.json()
