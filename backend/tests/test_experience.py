"""Tests for Iteration A: Experience (progressive disclosure) endpoints."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://medflow-pre-beta.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(email=None, name="Test User"):
    email = email or f"newbie-{uuid.uuid4().hex[:8]}@medflow.dev"
    r = requests.post(f"{API}/auth/dev-login", json={"email": email, "name": name}, timeout=30)
    assert r.status_code == 200, f"dev-login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    assert tok
    return email, tok, {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def fresh_user():
    return _login()


@pytest.fixture
def existing_user():
    # tester@medflow.dev should already have history per test request context
    return _login(email="tester@medflow.dev", name="Tester")


# ── /api/experience/state ─────────────────────────────────────────────
class TestExperienceState:
    def test_fresh_user_state(self, fresh_user):
        _, _, h = fresh_user
        r = requests.get(f"{API}/experience/state", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # required keys
        for k in ("capabilities", "stats", "home_layout", "tour_pending", "minimal_onboarding_done", "catalog", "minimal"):
            assert k in data, f"missing {k}"
        caps = data["capabilities"]
        for slug in ("smart_home", "exam_mode", "checkin", "mental_health_signal", "tutor_ai"):
            assert caps.get(slug) == "enabled", f"{slug} should be enabled"
        assert caps.get("community") == "locked"
        assert caps.get("google_calendar") == "locked"
        # fresh user: no history → home_layout='smart' + tour_pending=False + minimal_done=False
        assert data["minimal_onboarding_done"] is False
        assert data["tour_pending"] is False
        assert data["home_layout"] == "smart"
        # stats zero-ish
        assert data["stats"]["checkins_total"] == 0
        assert data["stats"]["pomodoros_completed"] == 0

    def test_capability_thresholds_locked_for_fresh(self, fresh_user):
        _, _, h = fresh_user
        data = requests.get(f"{API}/experience/state", headers=h, timeout=30).json()
        caps = data["capabilities"]
        assert caps["study_rhythm"] == "locked"
        assert caps["coach_weekly"] == "locked"
        assert caps["analytics"] == "locked"

    def test_catalog_structure(self, fresh_user):
        _, _, h = fresh_user
        data = requests.get(f"{API}/experience/state", headers=h, timeout=30).json()
        cat = data["catalog"]
        assert isinstance(cat, list) and len(cat) >= 5
        for entry in cat:
            assert set(entry.keys()) == {"slug", "label", "description"}


# ── /api/experience/onboarding-minimal ────────────────────────────────
class TestMinimalOnboarding:
    def test_success_persists_and_updates_state(self, fresh_user):
        _, _, h = fresh_user
        payload = {"period_number": 3, "faculty": "FCMMG", "typical_study_min": 45}
        r = requests.post(f"{API}/experience/onboarding-minimal", json=payload, headers=h, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        state = requests.get(f"{API}/experience/state", headers=h, timeout=30).json()
        assert state["minimal_onboarding_done"] is True
        assert state["home_layout"] == "smart"
        assert state["minimal"]["period"] == 3
        assert state["minimal"]["faculty"] == "FCMMG"
        assert state["minimal"]["typical_study_min"] == 45

    @pytest.mark.parametrize("payload", [
        {"period_number": 0, "faculty": "X", "typical_study_min": 30},
        {"period_number": 13, "faculty": "X", "typical_study_min": 30},
        {"period_number": 3, "faculty": "", "typical_study_min": 30},
        {"period_number": 3, "faculty": "X", "typical_study_min": 10},
        {"period_number": 3, "faculty": "X", "typical_study_min": 300},
    ])
    def test_validation_rejects(self, fresh_user, payload):
        _, _, h = fresh_user
        r = requests.post(f"{API}/experience/onboarding-minimal", json=payload, headers=h, timeout=30)
        assert r.status_code == 422, f"expected 422 got {r.status_code} for {payload}"


# ── /api/experience/tour-complete ─────────────────────────────────────
class TestTourComplete:
    def test_smart_choice(self, fresh_user):
        _, _, h = fresh_user
        r = requests.post(f"{API}/experience/tour-complete", json={"home_layout": "smart"}, headers=h, timeout=30)
        assert r.status_code == 200
        assert r.json().get("home_layout") == "smart"
        state = requests.get(f"{API}/experience/state", headers=h, timeout=30).json()
        assert state["home_layout"] == "smart"
        assert state["tour_pending"] is False

    def test_control_center_choice(self, fresh_user):
        _, _, h = fresh_user
        r = requests.post(f"{API}/experience/tour-complete", json={"home_layout": "control_center"}, headers=h, timeout=30)
        assert r.status_code == 200
        state = requests.get(f"{API}/experience/state", headers=h, timeout=30).json()
        assert state["home_layout"] == "control_center"
        assert state["tour_pending"] is False

    def test_invalid_layout_rejected(self, fresh_user):
        _, _, h = fresh_user
        r = requests.post(f"{API}/experience/tour-complete", json={"home_layout": "invalid"}, headers=h, timeout=30)
        assert r.status_code == 422


# ── /api/home/today ───────────────────────────────────────────────────
class TestHomeToday:
    def test_fresh_user_awareness_and_no_observation(self, fresh_user):
        _, _, h = fresh_user
        r = requests.get(f"{API}/home/today", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("date", "recommendation", "observation", "awareness", "stats"):
            assert k in data
        # fresh: checkins==0 → awareness set + observation None
        assert data["awareness"] and "Ainda não conheço" in data["awareness"]
        assert data["observation"] is None
        # fresh: no exam, no block, no checkin today → recommend "Fazer o check-in de hoje"
        rec = data["recommendation"]
        assert rec is not None
        assert rec["kind"] == "checkin"
        assert rec["action_route"] == "/checkin"
        for f in ("title", "subtitle", "duration_min", "action_route", "action_label"):
            assert f in rec

    def test_existing_user_home_today_shape(self, existing_user):
        _, _, h = existing_user
        r = requests.get(f"{API}/home/today", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["recommendation"] is not None
        assert data["stats"]["checkins_total"] >= 0


# ── Auth guard ────────────────────────────────────────────────────────
def test_state_unauthenticated_rejected():
    r = requests.get(f"{API}/experience/state", timeout=15)
    assert r.status_code in (401, 403)
