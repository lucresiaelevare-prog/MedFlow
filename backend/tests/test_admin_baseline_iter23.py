"""Linha de base agregada: cadastros, atividade, novos alunos e último acesso."""
from __future__ import annotations

import os

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
QA_TOKEN = "medflow_qa_session_20260805"


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


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


def test_overview_baseline_matches_aggregate_student_count(mongo_db, admin_headers):
    response = requests.get(f"{API}/admin/business/overview", headers=admin_headers)
    assert response.status_code == 200, response.text
    growth = response.json()["growth"]
    expected_total = mongo_db.users.count_documents({"is_admin": {"$ne": True}})
    assert growth["total_students"] == expected_total
    assert growth["active_students"] == growth["active_students_30d"]
    assert growth["active_students_7d"] <= growth["active_students_30d"]
    assert growth["new_students_today"] <= growth["new_students_7d"]
    assert growth["new_students_7d"] <= growth["new_students_30d"]
    assert set(growth["last_access"]) == {"latest_at", "students_with_recorded_access"}
    assert "user_id" not in str(growth)
    assert "email" not in str(growth)


def test_student_cannot_read_baseline():
    response = requests.get(
        f"{API}/admin/business/overview",
        headers={"Authorization": f"Bearer {QA_TOKEN}"},
    )
    assert response.status_code == 403, response.text