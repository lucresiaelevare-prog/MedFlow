"""Contas administrativas explícitas e visibilidade da navegação administrativa."""
from __future__ import annotations

import os

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_ACCOUNTS = [
    ("ADMIN_EDER_EMAIL", "ADMIN_EDER_PASSWORD", "Eder"),
    ("ADMIN_CARINE_EMAIL", "ADMIN_CARINE_PASSWORD", "Carine"),
]


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.mark.parametrize(("email_key", "password_key", "name"), ADMIN_ACCOUNTS)
def test_named_admin_can_sign_in_and_access_admin_api(email_key, password_key, name, mongo_db):
    email = os.environ[email_key]
    password = os.environ[password_key]
    document = mongo_db.users.find_one({"email": email}, {"_id": 0})
    assert document is not None
    assert document["is_admin"] is True
    assert document["name"] == name
    assert document.get("password_hash", "").startswith("$2")

    response = requests.post(
        f"{API}/auth/admin-login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == email
    assert body["user"]["is_admin"] is True

    admin_response = requests.get(
        f"{API}/admin/whoami",
        headers={"Authorization": f"Bearer {body['session_token']}"},
    )
    assert admin_response.status_code == 200, admin_response.text
    assert admin_response.json()["is_admin"] is True


def test_student_cannot_receive_admin_navigation_permission():
    response = requests.get(
        f"{API}/admin/whoami",
        headers={"Authorization": "Bearer medflow_qa_session_20260805"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_admin"] is False