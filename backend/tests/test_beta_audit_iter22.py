"""Iter22 audit: idempotência de lifecycle, resíduos de teste, ausência de PII/tokens."""
from __future__ import annotations

import os
import re
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
QA_TOKEN = "medflow_qa_session_20260805"
QA_HEADERS = {"Authorization": f"Bearer {QA_TOKEN}"}


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(
        f"{API}/auth/admin-login",
        json={
            "email": os.environ["ADMIN_CARINE_EMAIL"],
            "password": os.environ["ADMIN_CARINE_PASSWORD"],
        },
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def test_no_leftover_test_documents(mongo_db):
    """Coleções conhecidas não podem conter resíduos de iterações anteriores."""
    leftovers = {}
    rec_leftovers = list(
        mongo_db.recommendation_events.find(
            {"id": {"$regex": "^(rec_observe_|rec_report_)"}}, {"_id": 0, "id": 1}
        )
    )
    if rec_leftovers:
        leftovers["recommendation_events"] = [d["id"] for d in rec_leftovers]
    conf_leftovers = list(
        mongo_db.confidence_shadow_events.find(
            {"event_id": {"$regex": "^(sr_confidence_|conf_report_)"}}, {"_id": 0, "event_id": 1}
        )
    )
    if conf_leftovers:
        leftovers["confidence_shadow_events"] = [d["event_id"] for d in conf_leftovers]
    review_leftovers = list(
        mongo_db.smart_reviews.find(
            {"id": {"$regex": "^sr_confidence_"}}, {"_id": 0, "id": 1}
        )
    )
    if review_leftovers:
        leftovers["smart_reviews"] = [d["id"] for d in review_leftovers]
    assert not leftovers, f"Resíduos de teste encontrados: {leftovers}"


def test_recommendation_lifecycle_is_idempotent(mongo_db):
    """POSTs repetidos de shown/why-expanded/started/completed devem ser idempotentes."""
    user = mongo_db.user_sessions.find_one({"session_token": QA_TOKEN}, {"_id": 0})
    assert user is not None
    rec_id = f"rec_observe_{uuid.uuid4().hex[:12]}"
    mongo_db.recommendation_events.insert_one(
        {
            "id": rec_id,
            "user_id": user["user_id"],
            "shown_at": None,
            "why_expanded_at": None,
            "started_at": None,
            "completed_at": None,
            "abandoned_at": None,
            "outcome": None,
            "recommended_at": "2026-08-06T00:00:00+00:00",
        }
    )
    try:
        for endpoint in ("shown", "why-expanded", "started"):
            r1 = requests.post(f"{API}/recommendations/{rec_id}/{endpoint}", headers=QA_HEADERS)
            r2 = requests.post(f"{API}/recommendations/{rec_id}/{endpoint}", headers=QA_HEADERS)
            assert r1.status_code == 202
            assert r2.status_code == 202
        # após 2x cada endpoint, ainda deve existir apenas 1 documento
        count = mongo_db.recommendation_events.count_documents({"id": rec_id})
        assert count == 1, f"Duplicidade detectada: {count} documentos"
        doc = mongo_db.recommendation_events.find_one({"id": rec_id}, {"_id": 0})
        first_shown = doc["shown_at"]
        # POST extra de shown NÃO deve sobrescrever timestamp original
        r3 = requests.post(f"{API}/recommendations/{rec_id}/shown", headers=QA_HEADERS)
        assert r3.status_code == 202
        doc2 = mongo_db.recommendation_events.find_one({"id": rec_id}, {"_id": 0})
        assert doc2["shown_at"] == first_shown, "shown_at foi sobrescrito em POST repetido"
    finally:
        mongo_db.recommendation_events.delete_one({"id": rec_id})


def test_beta_intelligence_never_leaks_pii_or_tokens(admin_headers):
    r = requests.get(f"{API}/admin/business/beta-intelligence", headers=admin_headers)
    assert r.status_code == 200
    body = r.text
    for banned in ("user_id", "email", "session_token", "@medflow.local", "medflow_qa_session_"):
        assert banned not in body, f"PII/token vazado: {banned}"
    # nenhum ObjectId residual
    assert "_id" not in r.json()


def test_confidence_events_are_always_shadow(mongo_db, admin_headers):
    """Todos os confidence_shadow_events devem ter shadow_mode=True."""
    non_shadow = mongo_db.confidence_shadow_events.count_documents({"shadow_mode": {"$ne": True}})
    assert non_shadow == 0, f"{non_shadow} eventos com shadow_mode != True"


def test_beta_intelligence_flags_insufficient_sample(admin_headers):
    """Sample size < 10 deve continuar exposto para leitura crítica; não deve mascarar como 'conclusão'."""
    r = requests.get(f"{API}/admin/business/beta-intelligence", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    # observation_only garante que nenhum campo indica ação automatizada
    assert data["observation_only"] is True
    # sample_size deve ser um inteiro exposto (para a leitora julgar suficiência)
    assert isinstance(data["confidence"]["sample_size"], int)


def test_admin_business_overview_updated_at_is_iso(admin_headers):
    r = requests.get(f"{API}/admin/business/overview", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "updated_at" in data
    # ISO8601 básico
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", str(data["updated_at"]))


# Regressão: MIP phase2 e tutor/preceptor rotas conhecidas não retornam 5xx (com sessão QA quando aplicável)
@pytest.mark.parametrize(
    "path",
    [
        "/mip/phase2/metrics",
        "/tutor/state",
        "/preceptor/summary",
    ],
)
def test_extra_regression_no_5xx(path):
    r = requests.get(f"{API}{path}", headers=QA_HEADERS)
    assert r.status_code < 500, f"{path} -> {r.status_code}: {r.text[:200]}"
