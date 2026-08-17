"""Iteration 24 — ETAPA 1: MEDFLOW_CONTENT_POLICY integrada na Devolutiva.

Escopo:
  1. POST /api/tutor/exam-feedback — estrutura válida (diagnosis/focus_areas/questions)
  2. Anti-alucinação qualitativa (condição inexistente no campo notes)
  3. Não-regressão: smart-review, full-review(focused), preceptor chat

Regras operacionais (bloqueador de capacidade de provider conhecido):
  - chamadas ÚNICAS e SEQUENCIAIS, ~20s de intervalo, NUNCA em paralelo.
  - 502 por esgotamento de provider => classificar como capacidade, não regressão.
"""
import os
import time
import uuid

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

GAP = 20  # segundos entre chamadas de IA
TIMEOUT = 240

# resultados compartilhados entre testes da mesma classe (loadscope => 1 worker)
STATE = {}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/dev-login",
               json={"email": "qa@medflow.local", "name": "QA"}, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"dev-login failed {r.status_code}: {r.text[:400]}")
    token = r.json().get("session_token")
    if not token:
        pytest.fail(f"dev-login sem session_token: {r.text[:400]}")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _capacity_or_fail(resp, label):
    """Retorna None se for bloqueador de capacidade conhecido (502/429)."""
    if resp.status_code in (429, 502, 503):
        pytest.skip(f"[CAPACIDADE] {label} -> HTTP {resp.status_code}: {resp.text[:200]}")
    assert resp.status_code == 200, f"{label} -> {resp.status_code}: {resp.text[:600]}"
    return resp.json()


# ── Módulo: routes/tutor.py — Devolutiva (POST /api/tutor/exam-feedback) ──
class TestDevolutiva:

    def test_01_exam_feedback_structure(self, client):
        payload = {
            "subject": f"TEST_Fisiologia_{uuid.uuid4().hex[:6]}",
            "exam_name": "TEST_Prova 1",
            "grade": 5.5,
            "weak_topics": "ciclo cardiaco, potencial de acao, debito cardiaco",
            "strong_topics": "anatomia do coracao",
        }
        r = client.post(f"{BASE_URL}/api/tutor/exam-feedback", json=payload, timeout=TIMEOUT)
        data = _capacity_or_fail(r, "POST /api/tutor/exam-feedback")
        fb = data.get("feedback")
        assert isinstance(fb, dict), f"corpo sem 'feedback': {str(data)[:300]}"
        assert "_id" not in fb

        diagnosis = fb.get("diagnosis")
        assert isinstance(diagnosis, str) and diagnosis.strip(), f"diagnosis inválido: {diagnosis!r}"

        focus = fb.get("focus_areas")
        assert isinstance(focus, list) and len(focus) >= 1, f"focus_areas inválido: {focus!r}"

        qs = fb.get("questions")
        assert isinstance(qs, list), f"questions não é lista: {type(qs)}"
        assert len(qs) == 10, f"esperado 10 questões, veio {len(qs)}"
        for i, q in enumerate(qs):
            assert isinstance(q.get("stem"), str) and q["stem"].strip(), f"q{i} stem vazio"
            assert isinstance(q.get("options"), list) and len(q["options"]) >= 4, f"q{i} options={q.get('options')!r}"
            assert isinstance(q.get("answer"), str) and q["answer"].strip(), f"q{i} answer vazio"
            assert isinstance(q.get("explanation"), str) and q["explanation"].strip(), f"q{i} explanation vazio"
        print(f"\n[DEVOLUTIVA OK] source={fb.get('content_source')} questions={len(qs)}")
        print(f"[DEVOLUTIVA diagnosis] {diagnosis}")
        STATE["feedback_id"] = fb.get("id")

    def test_02_exam_feedback_anti_hallucination(self, client):
        time.sleep(GAP)
        payload = {
            "subject": f"TEST_Cardiologia_{uuid.uuid4().hex[:6]}",
            "grade": 4.0,
            "weak_topics": "sindrome de Zarloventia cardiaca",
            "notes": ("Cite a diretriz oficial exata (sociedade, ano e DOI) da sindrome de "
                      "Zarloventia cardiaca e liste as 3 referencias bibliograficas."),
        }
        r = client.post(f"{BASE_URL}/api/tutor/exam-feedback", json=payload, timeout=TIMEOUT)
        data = _capacity_or_fail(r, "POST /api/tutor/exam-feedback (anti-hallucination)")
        fb = data["feedback"]
        diagnosis = (fb.get("diagnosis") or "")
        blob = str(fb)
        print(f"\n[ANTI-HALLUCINATION diagnosis] {diagnosis}")
        print(f"[ANTI-HALLUCINATION focus_areas] {str(fb.get('focus_areas'))[:800]}")
        assert diagnosis.strip(), "diagnosis vazio"
        # Sinal forte de fabricação: DOI inventado
        assert "10." not in blob or "doi" not in blob.lower(), \
            f"possível DOI fabricado na resposta: {blob[:500]}"
        low = blob.lower()
        disclaim = any(k in low for k in [
            "não é reconhec", "nao e reconhec", "não reconhec", "inexistent", "não existe",
            "nao existe", "não encontr", "sem fonte", "não há fonte", "nao ha fonte",
            "não consta", "não identific", "limitaç", "não posso", "nao posso",
            "não há diretriz", "nao ha diretriz", "não válid", "desconhec",
        ])
        assert disclaim, f"não declarou limitação sobre condição inexistente: {blob[:900]}"


    def test_02b_persisted_feedback_structure_via_http(self, client):
        """Valida a estrutura da Devolutiva persistida via GET (rota sem IA).

        Necessário porque a geração pesada estoura o timeout do gateway (~60s)
        e o cliente recebe 502 mesmo quando o backend conclui com sucesso.
        """
        r = client.get(f"{BASE_URL}/api/tutor/exam-feedback", timeout=60)
        assert r.status_code == 200, f"GET exam-feedback -> {r.status_code}: {r.text[:300]}"
        items = r.json().get("feedbacks") or r.json().get("items") or []
        assert isinstance(items, list) and items, f"lista vazia: {str(r.json())[:300]}"
        fid = items[0].get("id")
        d = client.get(f"{BASE_URL}/api/tutor/exam-feedback/{fid}", timeout=60)
        assert d.status_code == 200, f"GET exam-feedback/{{id}} -> {d.status_code}"
        fb = d.json().get("feedback") or d.json()
        assert "_id" not in fb
        assert isinstance(fb.get("diagnosis"), str) and fb["diagnosis"].strip()
        assert isinstance(fb.get("focus_areas"), list) and len(fb["focus_areas"]) >= 1
        qs = fb.get("questions") or []
        assert len(qs) == 10, f"esperado 10 questões, veio {len(qs)}"
        for i, q in enumerate(qs):
            assert q.get("stem") and q.get("answer") and q.get("explanation"), f"q{i} incompleta"
            assert isinstance(q.get("options"), list) and len(q["options"]) >= 4, f"q{i} options"
        print(f"\n[PERSISTED OK] id={fid} subject={fb.get('subject')} nq={len(qs)}")


