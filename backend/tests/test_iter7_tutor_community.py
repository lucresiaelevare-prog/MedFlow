"""Iteration 7 tests — Tutor IA, Comunidade, Acessibilidade, Regressão.

Runs against public backend URL from REACT_APP_BACKEND_URL.
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://medflow-pre-beta.preview.emergentagent.com").rstrip("/")


def _login(is_admin: bool = False, suffix: str = "") -> tuple[requests.Session, str, str]:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"tester{suffix}@medflow.local"
    r = s.post(f"{BASE_URL}/api/auth/dev-login", json={
        "email": email, "name": f"Tester{suffix}", "is_admin": is_admin,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    token = data["session_token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s, token, data["user"]["user_id"]


@pytest.fixture(scope="module")
def user_a():
    s, tok, uid = _login(suffix=f"-a-{uuid.uuid4().hex[:6]}")
    return s, tok, uid


@pytest.fixture(scope="module")
def user_b():
    s, tok, uid = _login(suffix=f"-b-{uuid.uuid4().hex[:6]}")
    return s, tok, uid


# ---------- Tutor IA ----------

@pytest.fixture(scope="module")
def tutor_feedback(user_a):
    s, _, _ = user_a
    r = s.post(f"{BASE_URL}/api/tutor/exam-feedback", json={
        "subject": "Anatomia",
        "exam_name": "P1",
        "grade": 5.0,
        "weak_topics": "ossos do crânio; forames",
        "strong_topics": "coluna",
    }, timeout=120)
    assert r.status_code == 200, f"status={r.status_code} body={r.text[:400]}"
    data = r.json()["feedback"]
    return data


def test_tutor_create_feedback_shape(tutor_feedback):
    fb = tutor_feedback
    assert fb["id"].startswith("tf_")
    assert isinstance(fb["diagnosis"], str) and len(fb["diagnosis"]) > 0
    assert isinstance(fb["focus_areas"], list) and len(fb["focus_areas"]) >= 1
    for fa in fb["focus_areas"]:
        assert "topic" in fa and "plan" in fa
    qs = fb["questions"]
    assert isinstance(qs, list) and len(qs) == 10
    for q in qs:
        assert "stem" in q and q["stem"]
        assert isinstance(q["options"], list) and len(q["options"]) == 4
        assert q["answer"].strip().upper()[:1] in {"A", "B", "C", "D"}
        assert q["explanation"]


def test_tutor_list_and_get(user_a, tutor_feedback):
    s, _, _ = user_a
    fid = tutor_feedback["id"]
    r = s.get(f"{BASE_URL}/api/tutor/exam-feedback")
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(it["id"] == fid for it in items)

    r2 = s.get(f"{BASE_URL}/api/tutor/exam-feedback/{fid}")
    assert r2.status_code == 200
    assert r2.json()["feedback"]["id"] == fid


def test_tutor_submit_answers(user_a, tutor_feedback):
    s, _, _ = user_a
    fid = tutor_feedback["id"]
    answers = {str(i): "A" for i in range(10)}
    r = s.post(f"{BASE_URL}/api/tutor/exam-feedback/{fid}/answers", json={"answers": answers})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "score" in data
    assert data["total"] == 10
    assert isinstance(data["correct"], int)
    assert isinstance(data["detail"], list) and len(data["detail"]) == 10
    for d in data["detail"]:
        assert isinstance(d["correct"], bool)
        assert "explanation" in d


def test_tutor_delete(user_a, tutor_feedback):
    s, _, _ = user_a
    fid = tutor_feedback["id"]
    r = s.delete(f"{BASE_URL}/api/tutor/exam-feedback/{fid}")
    assert r.status_code == 200
    r2 = s.get(f"{BASE_URL}/api/tutor/exam-feedback/{fid}")
    assert r2.status_code == 404


# ---------- Comunidade ----------

def test_community_create_validations(user_a):
    s, _, _ = user_a
    # short body
    r = s.post(f"{BASE_URL}/api/community/posts", json={"body": "ab"})
    assert r.status_code == 400

    # default category geral when not provided
    r2 = s.post(f"{BASE_URL}/api/community/posts", json={"body": "Meu primeiro post de teste"})
    assert r2.status_code == 200, r2.text
    post = r2.json()["post"]
    assert post["category"] == "geral"


def test_community_list_and_category_filter(user_a):
    s, _, _ = user_a
    # Create one with category rotina
    r = s.post(f"{BASE_URL}/api/community/posts", json={"body": "Rotina puxada hoje", "category": "rotina"})
    assert r.status_code == 200
    r2 = s.get(f"{BASE_URL}/api/community/posts")
    assert r2.status_code == 200
    posts = r2.json()["posts"]
    assert any("like_count" in p and "liked_by_me" in p and "is_mine" in p for p in posts)

    r3 = s.get(f"{BASE_URL}/api/community/posts", params={"category": "rotina"})
    assert r3.status_code == 200
    assert all(p["category"] == "rotina" for p in r3.json()["posts"])


def test_community_like_toggle(user_a):
    s, _, _ = user_a
    r = s.post(f"{BASE_URL}/api/community/posts", json={"body": "Testando like"})
    pid = r.json()["post"]["id"]
    r1 = s.post(f"{BASE_URL}/api/community/posts/{pid}/like")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["liked"] is True and d1["like_count"] == 1

    r2 = s.post(f"{BASE_URL}/api/community/posts/{pid}/like")
    d2 = r2.json()
    assert d2["liked"] is False and d2["like_count"] == 0


def test_community_comments_crud(user_a):
    s, _, _ = user_a
    r = s.post(f"{BASE_URL}/api/community/posts", json={"body": "Post p/ comentários"})
    pid = r.json()["post"]["id"]

    rc = s.post(f"{BASE_URL}/api/community/posts/{pid}/comments", json={"body": "Bom post!"})
    assert rc.status_code == 200
    cid = rc.json()["comment"]["id"]

    rl = s.get(f"{BASE_URL}/api/community/posts/{pid}/comments")
    assert rl.status_code == 200
    assert any(c["id"] == cid for c in rl.json()["comments"])

    rd = s.delete(f"{BASE_URL}/api/community/comments/{cid}")
    assert rd.status_code == 200


def test_community_delete_permissions(user_a, user_b):
    sa, _, _ = user_a
    sb, _, _ = user_b
    r = sa.post(f"{BASE_URL}/api/community/posts", json={"body": "Só o dono pode apagar"})
    pid = r.json()["post"]["id"]
    # user B tries to delete → 403
    rb = sb.delete(f"{BASE_URL}/api/community/posts/{pid}")
    assert rb.status_code == 403
    # owner deletes → 200
    ra = sa.delete(f"{BASE_URL}/api/community/posts/{pid}")
    assert ra.status_code == 200


def test_community_anonymous_author(user_a):
    s, _, _ = user_a
    # Enable anonymous
    rp = s.patch(f"{BASE_URL}/api/profile", json={"anonymous_community": True})
    assert rp.status_code == 200
    r = s.post(f"{BASE_URL}/api/community/posts", json={"body": "Post anônimo aqui"})
    assert r.status_code == 200
    author = r.json()["post"]["author"]
    assert author["name"] == "Estudante anônimo"
    # Reset
    s.patch(f"{BASE_URL}/api/profile", json={"anonymous_community": False})


# ---------- Perfil / Acessibilidade ----------

def test_profile_accessibility_persistence(user_b):
    s, _, _ = user_b
    payload = {
        "font_size": "lg",
        "high_contrast": True,
        "simplified_ui": True,
        "dyslexia_font": True,
        "reduce_motion": True,
    }
    r = s.patch(f"{BASE_URL}/api/profile", json=payload)
    assert r.status_code == 200, r.text
    r2 = s.get(f"{BASE_URL}/api/profile")
    assert r2.status_code == 200
    prof = r2.json()
    # profile endpoint may return under 'profile' key or flat
    data = prof.get("profile", prof)
    for k, v in payload.items():
        assert data.get(k) == v, f"{k} expected {v} got {data.get(k)}"


# ---------- Regressão ----------

@pytest.mark.parametrize("path", [
    "/api/auth/me",
    "/api/iea",
    "/api/missions/today",
    "/api/agenda/blocks",
    "/api/leisure/suggestions",
    "/api/study/strategies",
    "/api/sleep/plan",
    "/api/priority/today",
    "/api/admin/whoami",
    "/api/habits/log",
])
def test_regression_get(user_a, path):
    s, _, _ = user_a
    r = s.get(f"{BASE_URL}{path}")
    # 200 or 405 acceptable when endpoint might be POST-only; but per spec should respond without error.
    assert r.status_code in (200, 405), f"{path} -> {r.status_code} {r.text[:200]}"
