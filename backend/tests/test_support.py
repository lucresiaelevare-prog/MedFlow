"""Support contacts + smoke regression tests for MedFlow iteration 3."""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
TOKEN = "test_session_support_1783445454477"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

EXPECTED_SLUGS = {"cvv", "samu", "caps", "abrames", "mapa-saude-mental", "apoio-universitario"}


# --- Support: contacts list ---
class TestSupportContactsList:
    def test_requires_auth(self):
        r = requests.get(f"{API}/support-contacts")
        assert r.status_code == 401

    def test_list_returns_six_expected_contacts(self):
        r = requests.get(f"{API}/support-contacts", headers=H)
        assert r.status_code == 200, r.text
        contacts = r.json()["contacts"]
        assert len(contacts) == 6
        slugs = {c["slug"] for c in contacts}
        assert slugs == EXPECTED_SLUGS
        # CVV + SAMU priority
        by_slug = {c["slug"]: c for c in contacts}
        assert by_slug["cvv"].get("priority") is True
        assert by_slug["cvv"]["phone"] == "188"
        assert by_slug["samu"].get("priority") is True
        assert by_slug["samu"]["phone"] == "192"
        # each has at least one actionable channel
        for c in contacts:
            assert any(c.get(k) for k in ("phone", "chat_url", "url", "email", "hours"))


# --- Support: log endpoint ---
class TestSupportLog:
    def test_valid_call_log_persists(self):
        r = requests.post(f"{API}/support-contacts/log",
                          json={"contact_slug": "cvv", "method": "call"}, headers=H)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_valid_chat_log(self):
        r = requests.post(f"{API}/support-contacts/log",
                          json={"contact_slug": "cvv", "method": "chat"}, headers=H)
        assert r.status_code == 200

    def test_valid_link_log(self):
        r = requests.post(f"{API}/support-contacts/log",
                          json={"contact_slug": "caps", "method": "link"}, headers=H)
        assert r.status_code == 200

    def test_invalid_slug_rejected(self):
        r = requests.post(f"{API}/support-contacts/log",
                          json={"contact_slug": "bogus", "method": "call"}, headers=H)
        assert r.status_code == 400

    def test_invalid_method_rejected(self):
        r = requests.post(f"{API}/support-contacts/log",
                          json={"contact_slug": "cvv", "method": "sms"}, headers=H)
        assert r.status_code == 400

    def test_missing_fields_rejected(self):
        r = requests.post(f"{API}/support-contacts/log",
                          json={"contact_slug": "cvv"}, headers=H)
        assert r.status_code in (400, 422)


# --- Regression smoke tests for existing endpoints ---
class TestRegressionSmoke:
    def test_root(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        assert r.json()["service"] == "medflow-copiloto-academico"

    def test_iea(self):
        r = requests.get(f"{API}/iea", headers=H)
        assert r.status_code == 200
        d = r.json()
        assert len(d["pillars"]) == 5
        assert 0 <= d["iea"] <= 100

    def test_badges_catalog(self):
        r = requests.get(f"{API}/badges", headers=H)
        assert r.status_code == 200
        assert len(r.json()["badges"]) == 10

    def test_resources(self):
        r = requests.get(f"{API}/resources", headers=H)
        assert r.status_code == 200
        assert len(r.json()["resources"]) == 10

    def test_subjects_list(self):
        r = requests.get(f"{API}/subjects", headers=H)
        assert r.status_code == 200
        assert "subjects" in r.json()

    def test_exams_list(self):
        r = requests.get(f"{API}/exams", headers=H)
        assert r.status_code == 200
        assert "exams" in r.json()

    def test_mode_default_rotina(self):
        r = requests.get(f"{API}/mode", headers=H)
        assert r.status_code == 200
        assert r.json()["mode"] in {"rotina", "prova", "plantao", "dependencia", "recuperacao"}

    def test_mode_invalid_400(self):
        r = requests.post(f"{API}/mode", json={"mode": "bogus"}, headers=H)
        assert r.status_code == 400
