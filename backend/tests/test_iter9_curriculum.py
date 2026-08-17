"""Iter9 — Curriculum templates, critical subjects, pomodoro subject linking."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://medflow-pre-beta.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    email = f"iter9_{uuid.uuid4().hex[:8]}@medflow.local"
    r = s.post(f"{BASE_URL}/api/auth/dev-login",
               json={"email": email, "name": "Iter9 Tester", "is_admin": False})
    assert r.status_code == 200, r.text
    tok = r.json().get("session_token")
    assert tok
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# ─── Templates ─────────────────────────────────────────────────

def test_curriculum_templates(client):
    r = client.get(f"{BASE_URL}/api/academic/curriculum-templates")
    assert r.status_code == 200
    data = r.json()
    slugs = {u["slug"]: u for u in data["universities"]}
    assert "faminas-bh" in slugs and "fcmmg" in slugs
    assert slugs["faminas-bh"]["label"] == "FAMINAS-BH"
    assert slugs["fcmmg"]["label"] == "FCMMG"
    assert slugs["faminas-bh"]["semesters"] == [1, 2, 3]
    assert slugs["fcmmg"]["semesters"] == [1, 2, 3]


# ─── FAMINAS-BH import ─────────────────────────────────────────

def test_import_faminas_semester1(client):
    r = client.post(f"{BASE_URL}/api/academic/import-curriculum",
                    json={"university": "faminas-bh", "semester": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 9
    assert body["skipped"] == 0
    assert body["university"] == "FAMINAS-BH"

    r2 = client.get(f"{BASE_URL}/api/subjects")
    subs = r2.json()["subjects"]
    curr = [s for s in subs if s.get("source") == "curriculum"]
    assert len(curr) == 9
    for s in curr:
        assert s.get("curriculum_university") == "faminas-bh"
        assert s.get("curriculum_semester") == 1
    criticals = [s for s in curr if s.get("is_critical")]
    assert len(criticals) >= 3
    names = " | ".join(s["name"] for s in criticals)
    assert "Anatômicas" in names
    assert "Tecidos" in names
    assert "Funcionais" in names


def test_import_idempotent(client):
    r = client.post(f"{BASE_URL}/api/academic/import-curriculum",
                    json={"university": "faminas-bh", "semester": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 0
    assert body["skipped"] == 9


def test_import_replace_semester2(client):
    r = client.post(f"{BASE_URL}/api/academic/import-curriculum",
                    json={"university": "faminas-bh", "semester": 2, "replace": True})
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 8
    r2 = client.get(f"{BASE_URL}/api/subjects")
    curr = [s for s in r2.json()["subjects"] if s.get("source") == "curriculum"]
    assert len(curr) == 8
    assert all(s.get("curriculum_semester") == 2 for s in curr)


def test_import_fcmmg(client):
    # Clear curriculum first via replace
    r = client.post(f"{BASE_URL}/api/academic/import-curriculum",
                    json={"university": "fcmmg", "semester": 1, "replace": True})
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 12
    r2 = client.get(f"{BASE_URL}/api/subjects")
    curr = [s for s in r2.json()["subjects"] if s.get("source") == "curriculum"]
    names_critical = {s["name"] for s in curr if s.get("is_critical")}
    assert "Anatomia Humana I" in names_critical
    assert "Bioquímica" in names_critical
    assert "Neuroanatomia Médica" in names_critical


def test_import_invalid_university(client):
    r = client.post(f"{BASE_URL}/api/academic/import-curriculum",
                    json={"university": "usp", "semester": 1})
    assert r.status_code == 400
    assert "não suportada" in r.json().get("detail", "").lower() or "suportada" in r.json().get("detail", "")


def test_import_invalid_semester(client):
    r = client.post(f"{BASE_URL}/api/academic/import-curriculum",
                    json={"university": "faminas-bh", "semester": 99})
    assert r.status_code == 404


# ─── PATCH subject ─────────────────────────────────────────────

def test_patch_subject_is_critical(client):
    # Create manual subject without critical term
    r = client.post(f"{BASE_URL}/api/subjects",
                    json={"name": "Estudo Livre XYZ"})
    assert r.status_code == 200
    sid = r.json()["subject"]["id"]
    assert r.json()["subject"]["is_critical"] is False

    r2 = client.patch(f"{BASE_URL}/api/subjects/{sid}", json={"is_critical": True})
    assert r2.status_code == 200
    assert r2.json()["subject"]["is_critical"] is True

    r3 = client.patch(f"{BASE_URL}/api/subjects/{sid}", json={})
    assert r3.status_code == 400
    assert "atualizar" in r3.json()["detail"].lower()


# ─── Exam + priority + critical bonus ──────────────────────────

def test_exam_has_subject_is_critical_and_priority(client):
    # Create critical subject
    r = client.post(f"{BASE_URL}/api/subjects", json={"name": "Anatomia Teste"})
    crit_id = r.json()["subject"]["id"]
    assert r.json()["subject"]["is_critical"] is True

    # Create non-critical subject
    r = client.post(f"{BASE_URL}/api/subjects", json={"name": "Redação Médica"})
    nc_id = r.json()["subject"]["id"]
    assert r.json()["subject"]["is_critical"] is False

    from datetime import date, timedelta
    exam_date = (date.today() + timedelta(days=3)).isoformat()

    r = client.post(f"{BASE_URL}/api/exams", json={
        "subject_id": crit_id, "name": "Prova Anatomia",
        "exam_date": exam_date, "weight": 1.0,
    })
    assert r.status_code == 200
    assert r.json()["exam"]["subject_is_critical"] is True

    r = client.post(f"{BASE_URL}/api/exams", json={
        "subject_id": nc_id, "name": "Prova Redação",
        "exam_date": exam_date, "weight": 1.0,
    })
    assert r.status_code == 200
    assert r.json()["exam"]["subject_is_critical"] is False

    r = client.get(f"{BASE_URL}/api/priority/today")
    assert r.status_code == 200
    items = r.json()["items"]
    exams = [i for i in items if i["kind"] == "exam"]
    crit = [i for i in exams if "Anatomia" in i["title"]][0]
    nc = [i for i in exams if "Redação" in i["title"]][0]
    assert "prova crítica" in crit["why"].lower()
    assert crit["score"] > nc["score"]


# ─── Pomodoro subject_id ───────────────────────────────────────

def test_pomodoro_start_with_subject(client):
    r = client.post(f"{BASE_URL}/api/subjects", json={"name": "Bioquímica Alfa"})
    sid = r.json()["subject"]["id"]
    assert r.json()["subject"]["is_critical"] is True

    r = client.post(f"{BASE_URL}/api/pomodoro/start", json={"subject_id": sid})
    assert r.status_code == 200
    sess = r.json()["session"]
    assert sess["subject_id"] == sid
    assert sess["subject"] == "Bioquímica Alfa"
    assert sess["subject_meta"]["is_critical"] is True
    return sess["id"], sid


def test_pomodoro_start_invalid_subject(client):
    r = client.post(f"{BASE_URL}/api/pomodoro/start", json={"subject_id": "subj_invalid_xxx"})
    assert r.status_code == 404


def test_pomodoro_by_subject(client):
    # Create 2 subjects
    r1 = client.post(f"{BASE_URL}/api/subjects", json={"name": "Fisiologia Beta"})
    s1 = r1.json()["subject"]["id"]
    r2 = client.post(f"{BASE_URL}/api/subjects", json={"name": "História da Medicina"})
    s2 = r2.json()["subject"]["id"]

    # Start + complete 2 pomodoros
    for sid in (s1, s2):
        r = client.post(f"{BASE_URL}/api/pomodoro/start", json={"subject_id": sid})
        pid = r.json()["session"]["id"]
        rc = client.post(f"{BASE_URL}/api/pomodoro/{pid}/complete",
                         json={"focused_minutes": 25, "completed_cycles": 1})
        assert rc.status_code == 200

    r = client.get(f"{BASE_URL}/api/pomodoro/by-subject")
    assert r.status_code == 200
    items = r.json()["items"]
    by_name = {i["subject"]: i for i in items}
    assert "Fisiologia Beta" in by_name
    assert "História da Medicina" in by_name
    assert by_name["Fisiologia Beta"]["focused_minutes"] >= 25
    assert by_name["Fisiologia Beta"]["is_critical"] is True
    assert by_name["História da Medicina"]["is_critical"] is False


# ─── Regression: legacy flows ──────────────────────────────────

def test_regression_subject_auto_detect_critical(client):
    r = client.post(f"{BASE_URL}/api/subjects", json={"name": "Farmacologia Clínica"})
    assert r.status_code == 200
    assert r.json()["subject"]["is_critical"] is True


def test_regression_pomodoro_without_subject(client):
    r = client.post(f"{BASE_URL}/api/pomodoro/start", json={})
    assert r.status_code == 200
    sess = r.json()["session"]
    assert sess.get("subject_id") is None
    assert sess.get("subject_meta") is None


def test_regression_community_posts(client):
    r = client.get(f"{BASE_URL}/api/community/posts")
    assert r.status_code == 200
    assert "posts" in r.json()


def test_regression_agenda_blocks(client):
    r = client.get(f"{BASE_URL}/api/agenda/blocks")
    assert r.status_code == 200
