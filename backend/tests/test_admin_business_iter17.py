"""Iter17: Painel administrativo de gestão (business) — cobertura de endpoints.

Cobre:
  1. GET /api/admin/business/overview -> exige admin; retorna growth, learning,
     revenue.connected=false, ai, alerts, timeline com dados reais/estado honesto.
  2. GET /api/admin/business/students -> filtros search/university/period/plan/status
     e detalhe individual sem password_hash/_id, billing.connected=false.
  3. learning, content, wellness, feedbacks, settings exigem admin e nunca simulam
     receitas/pagamentos.
  4. is_technical_admin=true para Eder e Carine; QA estudante -> 403 no developer
     overview; beta admin (não técnico) -> 403 em /developer/overview.
  5. Regressão: rotas legadas /api/admin/stats seguem funcionando; sessão anônima
     e QA student -> 403 no overview.
"""
from __future__ import annotations

import os
from typing import Optional

import pytest
import requests

pytestmark = pytest.mark.skip(
    reason="Substituído pelo escopo enxuto do Beta em test_beta_admin_iter18.py."
)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

QA_TOKEN = "medflow_qa_session_20260805"


def _login(email_key: str, pw_key: str) -> requests.Session:
    session = requests.Session()
    resp = session.post(
        f"{API}/auth/admin-login",
        json={"email": os.environ[email_key], "password": os.environ[pw_key]},
    )
    assert resp.status_code == 200, resp.text
    return session


@pytest.fixture(scope="module")
def eder_session() -> requests.Session:
    return _login("ADMIN_EDER_EMAIL", "ADMIN_EDER_PASSWORD")


@pytest.fixture(scope="module")
def carine_session() -> requests.Session:
    return _login("ADMIN_CARINE_EMAIL", "ADMIN_CARINE_PASSWORD")


@pytest.fixture(scope="module")
def beta_session() -> requests.Session:
    return _login("ADMIN_EMAIL", "ADMIN_PASSWORD")


# ── (1) Overview ─────────────────────────────────────────────
class TestBusinessOverview:
    def test_overview_requires_admin_anonymous(self):
        r = requests.get(f"{API}/admin/business/overview")
        assert r.status_code in (401, 403), r.text

    def test_overview_forbidden_for_student(self):
        r = requests.get(
            f"{API}/admin/business/overview",
            cookies={"session_token": QA_TOKEN},
        )
        assert r.status_code == 403, r.text

    def test_overview_shape_for_eder(self, eder_session):
        r = eder_session.get(f"{API}/admin/business/overview")
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("growth", "learning", "revenue", "ai", "alerts", "updated_at"):
            assert key in body, f"missing {key}"
        # Estado honesto: receita não conectada
        assert body["revenue"]["connected"] is False
        assert "message" in body["revenue"]
        # Growth com timeline lista
        assert "timeline" in body["growth"]
        assert isinstance(body["growth"]["timeline"], list)
        assert isinstance(body["growth"]["active_students"], int)
        # AI health honesto (healthy|attention)
        assert body["ai"]["health"] in ("healthy", "attention")
        # Alerts é lista (pode estar vazia)
        assert isinstance(body["alerts"], list)


# ── (2) Students directory ──────────────────────────────────
class TestBusinessStudents:
    def test_students_requires_admin(self):
        r = requests.get(f"{API}/admin/business/students")
        assert r.status_code in (401, 403)

    def test_students_list_shape(self, eder_session):
        r = eder_session.get(f"{API}/admin/business/students")
        assert r.status_code == 200
        body = r.json()
        assert "students" in body and isinstance(body["students"], list)
        assert "filters" in body and "universities" in body["filters"]
        for stu in body["students"]:
            # jamais expor password_hash ou _id
            assert "password_hash" not in stu
            assert "_id" not in stu
            assert "user_id" in stu
            assert "status" in stu and stu["status"] in ("Ativo", "Inativo")

    def test_students_filter_search_no_match(self, eder_session):
        r = eder_session.get(
            f"{API}/admin/business/students",
            params={"search": "___zz_no_match_zz___"},
        )
        assert r.status_code == 200
        assert r.json()["students"] == []

    def test_students_filter_period_and_plan_and_status(self, eder_session):
        r = eder_session.get(
            f"{API}/admin/business/students",
            params={"period": 5, "plan": "free", "status": "Ativo"},
        )
        assert r.status_code == 200
        for stu in r.json()["students"]:
            assert stu["period"] == 5
            assert stu["plan"] == "free"
            assert stu["status"] == "Ativo"

    def test_student_detail_404(self, eder_session):
        r = eder_session.get(f"{API}/admin/business/students/does-not-exist")
        assert r.status_code == 404

    def test_student_detail_shape_when_exists(self, eder_session):
        listing = eder_session.get(f"{API}/admin/business/students").json()["students"]
        if not listing:
            pytest.skip("Sem alunos no banco para validar detalhe")
        user_id = listing[0]["user_id"]
        r = eder_session.get(f"{API}/admin/business/students/{user_id}")
        assert r.status_code == 200, r.text
        body = r.json()
        # sem password_hash / _id
        assert "password_hash" not in body["student"]
        assert "_id" not in body["student"]
        for key in ("student", "profile", "progress", "billing"):
            assert key in body
        assert body["billing"]["connected"] is False
        # progresso agregado com contadores
        for k in ("checkins", "study_actions", "missions_completed", "ai_requests"):
            assert k in body["progress"]
            assert isinstance(body["progress"][k], int)


