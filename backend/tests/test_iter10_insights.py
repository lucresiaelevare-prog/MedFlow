"""Tests for iteration 10 — /api/insights/weekly-report and /api/goals/weekly."""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/dev-login",
                      json={"email": "tester_iter10@medflow.dev", "name": "Iter10"})
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# 1. Auth required
def test_weekly_report_requires_auth():
    r = requests.get(f"{BASE_URL}/api/insights/weekly-report")
    assert r.status_code == 401


# 2. Weekly goals endpoint still works
def test_goals_weekly(auth_headers):
    r = requests.get(f"{BASE_URL}/api/goals/weekly", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    for k in ("week_start", "week_end", "achieved", "total", "goals"):
        assert k in d
    assert isinstance(d["goals"], list) and len(d["goals"]) > 0
    g0 = d["goals"][0]
    for k in ("current", "target", "progress", "achieved", "slug", "title"):
        assert k in g0


# 3. Weekly-report structure default days=7
def test_weekly_report_structure(auth_headers):
    r = requests.get(f"{BASE_URL}/api/insights/weekly-report", headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    for key in ("focus_series", "habits_series", "mood_series", "totals", "coaching", "range"):
        assert key in d, f"missing {key}"
    assert len(d["focus_series"]) == 7
    assert len(d["habits_series"]) == 7
    assert len(d["mood_series"]) == 7
    # chronological
    dates = [x["date"] for x in d["focus_series"]]
    assert dates == sorted(dates)
    # totals keys
    for k in ("focus_minutes", "care_actions", "checkins", "avg_mood", "days_focused", "days_care"):
        assert k in d["totals"]
    # coaching
    assert "text" in d["coaching"] and "cached" in d["coaching"] and "date" in d["coaching"]
    assert isinstance(d["coaching"]["text"], str) and len(d["coaching"]["text"]) > 0


# 4. days=30 supported
def test_weekly_report_days_30(auth_headers):
    r = requests.get(f"{BASE_URL}/api/insights/weekly-report?days=30", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    assert len(d["focus_series"]) == 30


# 5. Coaching cache: second call same day -> cached=true, same text
def test_coaching_cached(auth_headers):
    r1 = requests.get(f"{BASE_URL}/api/insights/weekly-report", headers=auth_headers)
    text1 = r1.json()["coaching"]["text"]
    r2 = requests.get(f"{BASE_URL}/api/insights/weekly-report", headers=auth_headers)
    d2 = r2.json()
    assert d2["coaching"]["cached"] is True
    assert d2["coaching"]["text"] == text1


# 6. Aggregation reflects new activity
def test_weekly_report_aggregation(auth_headers):
    # Fresh user to avoid interference
    login = requests.post(f"{BASE_URL}/api/auth/dev-login",
                          json={"email": f"agg_{int(time.time())}@medflow.dev", "name": "Agg"}).json()
    h = {"Authorization": f"Bearer {login['session_token']}", "Content-Type": "application/json"}

    # Baseline
    base = requests.get(f"{BASE_URL}/api/insights/weekly-report", headers=h).json()["totals"]

    # Checkin mood=4
    c = requests.post(f"{BASE_URL}/api/checkin", headers=h,
                      json={"mood": 4, "energy": 3, "stress": 3, "sleep_hours": 7})
    assert c.status_code in (200, 201), c.text

    # Care log
    cl = requests.post(f"{BASE_URL}/api/care/log", headers=h, json={"slug": "hydrate"})
    assert cl.status_code == 200, cl.text

    # Pomodoro start + complete
    ps = requests.post(f"{BASE_URL}/api/pomodoro/start", headers=h,
                       json={"planned_minutes": 45})
    assert ps.status_code in (200, 201), ps.text
    sid = ps.json().get("id") or ps.json().get("session_id") or ps.json().get("session", {}).get("id")
    assert sid, f"no session id in {ps.json()}"
    pc = requests.post(f"{BASE_URL}/api/pomodoro/{sid}/complete", headers=h,
                       json={"focused_minutes": 45})
    assert pc.status_code in (200, 201), pc.text

    # Report
    d = requests.get(f"{BASE_URL}/api/insights/weekly-report", headers=h).json()
    t = d["totals"]
    assert t["focus_minutes"] >= 45, t
    assert t["care_actions"] >= 1
    assert t["checkins"] >= 1
    assert t["avg_mood"] == 4.0
    assert t["days_focused"] >= 1
    assert t["days_care"] >= 1
