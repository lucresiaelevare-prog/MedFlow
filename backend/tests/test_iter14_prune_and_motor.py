"""Iter14 backend tests — PODA (routes removed) + MOTOR VISÍVEL (why_signals/why_now).

Covers:
- Removed routes now return 404 (missions, planner/agenda, community, badges).
- Preserved endpoints still 200 (iea, streak, home/today, pomodoro/today,
  tutor/plan, learning/me/mastery, insights/effectiveness-report).
- /home/today.recommendation exposes why_signals (list of {icon,kind,label,value})
  and why_now (str). Signal count/kinds vary with context.
- Seeded chronotype + subject → routine_rotation with chronotype+hour signals.
- Seeded high-stress checkins → saturation_mode with why_now containing
  "sobrecarga" or "consolidar".
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


def _dev_login(email: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/dev-login", json={"email": email, "name": email.split("@")[0]})
    assert r.status_code == 200, f"dev-login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


def _find_user_id(email: str) -> str:
    u = db.users.find_one({"email": email}, {"_id": 0, "user_id": 1, "id": 1})
    assert u, f"user not found for {email}"
    return u.get("user_id") or u.get("id")


@pytest.fixture(scope="module")
def client_fresh():
    email = f"iter14_fresh_{uuid.uuid4().hex[:6]}@medflow.local"
    s = _dev_login(email)
    uid = _find_user_id(email)
    # Clean any residuals just in case
    for col in ("checkins", "user_profiles", "subjects", "recommendation_events"):
        db[col].delete_many({"user_id": uid})
    yield s, uid, email
    for col in ("checkins", "user_profiles", "subjects", "recommendation_events"):
        db[col].delete_many({"user_id": uid})


@pytest.fixture(scope="module")
def client_night_subject():
    email = f"iter14_night_{uuid.uuid4().hex[:6]}@medflow.local"
    s = _dev_login(email)
    uid = _find_user_id(email)
    for col in ("checkins", "user_profiles", "subjects", "recommendation_events", "pomodoro_sessions"):
        db[col].delete_many({"user_id": uid})
    db.user_profiles.update_one(
        {"user_id": uid},
        {"$set": {"user_id": uid, "energy_peak": "noite",
                  "typical_study_min": 45, "sleep_target_h": 8}},
        upsert=True,
    )
    subj_id = f"subj_{uuid.uuid4().hex[:10]}"
    db.subjects.insert_one({
        "id": subj_id, "user_id": uid, "name": "Cardiologia",
        "priority": "alta", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # seed a checkin so we have sleep/mood/stress signals (6/7/4)
    now_iso = datetime.now(timezone.utc).isoformat()
    db.checkins.insert_one({
        "id": f"ck_{uuid.uuid4().hex[:10]}", "user_id": uid,
        "sleep": 6, "mood": 7, "stress": 4,
        "sleep_hours": 6, "created_at": now_iso,
    })
    yield s, uid, subj_id, email
    for col in ("checkins", "user_profiles", "subjects", "recommendation_events", "pomodoro_sessions"):
        db[col].delete_many({"user_id": uid})


@pytest.fixture(scope="module")
def client_saturated():
    email = f"iter14_sat_{uuid.uuid4().hex[:6]}@medflow.local"
    s = _dev_login(email)
    uid = _find_user_id(email)
    for col in ("checkins", "user_profiles", "recommendation_events"):
        db[col].delete_many({"user_id": uid})
    now = datetime.now(timezone.utc)
    for i in range(3):
        db.checkins.insert_one({
            "id": f"ck_{uuid.uuid4().hex[:10]}", "user_id": uid,
            "sleep": 5, "mood": 3, "stress": 9,
            "sleep_hours": 5,
            "created_at": (now - timedelta(hours=i * 6)).isoformat(),
        })
    yield s, uid, email
    for col in ("checkins", "user_profiles", "recommendation_events"):
        db[col].delete_many({"user_id": uid})


# ─── PODA: rotas removidas devem retornar 404 ─────────────────────
class TestPrunedEndpoints:
    @pytest.mark.parametrize("path,method,body", [
        ("/api/community/posts", "GET", None),
        ("/api/missions/today", "GET", None),
        ("/api/missions/generate", "POST", {}),
        ("/api/agenda/blocks", "GET", None),
        ("/api/agenda/blocks", "POST", {"title": "x"}),
        ("/api/badges", "GET", None),
    ])
    def test_pruned_returns_404(self, client_fresh, path, method, body):
        s, _, _ = client_fresh
        if method == "GET":
            r = s.get(f"{BASE_URL}{path}")
        else:
            r = s.post(f"{BASE_URL}{path}", json=body)
        assert r.status_code == 404, f"{method} {path} → {r.status_code} (expected 404)"


# ─── PRESERVAÇÃO: endpoints que devem continuar 200 ───────────────
class TestPreservedEndpoints:
    def test_iea(self, client_fresh):
        s, _, _ = client_fresh
        r = s.get(f"{BASE_URL}/api/iea")
        assert r.status_code == 200
        data = r.json()
        assert "iea" in data and "pillars" in data

    def test_streak(self, client_fresh):
        s, _, _ = client_fresh
        r = s.get(f"{BASE_URL}/api/streak")
        assert r.status_code == 200
        assert "streak" in r.json()

    def test_home_today(self, client_fresh):
        s, _, _ = client_fresh
        r = s.get(f"{BASE_URL}/api/home/today")
        assert r.status_code == 200
        data = r.json()
        assert "recommendation" in data

    def test_pomodoro_today(self, client_fresh):
        s, _, _ = client_fresh
        r = s.get(f"{BASE_URL}/api/pomodoro/today")
        assert r.status_code == 200

    def test_tutor_plan(self, client_fresh):
        s, _, _ = client_fresh
        r = s.post(f"{BASE_URL}/api/tutor/plan",
                   json={"mode": "quick_review", "subject": "Cardiologia", "days": 3, "minutes_per_day": 30})
        assert r.status_code == 200, r.text

    def test_learning_mastery(self, client_fresh):
        s, _, _ = client_fresh
        r = s.get(f"{BASE_URL}/api/learning/me/mastery")
        assert r.status_code == 200

    def test_effectiveness_report(self, client_fresh):
        s, _, _ = client_fresh
        r = s.get(f"{BASE_URL}/api/insights/effectiveness-report")
        assert r.status_code == 200


# ─── MOTOR VISÍVEL ────────────────────────────────────────────────
class TestMotorVisivel:
    def test_fresh_user_has_min_signals(self, client_fresh):
        """User novo sem check-in: pelo menos 2 sinais (clock + brain)."""
        s, _, _ = client_fresh
        r = s.get(f"{BASE_URL}/api/home/today")
        assert r.status_code == 200
        rec = r.json()["recommendation"]
        assert "why_now" in rec and isinstance(rec["why_now"], str) and len(rec["why_now"]) > 0
        assert "why_signals" in rec and isinstance(rec["why_signals"], list)
        signals = rec["why_signals"]
        kinds = {sig["kind"] for sig in signals}
        # Validate structure of each signal
        for sig in signals:
            assert set(sig.keys()) >= {"icon", "kind", "label", "value"}
        assert len(signals) >= 2, f"expected >=2 signals, got {len(signals)}: {kinds}"
        assert "hour" in kinds, f"expected 'hour' (clock) in {kinds}"
        assert "confidence" in kinds, f"expected 'confidence' (brain) in {kinds}"

    def test_checkin_user_has_many_signals(self, client_night_subject):
        """User com check-in seed sleep=6, mood=7, stress=4 + energy_peak=noite:
        pelo menos 5 sinais incluindo sleep/mood/stress/clock/brain."""
        s, _, _, _ = client_night_subject
        r = s.get(f"{BASE_URL}/api/home/today")
        assert r.status_code == 200, r.text
        rec = r.json()["recommendation"]
        signals = rec.get("why_signals") or []
        kinds = {sig["kind"] for sig in signals}
        assert len(signals) >= 5, f"expected >=5, got {len(signals)}: {kinds}"
        for expected in ("sleep", "mood", "stress", "hour", "confidence"):
            assert expected in kinds, f"missing kind '{expected}' in {kinds}"

    def test_chronotype_signal_when_profile_set(self, client_night_subject):
        """energy_peak='noite' + subject → routine_rotation, chronotype signal
        value 'Noite', hour signal value contains 'pico' ou 'fora do pico'."""
        s, _, _, _ = client_night_subject
        r = s.get(f"{BASE_URL}/api/home/today")
        assert r.status_code == 200
        rec = r.json()["recommendation"]
        assert rec.get("rule") == "routine_rotation", f"rule was {rec.get('rule')}"
        signals = rec.get("why_signals") or []
        chrono = next((x for x in signals if x["kind"] == "chronotype"), None)
        hour_sig = next((x for x in signals if x["kind"] == "hour"), None)
        assert chrono is not None, "chronotype signal missing"
        assert chrono["value"] == "Noite", f"chronotype value: {chrono['value']}"
        assert hour_sig is not None
        v = hour_sig["value"].lower()
        assert "pico" in v, f"hour value should mention pico/fora do pico: {v}"
        # why_now: frase específica de routine_rotation deve conter 'matéria com menos foco'
        why_now = rec.get("why_now") or ""
        assert "matéria com menos foco" in why_now, f"why_now: {why_now}"

    def test_saturation_why_now(self, client_saturated):
        """3 checkins com stress=9 → saturation_mode, why_now com 'sobrecarga' ou 'consolidar'."""
        s, _, _ = client_saturated
        r = s.get(f"{BASE_URL}/api/home/today")
        assert r.status_code == 200
        rec = r.json()["recommendation"]
        assert rec.get("rule") == "saturation_mode", f"rule={rec.get('rule')}"
        why_now = (rec.get("why_now") or "").lower()
        assert ("sobrecarga" in why_now) or ("consolidar" in why_now), f"why_now: {why_now}"
