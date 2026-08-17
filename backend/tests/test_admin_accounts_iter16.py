"""Iter16: Verifica contas administrativas Eder/Carine com senha Med@123 e regressões.

Cobertura:
  1. POST /api/auth/admin-login com Med@123 -> 200 + is_admin True (Eder, Carine).
  2. Senha antiga 54321 -> 401 para ambas.
  3. GET /api/admin/whoami com sessão admin -> is_admin True; QA student -> is_admin False.
  4. Estudante QA acessando rota admin protegida -> 403.
  5. Beta admin continua funcional (regressão).
  6. Seed idempotente: user_id não muda, e-mails não duplicam, password_hash bcrypt não vaza nas respostas.
  7. Regressão: /api/mip/phase2/metrics para QA -> 403 (sem 5xx). Landing / -> 200.
"""
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

NAMED_ADMINS = [
    ("ADMIN_EDER_EMAIL", "ADMIN_EDER_PASSWORD", "Eder"),
    ("ADMIN_CARINE_EMAIL", "ADMIN_CARINE_PASSWORD", "Carine"),
]


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


# ── (1) Login sucesso + (6) e-mail único e password_hash oculto ──
@pytest.mark.parametrize(("email_key", "pw_key", "expected_name"), NAMED_ADMINS)
def test_admin_login_success_and_no_hash_leak(email_key, pw_key, expected_name, mongo_db):
    email = os.environ[email_key]
    pw = os.environ[pw_key]

    # verifica unicidade do e-mail (idempotência do seed)
    docs = list(mongo_db.users.find({"email": email}))
    assert len(docs) == 1, f"esperado 1 doc para {email}, achado {len(docs)}"

    resp = requests.post(f"{API}/auth/admin-login", json={"email": email, "password": pw})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["email"] == email
    assert body["user"]["is_admin"] is True
    assert body["user"]["name"] == expected_name
    # password_hash JAMAIS deve aparecer na resposta
    assert "password_hash" not in body["user"]
    # cookie httpOnly emitido
    assert resp.cookies.get("session_token") is not None


# ── (2) Senha antiga 54321 rejeitada ──
@pytest.mark.parametrize("email_key", ["ADMIN_EDER_EMAIL", "ADMIN_CARINE_EMAIL"])
def test_old_password_54321_is_rejected(email_key):
    email = os.environ[email_key]
    resp = requests.post(f"{API}/auth/admin-login", json={"email": email, "password": "54321"})
    assert resp.status_code == 401, resp.text


# ── (3) whoami com sessão admin -> True ──
@pytest.mark.parametrize(("email_key", "pw_key"), [(k[0], k[1]) for k in NAMED_ADMINS])
def test_whoami_admin_true(email_key, pw_key):
    session = requests.Session()
    login = session.post(
        f"{API}/auth/admin-login",
        json={"email": os.environ[email_key], "password": os.environ[pw_key]},
    )
    assert login.status_code == 200
    who = session.get(f"{API}/admin/whoami")
    assert who.status_code == 200
    assert who.json()["is_admin"] is True


# ── (3) QA student whoami -> False ──
def test_qa_student_whoami_is_not_admin():
    resp = requests.get(
        f"{API}/admin/whoami",
        cookies={"session_token": QA_TOKEN},
    )
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is False


# ── (4) QA student em rota admin protegida -> 403/401 ──
def test_qa_student_forbidden_on_admin_route():
    # /api/mip/phase2/metrics é uma rota administrativa real
    resp = requests.get(
        f"{API}/mip/phase2/metrics",
        cookies={"session_token": QA_TOKEN},
    )
    assert resp.status_code in (401, 403), resp.text


# ── (5) Beta admin continua funcional (regressão) ──
def test_beta_admin_login_still_works():
    email = os.environ["ADMIN_EMAIL"]
    pw = os.environ["ADMIN_PASSWORD"]
    resp = requests.post(f"{API}/auth/admin-login", json={"email": email, "password": pw})
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["is_admin"] is True


# ── (6) user_id estável entre logins ──
@pytest.mark.parametrize(("email_key", "pw_key"), [(k[0], k[1]) for k in NAMED_ADMINS])
def test_user_id_stable_across_logins(email_key, pw_key, mongo_db):
    email = os.environ[email_key]
    pw = os.environ[pw_key]
    doc = mongo_db.users.find_one({"email": email}, {"_id": 0})
    assert doc is not None
    uid_db = doc["user_id"]
    for _ in range(2):
        r = requests.post(f"{API}/auth/admin-login", json={"email": email, "password": pw})
        assert r.status_code == 200
        assert r.json()["user"]["user_id"] == uid_db


# ── (7) regressão: landing + tutor não retornam 5xx ──
def test_landing_and_tutor_not_5xx():
    for path in ("/", "/tutor"):
        r = requests.get(f"{BASE_URL}{path}")
        assert r.status_code < 500, f"{path} -> {r.status_code}"


# ── (7) regressão mip metrics: sem sessão -> 401/403 (sem 5xx) ──
def test_mip_metrics_requires_admin_no_5xx():
    r = requests.get(f"{API}/mip/phase2/metrics")
    assert r.status_code in (401, 403), r.text
