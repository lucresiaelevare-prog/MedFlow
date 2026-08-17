"""Iter19 — cobertura ampliada do escopo Beta simplificado.

Valida:
- Overview de Carine só expõe métricas Beta (sem receita/Stripe/assinaturas).
- Alunos: search, detalhe sem password_hash/_id, PATCH plano/bloqueio + histórico.
- Conteúdo: cada tipo aceito, publish/hide, sem ObjectId nas respostas.
- Plantão: consentimento obrigatório, resposta+resolução, /questions/public sem user_id/email.
- Configurações só retorna platform/ai/emails/logs (sem chaves ou provider names).
- Autorização: Carine admin não-técnica, Eder admin técnico, QA aluno 401/403 em rotas admin.
- MIP phase2 metrics responde para admin e Fase 3 não está ativa.
- Regressão: /api/tutor/*, /api/support/*, /api/dashboard/* sem 5xx.
"""
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


def _admin_login(email_key: str, pwd_key: str) -> dict:
    r = requests.post(
        f"{API}/auth/admin-login",
        json={"email": os.environ[email_key], "password": os.environ[pwd_key]},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


@pytest.fixture(scope="module")
def carine_headers():
    return _admin_login("ADMIN_CARINE_EMAIL", "ADMIN_CARINE_PASSWORD")


@pytest.fixture(scope="module")
def eder_headers():
    return _admin_login("ADMIN_EDER_EMAIL", "ADMIN_EDER_PASSWORD")


@pytest.fixture(scope="module")
def qa_headers():
    return {"Authorization": f"Bearer {QA_TOKEN}"}


# ─── Autorização e flags admin ────────────────────────────────────
def test_whoami_carine_is_admin_not_technical(carine_headers):
    r = requests.get(f"{API}/admin/whoami", headers=carine_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_admin"] is True
    assert data["is_technical_admin"] is False


def test_whoami_eder_is_admin_and_technical(eder_headers):
    r = requests.get(f"{API}/admin/whoami", headers=eder_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_admin"] is True
    assert data["is_technical_admin"] is True


def test_qa_student_forbidden_on_admin_routes(qa_headers):
    for path in [
        "/admin/business/overview",
        "/admin/business/students",
        "/admin/business/content",
        "/admin/business/questions",
        "/admin/business/settings",
        "/admin/business/developer/overview",
    ]:
        r = requests.get(f"{API}{path}", headers=qa_headers)
        assert r.status_code in (401, 403), f"{path} => {r.status_code}"


def test_carine_denied_on_developer_overview(carine_headers):
    r = requests.get(f"{API}/admin/business/developer/overview", headers=carine_headers)
    assert r.status_code == 403, r.text


def test_eder_allowed_on_developer_overview(eder_headers):
    r = requests.get(f"{API}/admin/business/developer/overview", headers=eder_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "shadow_mode" in body and "content_memory" in body and "engine" in body


# ─── Overview Beta sem receita ────────────────────────────────────
def test_overview_shape_beta_only(carine_headers):
    r = requests.get(f"{API}/admin/business/overview", headers=carine_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    growth = body["growth"]
    assert {"total_students", "active_students", "new_students_30d", "new_students_today", "plans"} <= set(growth)
    assert set(growth["plans"].keys()) == {"free", "premium"}
    assert body["revenue"]["connected"] is False
    text_blob = str(body).lower()
    # Ensure no Stripe/subscription/pricing simulation
    for banned in ["stripe", "subscription_id", "mrr", "arr"]:
        assert banned not in text_blob, f"campo banido {banned!r} no overview"
    assert "ai" in body and "alerts" in body and "learning" in body


# ─── Configurações reduzidas ──────────────────────────────────────
def test_settings_only_beta_sections(carine_headers):
    r = requests.get(f"{API}/admin/business/settings", headers=carine_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"platform", "ai", "emails", "logs"}
    # AI section must not leak keys/provider names
    ai_blob = str(body["ai"]).lower()
    for banned in ["sk-", "gsk_", "openai", "groq", "hf_", "pubmed"]:
        assert banned not in ai_blob, f"vazamento {banned!r} em settings.ai"
    assert isinstance(body["logs"]["sessions_last_24h"], int)


# ─── Alunos: busca + detalhe seguro + patch plano+bloqueio ───────
def test_students_listing_filters_and_detail(carine_headers, mongo_db):
    r = requests.get(f"{API}/admin/business/students", headers=carine_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "students" in body and "filters" in body
    for row in body["students"]:
        assert "password_hash" not in row
        assert "_id" not in row
    # Empty search returns something (>=0). Search with impossible substring returns []
    empty = requests.get(
        f"{API}/admin/business/students?search=zzzzzzz_no_match_zzz",
        headers=carine_headers,
    )
    assert empty.status_code == 200
    assert empty.json()["students"] == []


def test_student_plan_change_and_block_flow(carine_headers, mongo_db):
    suffix = uuid.uuid4().hex[:10]
    user_id = f"beta_scope_{suffix}"
    token = f"beta_scope_tok_{suffix}"
    mongo_db.users.insert_one(
        {
            "user_id": user_id,
            "email": f"scope.{suffix}@medflow.local",
            "name": "Aluno Scope Beta",
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
    mongo_db.checkins.insert_one({"id": f"chk_{suffix}", "user_id": user_id, "mood": 3})
    try:
        # Detail: safe fields only
        d = requests.get(f"{API}/admin/business/students/{user_id}", headers=carine_headers)
        assert d.status_code == 200, d.text
        student = d.json()["student"]
        assert "password_hash" not in student and "_id" not in student
        assert d.json()["billing"]["connected"] is False

        # Upgrade to premium
        up = requests.patch(
            f"{API}/admin/business/students/{user_id}",
            headers=carine_headers,
            json={"subscription_plan": "premium"},
        )
        assert up.status_code == 200
        assert up.json()["student"]["subscription_plan"] == "premium"
        assert up.json()["sessions_revoked"] is False

        # Token still valid after mere plan change
        me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200, me.text

        # Block
        bl = requests.patch(
            f"{API}/admin/business/students/{user_id}",
            headers=carine_headers,
            json={"access_blocked": True},
        )
        assert bl.status_code == 200
        assert bl.json()["sessions_revoked"] is True
        denied = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert denied.status_code == 401
        # History preserved
        assert mongo_db.checkins.count_documents({"user_id": user_id}) == 1

        # Empty patch -> 400
        empty = requests.patch(
            f"{API}/admin/business/students/{user_id}",
            headers=carine_headers,
            json={},
        )
        assert empty.status_code == 400

        # Non-existent -> 404
        nf = requests.patch(
            f"{API}/admin/business/students/does_not_exist_{suffix}",
            headers=carine_headers,
            json={"subscription_plan": "premium"},
        )
        assert nf.status_code == 404
    finally:
        mongo_db.user_sessions.delete_many({"user_id": user_id})
        mongo_db.checkins.delete_many({"user_id": user_id})
        mongo_db.users.delete_one({"user_id": user_id})


# ─── Conteúdo: cada tipo aceito ───────────────────────────────────
@pytest.mark.parametrize("content_type", ["course", "module", "lesson", "simulation", "pdf"])
def test_content_create_each_type(carine_headers, mongo_db, content_type):
    r = requests.post(
        f"{API}/admin/business/content",
        headers=carine_headers,
        json={
            "title": f"Teste {content_type} {uuid.uuid4().hex[:6]}",
            "content_type": content_type,
            "published": True,
        },
    )
    assert r.status_code == 200, r.text
    item = r.json()["item"]
    assert item["content_type"] == content_type
    assert "_id" not in item
    content_id = item["id"]
    listing = requests.get(f"{API}/admin/business/content", headers=carine_headers)
    assert listing.status_code == 200
    ids = [it["id"] for it in listing.json()["items"]]
    assert content_id in ids
    hide = requests.patch(
        f"{API}/admin/business/content/{content_id}/visibility",
        headers=carine_headers,
        json={"published": False},
    )
    assert hide.status_code == 200
    assert hide.json()["published"] is False
    mongo_db.cms_resources.delete_one({"id": content_id})


def test_content_visibility_invalid_id(carine_headers):
    r = requests.patch(
        f"{API}/admin/business/content/does_not_exist/visibility",
        headers=carine_headers,
        json={"published": True},
    )
    assert r.status_code == 404


# ─── Plantão: consent flow ────────────────────────────────────────
def test_public_questions_never_exposes_user_id(carine_headers, mongo_db, qa_headers):
    # Create with consent + publish anonymously
    r = requests.post(
        f"{API}/questions",
        headers=qa_headers,
        json={"message": "Public consent QA duvida.", "allow_anonymous_publication": True},
    )
    assert r.status_code == 200, r.text
    qid = r.json()["question"]["id"]
    assert "user_id" not in r.json()["question"]
    upd = requests.patch(
        f"{API}/admin/business/questions/{qid}",
        headers=carine_headers,
        json={"reply": "Resposta pública.", "resolved": True, "published_anonymously": True},
    )
    assert upd.status_code == 200
    # Public endpoint (no auth)
    pub = requests.get(f"{API}/questions/public")
    assert pub.status_code == 200
    row = next((q for q in pub.json()["questions"] if q["id"] == qid), None)
    assert row is not None
    forbidden_keys = {"user_id", "email", "name"}
    assert not (set(row.keys()) & forbidden_keys), f"Vazamento em pública: {row.keys()}"
    mongo_db.questions.delete_one({"id": qid})


def test_question_publish_denied_without_consent(carine_headers, mongo_db, qa_headers):
    r = requests.post(
        f"{API}/questions",
        headers=qa_headers,
        json={"message": "Sem consent duvida.", "allow_anonymous_publication": False},
    )
    qid = r.json()["question"]["id"]
    deny = requests.patch(
        f"{API}/admin/business/questions/{qid}",
        headers=carine_headers,
        json={"published_anonymously": True},
    )
    assert deny.status_code == 400
    mongo_db.questions.delete_one({"id": qid})


# ─── MIP: phase2 metrics ainda responde, Fase 3 desabilitada ─────
def test_mip_phase2_metrics_admin_ok(eder_headers):
    r = requests.get(f"{API}/mip/phase2/metrics", headers=eder_headers)
    assert r.status_code == 200, r.text


def test_mip_phase2_metrics_anonymous_blocked():
    r = requests.get(f"{API}/mip/phase2/metrics")
    assert r.status_code in (401, 403)


def test_no_phase3_endpoint():
    # Fase 3 não deve estar ativa (endpoint 404 ou 401 antes de auth)
    r = requests.get(f"{API}/mip/phase3/metrics")
    assert r.status_code in (401, 403, 404)


# ─── Regressão: fluxos estudantis sem 5xx ─────────────────────────
def test_student_dashboard_and_support_no_5xx(qa_headers):
    for path in [
        "/dashboard/overview",
        "/dashboard/today",
        "/support/messages",
        "/tutor/history",
    ]:
        r = requests.get(f"{API}{path}", headers=qa_headers)
        assert r.status_code < 500, f"{path} => {r.status_code} {r.text[:120]}"
