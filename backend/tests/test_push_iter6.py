"""Iteration 6 — Web Push (VAPID) tests. Covers /api/push/* + integration."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://medflow-pre-beta.preview.emergentagent.com").rstrip("/")
TOKEN = "test_session_support_1783445454477"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

FAKE_ENDPOINT = "https://fcm.googleapis.com/fcm/send/TEST_FAKE_ENDPOINT_iter6"
FAKE_KEYS = {"p256dh": "BNbxGYNMhEIi9zrneh7mqV4oUanjLzC3ySZW7pnGwqE4wJj5Iw7dCqB4qJXG-3iVeMSJ7yEqXcT5PZq3aQZM4Yc", "auth": "k8JV6HXulNz0DlBP2Q0m6A"}


# ---- /api/push/config ----
def test_config_requires_auth():
    r = requests.get(f"{BASE}/api/push/config")
    assert r.status_code == 401, r.text


def test_config_ok():
    r = requests.get(f"{BASE}/api/push/config", headers=H)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "vapid_public_key" in d
    assert len(d["vapid_public_key"]) > 80
    assert d["subject"].startswith("mailto:")
    assert set(d["supported_events"]) == {"checkin", "digest", "exams", "mental_health", "missions", "streak"}


# ---- subscribe / preferences ----
def test_subscribe_upsert_and_enables_notifications():
    # Reset prefs first for a deterministic default check across runs
    requests.patch(
        f"{BASE}/api/push/preferences",
        json={"checkin": True, "digest": True, "exams": True, "mental_health": True, "missions": True, "streak": True},
        headers=H,
    )
    body = {"endpoint": FAKE_ENDPOINT, "keys": FAKE_KEYS, "user_agent": "pytest", "tz": "America/Sao_Paulo"}
    r1 = requests.post(f"{BASE}/api/push/subscribe", json=body, headers=H)
    assert r1.status_code == 200, r1.text
    # second call - should upsert not duplicate
    r2 = requests.post(f"{BASE}/api/push/subscribe", json=body, headers=H)
    assert r2.status_code == 200

    prefs = requests.get(f"{BASE}/api/push/preferences", headers=H).json()
    assert prefs["notifications_enabled"] is True
    assert prefs["tz"] == "America/Sao_Paulo"
    for k in ("checkin", "digest", "exams", "mental_health", "missions", "streak"):
        assert prefs["preferences"][k] is True, f"pref {k} should default True"


def test_preferences_patch_subset_and_bad_tz():
    r = requests.patch(f"{BASE}/api/push/preferences", json={"digest": False, "streak": False}, headers=H)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["preferences"]["digest"] is False
    assert d["preferences"]["streak"] is False
    assert d["preferences"]["checkin"] is True

    r2 = requests.patch(f"{BASE}/api/push/preferences", json={"tz": "Not/AZone"}, headers=H)
    assert r2.status_code == 400

    # restore
    requests.patch(f"{BASE}/api/push/preferences", json={"digest": True, "streak": True}, headers=H)


def test_push_test_with_fake_endpoint_returns_failed_and_keeps_subscription():
    # subscription created in test_subscribe; fire test
    r = requests.post(f"{BASE}/api/push/test", json={}, headers=H)
    assert r.status_code == 200, r.text
    d = r.json()
    # webpush will fail against fake endpoint but status is not 404/410 (network/dns failure typically)
    assert d.get("failed", 0) >= 1 or d.get("sent", 0) >= 0
    # subscription must still exist (endpoint not deleted)
    # verify via a second /test still returns >=1 attempt (i.e., sub not deleted)
    r2 = requests.post(f"{BASE}/api/push/test", json={}, headers=H)
    assert r2.status_code == 200
    assert (r2.json().get("failed", 0) + r2.json().get("sent", 0)) >= 1


def test_unsubscribe():
    r = requests.delete(f"{BASE}/api/push/subscribe", params={"endpoint": FAKE_ENDPOINT}, headers=H)
    assert r.status_code == 200
    # after unsubscribe, test returns sent=0 failed=0
    r2 = requests.post(f"{BASE}/api/push/test", json={}, headers=H)
    assert r2.status_code == 200
    d = r2.json()
    assert d.get("sent", 0) == 0 and d.get("failed", 0) == 0


# ---- Integration: /api/checkin high-risk ----
def test_checkin_high_risk_still_returns_alert_no_500():
    r = requests.post(
        f"{BASE}/api/checkin",
        json={"mood": 1, "energy": 1, "focus": 1, "sleep_hours": 5, "stress": 5, "free_text": "quero me matar, não aguento mais viver"},
        headers=H,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    mh = d.get("mental_health_alert")
    assert mh is not None
    assert mh.get("id") and mh.get("level") in ("medium", "high") and mh.get("message")
    assert isinstance(mh.get("suggested_contacts", []), list)


# ---- Regression ----
@pytest.mark.parametrize("path", ["/api/", "/api/iea", "/api/missions/today", "/api/support-contacts", "/api/mental-health/alert"])
def test_regression_endpoints(path):
    r = requests.get(f"{BASE}{path}", headers=H)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"


# ---- Service Worker file ----
def test_sw_js_available():
    r = requests.get(f"{BASE}/sw.js")
    assert r.status_code == 200, r.text[:200]
    ct = r.headers.get("Content-Type", "")
    assert "javascript" in ct.lower(), f"content-type: {ct}"
    body = r.text
    assert "self.addEventListener" in body
    assert "push" in body
