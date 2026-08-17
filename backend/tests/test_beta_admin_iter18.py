"""Regressões do painel Beta: acesso, conteúdo e plantão de dúvidas."""
from __future__ import annotations

import os
import uuid

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


def test_beta_overview_has_only_required_management_metrics(admin_headers):
    response = requests.get(f"{API}/admin/business/overview", headers=admin_headers)
    assert response.status_code == 200, response.text
    growth = response.json()["growth"]
    assert {"total_students", "active_students", "new_students_30d", "plans"} <= set(growth)
    assert set(growth["plans"]) == {"free", "premium"}
    assert response.json()["revenue"]["connected"] is False


def test_content_create_and_publish_toggle(admin_headers, mongo_db):
    response = requests.post(
        f"{API}/admin/business/content",
        headers=admin_headers,
        json={"title": "PDF de teste Beta", "content_type": "pdf", "published": True},
    )
    assert response.status_code == 200, response.text
    content_id = response.json()["item"]["id"]
    hidden = requests.patch(
        f"{API}/admin/business/content/{content_id}/visibility",
        headers=admin_headers,
        json={"published": False},
    )
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["published"] is False
    mongo_db.cms_resources.delete_one({"id": content_id})


def test_question_requires_consent_for_anonymous_publication(admin_headers, mongo_db):
    response = requests.post(
        f"{API}/questions",
        headers={"Authorization": f"Bearer {QA_TOKEN}"},
        json={"message": "Dúvida sem consentimento para publicação.", "allow_anonymous_publication": False},
    )
    assert response.status_code == 200, response.text
    question_id = response.json()["question"]["id"]
    denied = requests.patch(
        f"{API}/admin/business/questions/{question_id}",
        headers=admin_headers,
        json={"published_anonymously": True},
    )
    assert denied.status_code == 400, denied.text
    mongo_db.questions.delete_one({"id": question_id})


def test_question_reply_resolve_and_public_anonymously(admin_headers, mongo_db):
    response = requests.post(
        f"{API}/questions",
        headers={"Authorization": f"Bearer {QA_TOKEN}"},
        json={"message": "Dúvida com consentimento para publicação.", "allow_anonymous_publication": True},
    )
    assert response.status_code == 200, response.text
    question_id = response.json()["question"]["id"]
    updated = requests.patch(
        f"{API}/admin/business/questions/{question_id}",
        headers=admin_headers,
        json={"reply": "Resposta do plantão.", "resolved": True, "published_anonymously": True},
    )
    assert updated.status_code == 200, updated.text
    public = requests.get(f"{API}/questions/public")
    assert public.status_code == 200, public.text
    row = next(item for item in public.json()["questions"] if item["id"] == question_id)
    assert row["admin_reply"] == "Resposta do plantão."
    assert "user_id" not in row
    mongo_db.questions.delete_one({"id": question_id})


def test_block_revokes_session_and_preserves_history(admin_headers, mongo_db):
    suffix = uuid.uuid4().hex[:12]
    user_id = f"beta_block_{suffix}"
    token = f"beta_block_token_{suffix}"
    mongo_db.users.insert_one(
        {
            "user_id": user_id,
            "email": f"block.{suffix}@medflow.local",
            "name": "Aluno Bloqueio Beta",
            "subscription_plan": "free",
            "access_blocked": False,
            "created_at": "2026-08-06T00:00:00+00:00",
        }
    )
    mongo_db.user_sessions.insert_one(
        {
            "user_id": user_id,
            "session_token": token,
            "expires_at": "2030-01-01T00:00:00+00:00",
            "created_at": "2026-08-06T00:00:00+00:00",
        }
    )
    mongo_db.checkins.insert_one({"id": f"chk_{suffix}", "user_id": user_id})
    blocked = requests.patch(
        f"{API}/admin/business/students/{user_id}",
        headers=admin_headers,
        json={"access_blocked": True, "subscription_plan": "premium"},
    )
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["sessions_revoked"] is True
    denied = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert denied.status_code == 401, denied.text
    assert mongo_db.checkins.count_documents({"user_id": user_id}) == 1
    mongo_db.user_sessions.delete_many({"user_id": user_id})
    mongo_db.checkins.delete_many({"user_id": user_id})
    mongo_db.users.delete_one({"user_id": user_id})