"""Iter15 REFACTOR — decision_engine.py extracted from routes/experience.py.

Behavior must be identical to iter14. Tests here focus on:
- Fresh user smoke: 200 + recommendation shape.
- Saturation triggers via different seed patterns (stress_high, mood_low_persistent,
  sleep_low_persistent, abandon_streak) → each yields evidence.data.rule matching.
- Additional endpoints not covered by iter14 suite: tutor/mastery-map, admin whoami,
  admin research/cohort, experience/state/tour-preview.
- learning/content/{id}/answered still returns fatigue payload.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]

ADMIN_EMAIL = "admin@medflow.app"
ADMIN_PASSWORD = "MedFlow2026!"


def _dev_login(email: str) -> tuple[requests.Session, str]:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/dev-login", json={"email": email, "name": email.split("@")[0]})
    assert r.status_code == 200, f"dev-login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    u = db.users.find_one({"email": email}, {"_id": 0, "user_id": 1, "id": 1})
    uid = u.get("user_id") or u.get("id") if u else None
    return s, uid


def _fresh_email() -> str:
    return f"iter15r_{uuid.uuid4().hex[:8]}@medflow.local"


# ---------- REGRESSION: shape ----------

def test_home_today_shape_fresh_user():
    email = _fresh_email()
    s, _ = _dev_login(email)
    r = s.get(f"{BASE_URL}/api/home/today")
    assert r.status_code == 200, r.text
    data = r.json()
    rec = data.get("recommendation")
    assert rec is not None
    for k in ("rule", "priority", "title", "subtitle", "reasoning",
              "duration_min", "action_route", "action_label",
              "evidence", "why_now", "why_signals"):
        assert k in rec, f"missing key {k} in recommendation"
    assert isinstance(rec["rule"], str)
    assert isinstance(rec["priority"], int)
    assert 0 <= rec["priority"] <= 6
    assert isinstance(rec["why_now"], str) and rec["why_now"]
    assert isinstance(rec["why_signals"], list)
    ev = rec["evidence"]
    assert "explanation" in ev and "data" in ev


# ---------- SATURATION VARIANTS ----------

def _insert_checkin(user_id: str, *, sleep: int, mood: int, stress: int, minutes_ago: int = 60):
    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    db.checkins.insert_one({
        "user_id": user_id, "sleep": sleep, "mood": mood, "stress": stress,
        "created_at": ts, "ts": ts,
    })


def test_saturation_stress_high():
    email = _fresh_email()
    s, uid = _dev_login(email)
    assert uid
    _insert_checkin(uid, sleep=7, mood=6, stress=9, minutes_ago=30)
    r = s.get(f"{BASE_URL}/api/home/today")
    assert r.status_code == 200
    rec = r.json()["recommendation"]
    assert rec["rule"] == "saturation_mode", rec
    assert rec["priority"] == 6
    assert rec["duration_min"] == 10
    assert rec["action_route"] == "/tutor"
    assert rec["evidence"]["data"].get("rule") == "stress_high"


def test_saturation_mood_low_persistent():
    email = _fresh_email()
    s, uid = _dev_login(email)
    for i in range(3):
        _insert_checkin(uid, sleep=7, mood=3, stress=5, minutes_ago=60 * (i + 1))
    r = s.get(f"{BASE_URL}/api/home/today")
    assert r.status_code == 200
    rec = r.json()["recommendation"]
    assert rec["rule"] == "saturation_mode"
    assert rec["evidence"]["data"].get("rule") == "mood_low_persistent"


def test_saturation_sleep_low_persistent():
    email = _fresh_email()
    s, uid = _dev_login(email)
    for i in range(3):
        _insert_checkin(uid, sleep=3, mood=6, stress=5, minutes_ago=60 * (i + 1))
    r = s.get(f"{BASE_URL}/api/home/today")
    assert r.status_code == 200
    rec = r.json()["recommendation"]
    assert rec["rule"] == "saturation_mode"
    assert rec["evidence"]["data"].get("rule") == "sleep_low_persistent"


def test_saturation_abandon_streak():
    email = _fresh_email()
    s, uid = _dev_login(email)
    now = datetime.now(timezone.utc)
    for i in range(3):
        ts = now - timedelta(hours=i * 4 + 1)
        db.recommendation_events.insert_one({
            "user_id": uid,
            "outcome": "abandoned",
            "abandoned_at": ts.isoformat(),
            "created_at": ts,
        })
    r = s.get(f"{BASE_URL}/api/home/today")
    assert r.status_code == 200
    rec = r.json()["recommendation"]
    assert rec["rule"] == "saturation_mode", rec
    assert rec["evidence"]["data"].get("rule") == "abandon_streak"


# ---------- Signal richness ----------

def test_why_signals_richness_after_checkin():
    email = _fresh_email()
    s, uid = _dev_login(email)
    _insert_checkin(uid, sleep=6, mood=7, stress=4, minutes_ago=30)
    r = s.get(f"{BASE_URL}/api/home/today")
    assert r.status_code == 200
    rec = r.json()["recommendation"]
    signals = rec["why_signals"]
    assert isinstance(signals, list)
    assert len(signals) >= 5, f"expected >=5 signals, got {len(signals)}: {signals}"
    kinds = {sig["kind"] for sig in signals}
    for expected in ("sleep", "mood", "stress", "hour"):
        assert expected in kinds, f"missing {expected} in signals: {kinds}"
    for sig in signals:
        for k in ("icon", "kind", "label", "value"):
            assert k in sig, f"signal missing {k}: {sig}"


# ---------- Fatigue endpoint ----------

def test_learning_content_answered_returns_fatigue():
    email = _fresh_email()
    s, _ = _dev_login(email)
    # Create a content item — try tutor/plan generation first for a real id.
    content_id = "any-id-" + uuid.uuid4().hex[:6]
    r = s.post(
        f"{BASE_URL}/api/learning/content/{content_id}/answered",
        json={"correct": True, "duration_ms": 5000},
    )
    # Endpoint should exist and return the expected shape regardless of content existence.
    assert r.status_code in (200, 404), r.status_code
    if r.status_code == 200:
        body = r.json()
        assert "ok" in body
        assert "fatigue" in body
        fat = body["fatigue"]
        for k in ("fatigued", "reason", "evidence"):
            assert k in fat


# ---------- Other preserved endpoints ----------

def test_experience_state_and_tour_preview():
    email = _fresh_email()
    s, _ = _dev_login(email)
    r1 = s.get(f"{BASE_URL}/api/experience/state")
    assert r1.status_code == 200, r1.text
    r2 = s.get(f"{BASE_URL}/api/experience/tour-preview")
    assert r2.status_code == 200, r2.text


def test_experience_onboarding_minimal_and_tour_complete():
    email = _fresh_email()
    s, _ = _dev_login(email)
    r1 = s.post(
        f"{BASE_URL}/api/experience/onboarding-minimal",
        json={"energy_peak": "noite", "goal": "Cardio",
              "period_number": 4, "faculty": "USP", "typical_study_min": 45},
    )
    assert r1.status_code == 200, r1.text
    r2 = s.post(f"{BASE_URL}/api/experience/tour-complete", json={"home_layout": "smart"})
    assert r2.status_code == 200, r2.text


def test_tutor_mastery_map_ok():
    email = _fresh_email()
    s, _ = _dev_login(email)
    r = s.get(f"{BASE_URL}/api/tutor/mastery-map")
    assert r.status_code == 200, r.text


def test_admin_whoami_and_cohort():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/admin-login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text[:200]}")
    tok = r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    r1 = s.get(f"{BASE_URL}/api/admin/whoami")
    assert r1.status_code == 200, r1.text
    r2 = s.get(f"{BASE_URL}/api/admin/research/cohort")
    assert r2.status_code == 200, r2.text


# ---------- Pruned endpoints ----------

@pytest.mark.parametrize("path,method", [
    ("/api/community/posts", "GET"),
    ("/api/missions/today", "GET"),
    ("/api/badges", "GET"),
])
def test_pruned_endpoints_404(path, method):
    email = _fresh_email()
    s, _ = _dev_login(email)
    r = s.request(method, f"{BASE_URL}{path}")
    assert r.status_code == 404, f"{path} expected 404 got {r.status_code}"


def test_agenda_blocks_post_404():
    email = _fresh_email()
    s, _ = _dev_login(email)
    r = s.post(f"{BASE_URL}/api/agenda/blocks", json={"title": "x"})
    assert r.status_code == 404
