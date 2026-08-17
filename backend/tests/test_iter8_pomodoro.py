"""Iteration 8 — Pomodoro adaptativo, ajustes Tutor 502 message e toggle_like idempotente.

Roda contra REACT_APP_BACKEND_URL / dev-login.
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://medflow-pre-beta.preview.emergentagent.com"
).rstrip("/")


def _login(suffix: str = "") -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"iter8{suffix}@medflow.local"
    r = s.post(
        f"{BASE_URL}/api/auth/dev-login",
        json={"email": email, "name": f"Iter8{suffix}", "is_admin": False},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    tok = r.json()["session_token"]
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def sess() -> requests.Session:
    return _login(suffix=f"-{uuid.uuid4().hex[:6]}")


# ---------- Pomodoro Config Adaptativa ----------

def _patch_profile(s: requests.Session, body: dict):
    r = s.patch(f"{BASE_URL}/api/profile", json=body, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


def _get_config(s):
    r = s.get(f"{BASE_URL}/api/pomodoro/config", timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["config"]


class TestPomodoroConfig:
    def test_tdah(self, sess):
        _patch_profile(sess, {"is_neurodivergent": True, "neurodivergence_type": "tdah"})
        cfg = _get_config(sess)
        assert cfg["block_minutes"] == 25
        assert cfg["break_minutes"] == 5
        assert cfg["cycles"] == 3
        assert "TDAH" in cfg["reason"] and "25/5" in cfg["reason"]

    def test_ultradian(self, sess):
        _patch_profile(sess, {"is_neurodivergent": False, "focus_technique": "ultradian"})
        cfg = _get_config(sess)
        assert (cfg["block_minutes"], cfg["break_minutes"], cfg["cycles"]) == (90, 20, 2)
        assert "ultradian" in cfg["reason"].lower() or "90/20" in cfg["reason"]

    def test_flow(self, sess):
        _patch_profile(sess, {"is_neurodivergent": False, "focus_technique": "flow"})
        cfg = _get_config(sess)
        assert (cfg["block_minutes"], cfg["break_minutes"], cfg["cycles"]) == (60, 15, 3)
        assert "flow" in cfg["reason"].lower() or "60/15" in cfg["reason"]

    def test_default(self, sess):
        _patch_profile(sess, {"is_neurodivergent": False, "focus_technique": "pomodoro"})
        cfg = _get_config(sess)
        assert (cfg["block_minutes"], cfg["break_minutes"], cfg["cycles"]) == (50, 10, 4)
        assert "50/10" in cfg["reason"]


# ---------- Pomodoro Start / Complete / Skip / Today / Delete ----------

class TestPomodoroFlow:
    def test_start_without_block(self, sess):
        r = sess.post(f"{BASE_URL}/api/pomodoro/start", json={"subject": "Anatomia"}, timeout=20)
        assert r.status_code == 200, r.text
        s = r.json()["session"]
        assert s["status"] == "running"
        assert s["subject"] == "Anatomia"
        assert s["block_id"] is None
        assert s["block"] is None
        assert "block_minutes" in (s.get("config") or {})

    def test_start_with_invalid_block(self, sess):
        r = sess.post(f"{BASE_URL}/api/pomodoro/start", json={"block_id": "does_not_exist"}, timeout=20)
        assert r.status_code == 404

    def test_start_with_valid_block(self, sess):
        # Cria bloco em /api/agenda/blocks
        blk_body = {
            "title": "Estudo Anatomia",
            "category": "study",
            "date": time.strftime("%Y-%m-%d"),
            "start_time": "09:00",
            "end_time": "10:00",
        }
        r = sess.post(f"{BASE_URL}/api/agenda/blocks", json=blk_body, timeout=20)
        assert r.status_code in (200, 201), r.text
        block = r.json().get("block") or r.json()
        block_id = block.get("id") or block.get("_id")
        assert block_id
        r2 = sess.post(f"{BASE_URL}/api/pomodoro/start", json={"block_id": block_id}, timeout=20)
        assert r2.status_code == 200, r2.text
        s = r2.json()["session"]
        assert s["block_id"] == block_id
        assert s["block"]["title"] == "Estudo Anatomia"
        assert s["block"]["category"] == "study"
        assert s["block"]["start_time"] == "09:00"
        # store on class for downstream
        TestPomodoroFlow._block_id = block_id
        TestPomodoroFlow._session_id = s["id"]

    def test_complete_with_block(self, sess):
        sid = TestPomodoroFlow._session_id
        r = sess.post(
            f"{BASE_URL}/api/pomodoro/{sid}/complete",
            json={"focused_minutes": 48, "completed_cycles": 2},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        s = r.json()["session"]
        assert s["status"] == "completed"
        assert s["focused_minutes"] == 48
        assert s["completed_cycles"] == 2
        # Verifica bloco marcado done=true
        r_blocks = sess.get(f"{BASE_URL}/api/agenda/blocks", timeout=20)
        assert r_blocks.status_code == 200
        blocks = r_blocks.json().get("blocks") or r_blocks.json().get("items") or []
        blk = next((b for b in blocks if b.get("id") == TestPomodoroFlow._block_id), None)
        assert blk is not None, f"block not returned: {blocks}"
        assert blk.get("done") is True

    def test_complete_empty_body(self, sess):
        # start fresh session
        r = sess.post(f"{BASE_URL}/api/pomodoro/start", json={"subject": "Fisio"}, timeout=20)
        sid = r.json()["session"]["id"]
        r2 = sess.post(f"{BASE_URL}/api/pomodoro/{sid}/complete", json={}, timeout=20)
        assert r2.status_code == 200, r2.text
        s = r2.json()["session"]
        assert s["status"] == "completed"
        assert isinstance(s["focused_minutes"], int)  # derived from elapsed

    def test_skip_and_repeat(self, sess):
        r = sess.post(f"{BASE_URL}/api/pomodoro/start", json={"subject": "Bioq"}, timeout=20)
        sid = r.json()["session"]["id"]
        r1 = sess.post(f"{BASE_URL}/api/pomodoro/{sid}/skip", timeout=20)
        assert r1.status_code == 200
        r2 = sess.post(f"{BASE_URL}/api/pomodoro/{sid}/skip", timeout=20)
        assert r2.status_code == 404

    def test_today_and_totals(self, sess):
        r = sess.get(f"{BASE_URL}/api/pomodoro/today", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert "date" in data and "config" in data and "sessions" in data and "totals" in data
        # at least the 2 completed sessions above
        assert data["totals"]["completed_sessions"] >= 2
        assert data["totals"]["focused_minutes"] >= 48

    def test_delete(self, sess):
        r = sess.post(f"{BASE_URL}/api/pomodoro/start", json={"subject": "Del"}, timeout=20)
        sid = r.json()["session"]["id"]
        r_del = sess.delete(f"{BASE_URL}/api/pomodoro/{sid}", timeout=20)
        assert r_del.status_code == 200
        r_t = sess.get(f"{BASE_URL}/api/pomodoro/today", timeout=20)
        ids = [s["id"] for s in r_t.json()["sessions"]]
        assert sid not in ids


# ---------- Code review — Tutor 502 mensagem genérica ----------

class TestTutorSafety:
    def test_exam_feedback_valid_or_generic_502(self, sess):
        r = sess.post(
            f"{BASE_URL}/api/tutor/exam-feedback",
            json={
                "subject": "Anatomia",
                "exam_name": "P1",
                "grade": 6.0,
                "weak_topics": "ossos do crânio",
                "strong_topics": "coluna vertebral",
            },
            timeout=180,
        )
        # regressão: idealmente 200
        assert r.status_code in (200, 502), f"unexpected status {r.status_code}: {r.text[:300]}"
        if r.status_code == 502:
            body = r.text.lower()
            for leak in ["exception:", "traceback", "stacktrace", "anthropic", "claude"]:
                assert leak not in body, f"vazamento de detalhe interno no 502: {leak} — body={r.text[:300]}"
            # deve conter algo genérico
            assert (
                "temporariamente" in body or "indispon" in body or "tente novamente" in body
            ), r.text


# ---------- Code review — toggle_like idempotente ----------

class TestToggleLikeIdempotent:
    def test_like_unlike_like(self, sess):
        # cria post
        r = sess.post(
            f"{BASE_URL}/api/community/posts",
            json={"body": "Teste de like idempotente iter8", "category": "geral"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        pid = r.json()["post"]["id"]
        # 1st like
        r1 = sess.post(f"{BASE_URL}/api/community/posts/{pid}/like", timeout=20)
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["liked"] is True
        assert d1["like_count"] == 1
        # unlike
        r2 = sess.post(f"{BASE_URL}/api/community/posts/{pid}/like", timeout=20)
        d2 = r2.json()
        assert d2["liked"] is False
        assert d2["like_count"] == 0
        # like again
        r3 = sess.post(f"{BASE_URL}/api/community/posts/{pid}/like", timeout=20)
        d3 = r3.json()
        assert d3["liked"] is True
        assert d3["like_count"] == 1

        # cleanup
        sess.delete(f"{BASE_URL}/api/community/posts/{pid}", timeout=20)


# ---------- Regressão anti-quebra ----------

class TestRegression:
    def test_list_tutor_feedbacks(self, sess):
        r = sess.get(f"{BASE_URL}/api/tutor/exam-feedback", timeout=20)
        assert r.status_code == 200
        assert "items" in r.json()

    def test_list_community_posts(self, sess):
        r = sess.get(f"{BASE_URL}/api/community/posts", timeout=20)
        assert r.status_code == 200
        assert "posts" in r.json()

    def test_list_agenda_blocks(self, sess):
        r = sess.get(f"{BASE_URL}/api/agenda/blocks", timeout=20)
        assert r.status_code == 200