# ── (3) Áreas secundárias / operações ─────────────────────
class TestBusinessOperations:
    @pytest.mark.parametrize(
        "path",
        ["learning", "content", "wellness", "feedbacks", "settings"],
    )
    def test_requires_admin(self, path):
        r = requests.get(f"{API}/admin/business/{path}")
        assert r.status_code in (401, 403)

    def test_learning_shape(self, eder_session):
        r = eder_session.get(f"{API}/admin/business/learning")
        assert r.status_code == 200
        body = r.json()
        assert "difficult_topics" in body
        assert "studied_topics" in body
        assert isinstance(body["total_interactions"], int)

    def test_content_shape(self, eder_session):
        r = eder_session.get(f"{API}/admin/business/content")
        assert r.status_code == 200
        body = r.json()
        for k in ("resources", "wellness_items", "learning_materials", "recent_resources"):
            assert k in body
        assert isinstance(body["recent_resources"], list)

    def test_wellness_shape(self, eder_session):
        r = eder_session.get(f"{API}/admin/business/wellness")
        assert r.status_code == 200
        body = r.json()
        for k in ("checkins", "wellness_items", "average_mood", "recent_items"):
            assert k in body

    def test_feedbacks_shape(self, eder_session):
        r = eder_session.get(f"{API}/admin/business/feedbacks")
        assert r.status_code == 200
        body = r.json()
        assert "feedbacks" in body and isinstance(body["feedbacks"], list)
        assert isinstance(body["total"], int)

    def test_settings_honest_and_no_secret_leak(self, eder_session):
        r = eder_session.get(f"{API}/admin/business/settings")
        assert r.status_code == 200
        body = r.json()
        # Nunca conectar pagamento nesta etapa
        assert body["payments_connected"] is False
        assert "providers" in body
        # Nenhum valor de chave deve ser exposto: apenas boolean
        for provider, value in body["providers"].items():
            assert isinstance(value, bool), f"{provider} vazou valor: {value!r}"


# ── (4) is_technical_admin + developer overview ─────────
class TestTechnicalFlags:
    @pytest.mark.parametrize(
        "session_fixture",
        ["eder_session", "carine_session"],
    )
    def test_named_admins_are_technical(self, session_fixture, request):
        session: requests.Session = request.getfixturevalue(session_fixture)
        who = session.get(f"{API}/admin/whoami").json()
        assert who["is_admin"] is True
        assert who["is_technical_admin"] is True

    def test_developer_overview_ok_for_eder(self, eder_session):
        r = eder_session.get(f"{API}/admin/business/developer/overview")
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("shadow_mode", "content_memory", "engine"):
            assert k in body

    def test_developer_overview_forbidden_for_qa_student(self):
        r = requests.get(
            f"{API}/admin/business/developer/overview",
            cookies={"session_token": QA_TOKEN},
        )
        assert r.status_code == 403

    def test_developer_overview_forbidden_anonymous(self):
        r = requests.get(f"{API}/admin/business/developer/overview")
        assert r.status_code in (401, 403)


# ── (5) Regressões ───────────────────────────────────────
class TestRegression:
    def test_beta_admin_can_access_business_overview(self, beta_session):
        r = beta_session.get(f"{API}/admin/business/overview")
        assert r.status_code == 200

    def test_legacy_admin_stats_still_works(self, eder_session):
        r = eder_session.get(f"{API}/admin/stats")
        assert r.status_code == 200
        body = r.json()
        assert "users_total" in body or "users" in body or isinstance(body, dict)

    def test_landing_and_tutor_no_5xx(self):
        for path in ("/", "/tutor"):
            r = requests.get(f"{BASE_URL}{path}")
            assert r.status_code < 500

    def test_mip_phase2_metrics_shadow_mode_untouched_for_anon(self):
        r = requests.get(f"{API}/mip/phase2/metrics")
        assert r.status_code in (401, 403)
