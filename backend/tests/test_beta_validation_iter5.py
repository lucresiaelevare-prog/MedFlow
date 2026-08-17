"""Iteration 5 - Verify OpenAI 429 circuit breaker (_OPENAI_RATE_LIMIT_UNTIL).

After the first 429 from OpenAI, subsequent calls within 5 minutes should skip
OpenAI entirely and go straight to Groq. Verified by (a) both calls returning
200 with provider=groq + fallback_from=openai and (b) the second call being
noticeably faster than the first (no OpenAI round-trip).
"""
from __future__ import annotations

import os
import time

import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://medflow-pre-beta.preview.emergentagent.com"
).rstrip("/")
QA_TOKEN = "medflow_qa_session_20260805"
AUTH = {"Authorization": f"Bearer {QA_TOKEN}"}


def _call_openai_chat():
    started = time.monotonic()
    r = requests.post(
        f"{BASE_URL}/api/integrations/openai/chat",
        headers=AUTH,
        json={"message": "Responda somente OK.", "max_tokens": 5},
        timeout=25,
    )
    return r, time.monotonic() - started


def test_openai_circuit_breaker_two_calls():
    r1, t1 = _call_openai_chat()
    assert r1.status_code == 200, f"call1: {r1.status_code} {r1.text[:300]}"
    d1 = r1.json()
    assert d1.get("provider") == "groq", f"call1 provider: {d1}"
    assert d1.get("fallback_from") == "openai", f"call1 fallback_from: {d1}"
    assert (d1.get("text") or "").strip(), f"call1 empty text: {d1}"

    r2, t2 = _call_openai_chat()
    assert r2.status_code == 200, f"call2: {r2.status_code} {r2.text[:300]}"
    d2 = r2.json()
    assert d2.get("provider") == "groq", f"call2 provider: {d2}"
    assert d2.get("fallback_from") == "openai", f"call2 fallback_from: {d2}"
    assert (d2.get("text") or "").strip(), f"call2 empty text: {d2}"

    print(f"[iter5] call1={t1:.3f}s call2={t2:.3f}s")
    # After the breaker trips, call2 should NOT do an OpenAI round trip.
    # We accept t2 <= t1 + small jitter; assert t2 is meaningfully lower than t1
    # OR that t2 is short enough on its own (< 2s) to prove no OpenAI attempt.
    assert t2 < 2.0 or t2 < t1, (
        f"circuit breaker likely not tripped: t1={t1:.3f}s t2={t2:.3f}s "
        "(expected t2 short because OpenAI is skipped)"
    )


def test_auth_me_qa_session():
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=AUTH, timeout=15)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    data = r.json()
    assert data.get("email") or data.get("user"), f"unexpected /auth/me body: {data}"


def test_landing_shell_loads():
    r = requests.get(f"{BASE_URL}/", timeout=20)
    assert r.status_code == 200
    assert 'id="root"' in r.text
