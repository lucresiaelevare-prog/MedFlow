"""Integration status + scientific search tests (no paid AI calls)."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
QA_TOKEN = "medflow_qa_session_20260805"
HEADERS = {"Authorization": f"Bearer {QA_TOKEN}"}
COOKIES = {"session_token": QA_TOKEN}


# ── Status ────────────────────────────────────────────────────────────────────
def test_integrations_status_all_configured():
    r = requests.get(f"{BASE_URL}/api/integrations/status", headers=HEADERS, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    for provider in ("openai", "groq", "huggingface", "pubmed", "openalex"):
        assert provider in data, f"missing {provider} in status"
        assert data[provider].get("configured") is True, f"{provider} not configured: {data[provider]}"
    assert data["pubmed"].get("api_key") is True, f"pubmed.api_key expected True, got {data['pubmed']}"


def test_integrations_status_requires_auth():
    r = requests.get(f"{BASE_URL}/api/integrations/status", timeout=15)
    assert r.status_code == 401


# ── PubMed search ─────────────────────────────────────────────────────────────
def test_pubmed_search_returns_items():
    r = requests.get(
        f"{BASE_URL}/api/integrations/pubmed/search",
        params={"q": "anatomia", "retmax": 1},
        headers=HEADERS,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("query") == "anatomia"
    assert isinstance(body.get("items"), list)
    assert isinstance(body.get("count"), int)
    assert body["count"] == len(body["items"])
    # We requested retmax=1; expect at least one hit for such a broad term
    assert body["count"] >= 1, f"expected >=1 item, got {body}"


# ── OpenAlex search ───────────────────────────────────────────────────────────
def test_openalex_search_returns_items():
    r = requests.get(
        f"{BASE_URL}/api/integrations/openalex/search",
        params={"q": "anatomia", "per_page": 1},
        headers=HEADERS,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("query") == "anatomia"
    assert isinstance(body.get("items"), list)
    assert isinstance(body.get("count"), int)
    assert body["count"] == len(body["items"])
    assert body["count"] >= 1, f"expected >=1 item, got {body}"


# ── Cookie-based auth also works ──────────────────────────────────────────────
def test_status_via_cookie_session():
    r = requests.get(f"{BASE_URL}/api/integrations/status", cookies=COOKIES, timeout=15)
    assert r.status_code == 200
