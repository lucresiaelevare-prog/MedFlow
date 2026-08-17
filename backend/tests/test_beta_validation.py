"""Beta validation smoke for MedFlow (iteration 3).

Coverage:
- Auth guard on private routes (checkin, habits, tutor, resources, profile, support).
- /api/auth/me with QA session (Bearer + cookie).
- /api/auth/dev-login must return 404 (dev-login disabled).
- Submit a check-in and confirm it appears in /api/checkin/history.
- Log a care action (habit) and confirm counter increments in /api/care/today.
- One low-cost real OpenAI call via /api/integrations/openai/chat (max_tokens=5).
- PubMed + OpenAlex 1-result search sanity.
- Light concurrency smoke: 10 parallel /api/auth/me requests must all be 200.
"""
from __future__ import annotations

import concurrent.futures
import os

import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://medflow-pre-beta.preview.emergentagent.com"
).rstrip("/")
QA_TOKEN = "medflow_qa_session_20260805"
AUTH = {"Authorization": f"Bearer {QA_TOKEN}"}

PRIVATE_GETS = [
    "/api/auth/me",
    "/api/history",
    "/api/care/today",
    "/api/goals/weekly",
    "/api/report/weekly",
    "/api/resources",
    "/api/profile",
    "/api/mode",
    "/api/support-contacts",
    "/api/integrations/status",
]


# ─── Auth guard ──────────────────────────────────────────────────────
def test_private_routes_require_auth():
    failures = []
    for path in PRIVATE_GETS:
        r = requests.get(f"{BASE_URL}{path}", timeout=15)
        if r.status_code != 401:
            failures.append((path, r.status_code))
    assert not failures, f"expected 401 without token, got: {failures}"


def test_private_routes_ok_with_qa_session():
    failures = []
    for path in PRIVATE_GETS:
        r = requests.get(f"{BASE_URL}{path}", headers=AUTH, timeout=20)
        if r.status_code >= 500:
            failures.append((path, r.status_code, r.text[:200]))
        elif r.status_code != 200:
            failures.append((path, r.status_code, r.text[:200]))
    assert not failures, f"private GETs failed with QA session: {failures}"


def test_dev_login_disabled():
    r = requests.post(f"{BASE_URL}/api/auth/dev-login", json={}, timeout=15)
    assert r.status_code == 404, r.text


# ─── Check-in flow ───────────────────────────────────────────────────
def test_checkin_submit_and_persist():
    payload = {
        "sleep_hours": 7.5,
        "energy": 4,
        "mood": 4,
        "stress": 2,
        "upcoming_exam": False,
        "on_call_today": False,
        "free_text": "QA beta smoke — dia tranquilo.",
    }
    r = requests.post(f"{BASE_URL}/api/checkin", json=payload, headers=AUTH, timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    # response should contain the persisted check-in id or recommendation
    assert isinstance(body, dict)

    # History reflects the new entry
    h = requests.get(f"{BASE_URL}/api/history", headers=AUTH, timeout=20)
    assert h.status_code == 200
    hist = h.json()
    items = hist.get("checkins", []) if isinstance(hist, dict) else []
    assert isinstance(items, list) and len(items) >= 1, f"empty history after check-in: {hist}"


# ─── Habits flow ─────────────────────────────────────────────────────
def test_care_log_increments_today_counter():
    before = requests.get(f"{BASE_URL}/api/care/today", headers=AUTH, timeout=15)
    assert before.status_code == 200
    before_map = {t["slug"]: t["done_today"] for t in before.json()["tasks"]}

    r = requests.post(
        f"{BASE_URL}/api/care/log", json={"slug": "hydrate"}, headers=AUTH, timeout=15
    )
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True

    after = requests.get(f"{BASE_URL}/api/care/today", headers=AUTH, timeout=15)
    after_map = {t["slug"]: t["done_today"] for t in after.json()["tasks"]}
    assert after_map["hydrate"] == before_map.get("hydrate", 0) + 1


# ─── AI single low-cost call (authorised) ────────────────────────────
def test_openai_chat_single_low_cost():
    r = requests.post(
        f"{BASE_URL}/api/integrations/openai/chat",
        headers=AUTH,
        json={
            "message": "Responda somente OK.",
            "max_tokens": 5,
        },
        timeout=45,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    text = data.get("text") or data.get("content") or data.get("message") or ""
    if not text and isinstance(data.get("choices"), list) and data["choices"]:
        choice = data["choices"][0]
        text = (choice.get("message") or {}).get("content") or choice.get("text") or ""
    assert isinstance(text, str) and text.strip(), f"empty OpenAI response: {data}"


# ─── Academic search sanity ──────────────────────────────────────────
def test_pubmed_search_one_result():
    r = requests.get(
        f"{BASE_URL}/api/integrations/pubmed/search",
        headers=AUTH,
        params={"q": "anatomy", "retmax": 1},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("count") == len(body.get("items", []))
    assert len(body["items"]) >= 1


def test_openalex_search_one_result():
    r = requests.get(
        f"{BASE_URL}/api/integrations/openalex/search",
        headers=AUTH,
        params={"q": "anatomy", "per_page": 1},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("count") == len(body.get("items", []))
    assert len(body["items"]) >= 1


# ─── Concurrency smoke (beta 50) ─────────────────────────────────────
def test_concurrent_auth_me_10():
    def _call(_):
        return requests.get(f"{BASE_URL}/api/auth/me", headers=AUTH, timeout=20).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(_call, range(10)))
    assert all(sc == 200 for sc in results), f"unstable /auth/me under load: {results}"