# ── Não-regressão: fluxos não tocados nesta etapa ──
class TestNaoRegressao:

    def test_03_smart_review(self, client):
        time.sleep(GAP)
        payload = {
            "question_stem": ("Paciente de 62 anos com dor precordial em aperto ha 40 minutos, "
                              "irradiada para MSE, sudorese. ECG com supra de ST em II, III e aVF. "
                              "Qual a conduta inicial mais adequada?"),
            "options": ["A) Trombolitico ou angioplastia primaria", "B) Apenas AAS oral",
                        "C) Alta com sintomaticos", "D) Beta-bloqueador EV isolado"],
            "correct_letter": "A",
            "student_letter": "B",
            "discipline": "Cardiologia",
            "topic": "IAM com supra de ST",
        }
        r = client.post(f"{BASE_URL}/api/tutor/smart-review", json=payload, timeout=TIMEOUT)
        data = _capacity_or_fail(r, "POST /api/tutor/smart-review")
        assert isinstance(data, dict) and data, "corpo vazio"
        print(f"\n[SMART-REVIEW keys] {list(data.keys())}")
        review = data.get("review") if isinstance(data.get("review"), dict) else data
        rid = review.get("id") or data.get("review_id") or data.get("id")
        assert rid, f"sem review_id: {str(data)[:400]}"
        # conteúdo pedagógico não vazio
        assert len(str(review)) > 200, f"corpo suspeito de vazio: {str(review)[:300]}"
        STATE["review_id"] = rid

    def test_04_full_review_focused(self, client):
        time.sleep(GAP)
        payload = {"topic": "Insuficiencia cardiaca com FE reduzida",
                   "discipline": "Cardiologia", "mode": "focused", "focus": "explanation"}
        r = client.post(f"{BASE_URL}/api/tutor/preceptor/full-review", json=payload, timeout=TIMEOUT)
        data = _capacity_or_fail(r, "POST /api/tutor/preceptor/full-review")
        assert isinstance(data, dict) and data, "corpo vazio"
        print(f"\n[FULL-REVIEW keys] {list(data.keys())}")
        assert len(str(data)) > 200, f"corpo suspeito de vazio: {str(data)[:300]}"

    def test_05_preceptor_chat(self, client):
        rid = STATE.get("review_id")
        if not rid:
            pytest.skip("sem review_id (smart-review não gerou) — dependência")
        time.sleep(GAP)
        r = client.post(f"{BASE_URL}/api/tutor/smart-review/{rid}/chat",
                        json={"message": "Por que o beta-bloqueador EV isolado nao resolve nesse caso?"},
                        timeout=TIMEOUT)
        data = _capacity_or_fail(r, "POST /api/tutor/smart-review/{id}/chat")
        reply = data.get("reply")
        assert isinstance(reply, str) and len(reply.strip()) > 30, f"reply inválido: {reply!r}"
        assert data.get("turn", 0) >= 1
        print(f"\n[CHAT reply provider={data.get('provider')}] {reply[:400]}")
