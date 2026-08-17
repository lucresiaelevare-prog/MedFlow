"""Iteration 5 regression sanity — backend untouched, verify endpoints still work."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://medflow-pre-beta.preview.emergentagent.com').rstrip('/')
TOKEN = 'test_session_support_1783445454477'
HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}


@pytest.fixture
def s():
    sess = requests.Session()
    sess.headers.update(HEADERS)
    return sess


def test_health(s):
    r = s.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200


def test_iea(s):
    r = s.get(f"{BASE_URL}/api/iea", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert 'iea' in d
    assert isinstance(d['iea'], (int, float))
    assert 'pillars' in d and len(d['pillars']) == 5


def test_missions_today(s):
    r = s.get(f"{BASE_URL}/api/missions/today", timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert 'bundle' in d


def test_streak(s):
    r = s.get(f"{BASE_URL}/api/streak", timeout=15)
    assert r.status_code == 200
    assert 'streak' in r.json()


def test_profile(s):
    r = s.get(f"{BASE_URL}/api/profile", timeout=15)
    assert r.status_code == 200
    assert 'profile' in r.json()


def test_support_contacts(s):
    r = s.get(f"{BASE_URL}/api/support-contacts", timeout=15)
    assert r.status_code == 200


def test_mental_health_alert(s):
    r = s.get(f"{BASE_URL}/api/mental-health/alert", timeout=15)
    assert r.status_code == 200


def test_badges(s):
    r = s.get(f"{BASE_URL}/api/badges", timeout=15)
    assert r.status_code == 200


def test_resources(s):
    r = s.get(f"{BASE_URL}/api/resources", timeout=15)
    assert r.status_code == 200
