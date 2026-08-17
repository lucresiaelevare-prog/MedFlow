"""MedFlow — Iteration 13: 4 strategic differentials.
Tests: energy/chronotype engine + optimal_window, saturation, effectiveness-report, fatigue.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env", override=False)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]


def _iso(dt=None):
    return (dt or datetime.now(timezone.utc)).isoformat()


def _dev_login(suffix: str) -> tuple[str, str]:
    """Create isolated dev user, return (user_id, session_token)."""
    email = f"test_iter13_{suffix}_{uuid.uuid4().hex[:8]}@medflow.local"
    r = requests.post(
        f"{BASE_URL}/api/auth/dev-login",
        json={"email": email, "name": "Iter13 Tester"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    return data["user"]["user_id"], data["session_token"]


def _client(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


def _local_bucket_now() -> str:
    h = (datetime.now(timezone.utc).hour - 3) % 24
    if 5 <= h < 12:
        return "manha"
    if 12 <= h < 18:
        return "tarde"
    if 18 <= h < 23:
        return "noite"
    return "madrugada"


def _cleanup(user_id: str):
    for col in ("checkins", "user_profiles", "subjects", "recommendation_events",
                "student_content_events", "pomodoro_sessions"):
        _db[col].delete_many({"user_id": user_id})


# ─── (1) Energy peak / optimal_window ────────────────────────────
class TestOptimalWindow:
    def test_energy_peak_returns_optimal_window(self):
        uid, tok = _dev_login("peak")
        try:
            # Set profile with energy_peak matching current local bucket → is_peak True
            peak = _local_bucket_now()
            if peak == "madrugada":
                peak = "noite"  # optimal_window_label only supports manha/tarde/noite
            _db.user_profiles.update_one(
                {"user_id": uid},
                {"$set": {"user_id": uid, "energy_peak": peak,
                          "target_sleep_hours": 7,
                          "typical_study_min": 45,
                          "minimal_onboarding_done": True}},
                upsert=True,
            )
            # Insert a checkin today so P2 (checkin_pending) is skipped and we
            # reach P1 (routine_rotation) where optimal_window is emitted.
            _db.checkins.insert_one({
                "user_id": uid, "sleep": 7, "mood": 7, "stress": 4, "energy": 6,
                "created_at": _iso(),
            })
            # Ensure subject exists for routine_rotation to fire (P1)
            _db.subjects.insert_one({
                "id": f"sub_{uuid.uuid4().hex[:8]}",
                "user_id": uid, "name": "Anatomia", "priority": "media",
                "created_at": _iso(),
            })
            r = _client(tok).get(f"{BASE_URL}/api/home/today")
            assert r.status_code == 200, r.text
            rec = r.json()["recommendation"]
            # Must contain optimal_window key when peak is set
            assert "optimal_window" in rec, rec
            assert rec["optimal_window"] is not None
            assert isinstance(rec["optimal_window"], str)
            assert "Melhor entre" in rec["optimal_window"]
            data = rec.get("evidence", {}).get("data", {})
            assert "hour_bucket_now" in data
            assert "peak_bucket" in data
            assert "is_peak" in data
            assert data["peak_bucket"] == peak
            # sleep_debt_h optional only in routine_rotation branch
            if rec["rule"] == "routine_rotation":
                assert "sleep_debt_h" in data
        finally:
            _cleanup(uid)

    def test_no_peak_no_window(self):
        uid, tok = _dev_login("nopeak")
        try:
            _db.user_profiles.update_one(
                {"user_id": uid},
                {"$set": {"user_id": uid, "typical_study_min": 45,
                          "minimal_onboarding_done": True}},
                upsert=True,
            )
            r = _client(tok).get(f"{BASE_URL}/api/home/today")
            assert r.status_code == 200
            rec = r.json()["recommendation"]
            # optimal_window may be absent OR null (both acceptable per briefing)
            assert rec.get("optimal_window") in (None, "", ) or "optimal_window" not in rec
        finally:
            _cleanup(uid)


# ─── (2) Saturation Mode ────────────────────────────────────────
class TestSaturationMode:
    def _assert_saturation(self, tok: str, sub_rule: str):
        r = _client(tok).get(f"{BASE_URL}/api/home/today")
        assert r.status_code == 200, r.text
        rec = r.json()["recommendation"]
        assert rec["rule"] == "saturation_mode", rec
        assert rec["priority"] == 6
        assert rec["duration_min"] == 10
        assert rec["title"] == "Hoje vale uma pequena vitória"
        assert rec["evidence"]["data"].get("rule") == sub_rule

    def test_stress_high(self):
        uid, tok = _dev_login("sat_stress")
        try:
            _db.checkins.insert_one({
                "user_id": uid, "stress": 9, "mood": 5, "sleep": 6,
                "created_at": _iso(),
            })
            self._assert_saturation(tok, "stress_high")
        finally:
            _cleanup(uid)

    def test_mood_low_persistent(self):
        uid, tok = _dev_login("sat_mood")
        try:
            now = datetime.now(timezone.utc)
            for i in range(3):
                _db.checkins.insert_one({
                    "user_id": uid, "mood": 3, "sleep": 6, "stress": 3,
                    "created_at": _iso(now - timedelta(minutes=i)),
                })
            self._assert_saturation(tok, "mood_low_persistent")
        finally:
            _cleanup(uid)

    def test_sleep_low_persistent(self):
        uid, tok = _dev_login("sat_sleep")
        try:
            now = datetime.now(timezone.utc)
            for i in range(3):
                _db.checkins.insert_one({
                    "user_id": uid, "mood": 5, "sleep": 3, "stress": 3,
                    "created_at": _iso(now - timedelta(minutes=i)),
                })
            self._assert_saturation(tok, "sleep_low_persistent")
        finally:
            _cleanup(uid)

    def test_abandon_streak(self):
        uid, tok = _dev_login("sat_aband")
        try:
            now = datetime.now(timezone.utc)
            for i in range(3):
                _db.recommendation_events.insert_one({
                    "user_id": uid, "outcome": "abandoned",
                    "abandoned_at": _iso(now - timedelta(hours=i + 1)),
                    "recommended_at": _iso(now - timedelta(hours=i + 2)),
                })
            self._assert_saturation(tok, "abandon_streak")
        finally:
            _cleanup(uid)


# ─── (3) Effectiveness Report ────────────────────────────────────
class TestEffectivenessReport:
    def test_empty_user(self):
        uid, tok = _dev_login("eff_empty")
        try:
            r = _client(tok).get(f"{BASE_URL}/api/insights/effectiveness-report")
            assert r.status_code == 200, r.text
            data = r.json()
            for k in ("week_start", "prev_week_start", "current", "previous",
                      "trends", "best_disciplines", "worst_disciplines", "empty"):
                assert k in data, f"missing {k}"
            assert data["empty"] is True
        finally:
            _cleanup(uid)

    def test_with_history(self):
        uid, tok = _dev_login("eff_hist")
        try:
            now = datetime.now(timezone.utc)
            # Current week: sleep low days + rec events
            for i in range(3):
                _db.checkins.insert_one({
                    "user_id": uid, "mood": 4, "sleep_hours": 4.5, "stress": 4,
                    "created_at": _iso(now - timedelta(hours=i)),
                })
            for i in range(4):
                _db.recommendation_events.insert_one({
                    "user_id": uid,
                    "recommended_at": _iso(now - timedelta(hours=i)),
                    "shown_at": _iso(now - timedelta(hours=i)),
                    "outcome": "completed" if i < 2 else "shown",
                })
            _db.pomodoro_sessions.insert_one({
                "user_id": uid, "status": "completed",
                "focused_minutes": 45,
                "created_at": _iso(now - timedelta(hours=1)),
                "date": now.date().isoformat(),
            })
            r = _client(tok).get(f"{BASE_URL}/api/insights/effectiveness-report")
            assert r.status_code == 200, r.text
            data = r.json()
            cur = data["current"]
            assert cur["rec_shown"] >= 4
            assert cur["focus_minutes"] >= 45
            assert cur["avg_sleep"] is not None
            assert cur["low_sleep_days"] >= 2
            assert len(data["trends"]) >= 1
        finally:
            _cleanup(uid)

    def test_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/insights/effectiveness-report", timeout=10)
        assert r.status_code == 401


# ─── (4) Fatigue Detection ───────────────────────────────────────
class TestFatigue:
    def test_fatigue_empty(self):
        uid, tok = _dev_login("fat_empty")
        try:
            r = _client(tok).get(f"{BASE_URL}/api/learning/me/fatigue")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["fatigued"] is False
            assert data["evidence"]["n"] == 0
        finally:
            _cleanup(uid)

    def test_fatigue_from_errors(self):
        uid, tok = _dev_login("fat_err")
        try:
            now = datetime.now(timezone.utc)
            for i in range(5):
                _db.student_content_events.insert_one({
                    "user_id": uid, "event_type": "answered",
                    "correct": False, "time_spent_sec": 30,
                    "created_at": _iso(now - timedelta(minutes=i)),
                    "content_id": f"c_{i}",
                })
            r = _client(tok).get(f"{BASE_URL}/api/learning/me/fatigue")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["fatigued"] is True, data
            reason = (data.get("reason") or "").lower()
            assert ("cansaço" in reason) or ("pausa" in reason) or ("respirar" in reason), reason
        finally:
            _cleanup(uid)

    def test_fatigue_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/learning/me/fatigue", timeout=10)
        assert r.status_code == 401


# ─── (5) Regression — nothing broke ──────────────────────────────
class TestRegression:
    def test_home_today_ok(self):
        uid, tok = _dev_login("reg_home")
        try:
            r = _client(tok).get(f"{BASE_URL}/api/home/today")
            assert r.status_code == 200
        finally:
            _cleanup(uid)

    def test_tutor_mastery_map(self):
        uid, tok = _dev_login("reg_tutor")
        try:
            r = _client(tok).get(f"{BASE_URL}/api/tutor/mastery-map")
            assert r.status_code == 200, r.text
        finally:
            _cleanup(uid)
