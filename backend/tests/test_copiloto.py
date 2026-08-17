"""Copiloto Acadêmico backend tests — pivot features (IEA, missions, subjects, exams, badges, resources, mode, profile)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
TOKEN = "test_session_medflow_123"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

state = {}


# --- IEA ---
class TestIEA:
    def test_iea_shape(self):
        r = requests.get(f"{API}/iea", headers=H)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data["iea"], int)
        assert 0 <= data["iea"] <= 100
        assert data["weakest_pillar"] in {"estudos", "sono", "saude_fisica", "bem_estar", "social"}
        assert len(data["pillars"]) == 5
        keys = {p["key"] for p in data["pillars"]}
        assert keys == {"estudos", "sono", "saude_fisica", "bem_estar", "social"}
        for p in data["pillars"]:
            assert "label" in p and "emoji" in p and 0 <= p["score"] <= 100
        # IEA equals min pillar
        assert data["iea"] == min(p["score"] for p in data["pillars"])


# --- Profile & Mode ---
class TestProfileMode:
    def test_get_profile_defaults(self):
        r = requests.get(f"{API}/profile", headers=H)
        assert r.status_code == 200
        p = r.json()["profile"]
        assert p.get("study_tool") in ("anki", "quizlet", "remnote", "caderno", "outro")
        assert p.get("mode") in {"rotina", "prova", "plantao", "dependencia", "recuperacao"}

    def test_patch_profile_study_tool(self):
        r = requests.patch(f"{API}/profile", json={"study_tool": "quizlet"}, headers=H)
        assert r.status_code == 200
        assert r.json()["profile"]["study_tool"] == "quizlet"
        # revert
        requests.patch(f"{API}/profile", json={"study_tool": "anki"}, headers=H)

    def test_mode_valid_and_invalid(self):
        r = requests.post(f"{API}/mode", json={"mode": "prova"}, headers=H)
        assert r.status_code == 200
        assert r.json()["mode"] == "prova"
        r = requests.get(f"{API}/mode", headers=H)
        assert r.json()["mode"] == "prova"
        r = requests.post(f"{API}/mode", json={"mode": "bogus"}, headers=H)
        assert r.status_code == 400
        # reset to rotina
        requests.post(f"{API}/mode", json={"mode": "rotina"}, headers=H)


# --- Subjects & Exams ---
class TestSubjectsExams:
    def test_create_list_delete_subject_with_exams(self):
        r = requests.post(f"{API}/subjects",
                          json={"name": "TEST_Cardio", "is_dependency": True}, headers=H)
        assert r.status_code == 200
        subj = r.json()["subject"]
        assert subj["is_dependency"] is True
        state["subject_id"] = subj["id"]

        r = requests.get(f"{API}/subjects", headers=H)
        assert any(s["id"] == subj["id"] for s in r.json()["subjects"])

        # add exam
        r = requests.post(f"{API}/exams", json={
            "subject_id": subj["id"], "name": "TEST_P1", "exam_date": "2026-06-01"
        }, headers=H)
        assert r.status_code == 200
        exam = r.json()["exam"]
        state["exam_id"] = exam["id"]

        # list sorted
        r = requests.get(f"{API}/exams", headers=H)
        assert r.status_code == 200
        exams = r.json()["exams"]
        assert any(e["id"] == exam["id"] for e in exams)

        # grade
        r = requests.patch(f"{API}/exams/{exam['id']}",
                           json={"grade": 8.5, "weak_topics": "TEST_arritmias"}, headers=H)
        assert r.status_code == 200
        assert r.json()["exam"]["grade"] == 8.5
        assert r.json()["exam"]["weak_topics"] == "TEST_arritmias"

    def test_exam_requires_valid_subject(self):
        r = requests.post(f"{API}/exams", json={
            "subject_id": "subj_nope", "name": "TEST_X", "exam_date": "2026-06-01"
        }, headers=H)
        assert r.status_code == 404

    def test_delete_subject_cascades_exams(self):
        sid = state.get("subject_id")
        eid = state.get("exam_id")
        assert sid and eid
        r = requests.delete(f"{API}/subjects/{sid}", headers=H)
        assert r.status_code == 200
        r = requests.get(f"{API}/exams", headers=H)
        assert not any(e["id"] == eid for e in r.json()["exams"])


# --- Missions ---
class TestMissions:
    def test_generate_and_cache_and_get(self):
        r = requests.post(f"{API}/missions/generate", headers=H, timeout=60)
        assert r.status_code == 200, r.text
        bundle = r.json()["bundle"]
        assert 3 <= len(bundle["missions"]) <= 5
        for m in bundle["missions"]:
            assert m["title"] and m["category"] and "minutes" in m and "why" in m
        state["bundle_id"] = bundle["id"]
        state["mission_id"] = bundle["missions"][0]["id"]

        # cached second call
        r2 = requests.post(f"{API}/missions/generate", headers=H)
        assert r2.status_code == 200
        assert r2.json()["bundle"]["id"] == bundle["id"]

        # today
        r3 = requests.get(f"{API}/missions/today", headers=H)
        assert r3.status_code == 200
        assert r3.json()["bundle"]["id"] == bundle["id"]

    def test_complete_and_skip(self):
        mid = state["mission_id"]
        r = requests.post(f"{API}/missions/{mid}/complete",
                          json={"completed": True}, headers=H)
        assert r.status_code == 200
        b = r.json()["bundle"]
        m = next(x for x in b["missions"] if x["id"] == mid)
        assert m["completed"] is True
        # skip another
        others = [x for x in b["missions"] if x["id"] != mid]
        if others:
            oid = others[0]["id"]
            r = requests.post(f"{API}/missions/{oid}/complete",
                              json={"completed": False}, headers=H)
            assert r.status_code == 200
            b2 = r.json()["bundle"]
            m2 = next(x for x in b2["missions"] if x["id"] == oid)
            assert m2["skipped"] is True

    def test_complete_missing_mission(self):
        r = requests.post(f"{API}/missions/m_nope/complete",
                          json={"completed": True}, headers=H)
        assert r.status_code == 404


# --- Badges ---
class TestBadges:
    def test_catalog_and_earned(self):
        r = requests.get(f"{API}/badges", headers=H)
        assert r.status_code == 200
        badges = r.json()["badges"]
        assert len(badges) == 10
        by_slug = {b["slug"]: b for b in badges}
        assert "primeiro_passo" in by_slug
        # After previous test iterations there was a checkin — so primeiro_passo should be earned
        assert by_slug["primeiro_passo"]["earned"] is True


# --- Resources ---
class TestResources:
    def test_list_all(self):
        r = requests.get(f"{API}/resources", headers=H)
        assert r.status_code == 200
        items = r.json()["resources"]
        assert len(items) == 10
        for it in items:
            assert it["url"].startswith("http")
            assert it["pillar"] in {"estudos", "sono", "saude_fisica", "bem_estar", "social"}

    def test_filter_by_pillar(self):
        r = requests.get(f"{API}/resources?pillar=estudos", headers=H)
        assert r.status_code == 200
        items = r.json()["resources"]
        assert len(items) > 0
        for it in items:
            assert it["pillar"] == "estudos"


# --- Legacy check-in regenerates missions bundle ---
class TestLegacyCheckinResetsBundle:
    def test_checkin_clears_todays_bundle(self):
        # ensure bundle exists
        r0 = requests.get(f"{API}/missions/today", headers=H)
        assert r0.json()["bundle"] is not None
        # submit checkin
        payload = {"sleep_hours": 7.5, "energy": 4, "mood": 4, "stress": 2,
                   "upcoming_exam": False, "on_call_today": False}
        r = requests.post(f"{API}/checkin", json=payload, headers=H, timeout=60)
        assert r.status_code == 200
        # bundle should be cleared
        r1 = requests.get(f"{API}/missions/today", headers=H)
        assert r1.json()["bundle"] is None


# --- Mood still works ---
class TestMoodMindfulness:
    def test_mood_log(self):
        r = requests.post(f"{API}/mood", json={"value": 5, "note": "TEST"}, headers=H)
        assert r.status_code == 200
        assert r.json()["mood"]["value"] == 5

    def test_mindfulness_log(self):
        r = requests.post(f"{API}/mindfulness/log",
                         json={"session_slug": "breath-4-7-8", "duration_seconds": 60},
                         headers=H)
        assert r.status_code == 200
