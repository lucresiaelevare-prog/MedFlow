"""Iteration 11 — Curriculum router integration.

Validates:
  1) Unit routing: specialty + module + integration signals per curriculum.
  2) Explicit module override preservation.
  3) Endpoint (mode=focused, monkeypatched smart_chat) merges curricular
     instruction into the system prompt and strips 'instruction' from the
     returned curriculum_context.

No real IA calls in this iteration — smart_chat is monkeypatched.
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from curriculum_router import route_curriculum  # noqa: E402
from routes import preceptor_router  # noqa: E402


QA_USER_ID = "qa-student-medflow"


# ── 1. Unit tests on route_curriculum ─────────────────────────────
class TestCurriculumRouterUnit:
    def test_faminas_p1_anatomia_ulnar(self):
        ctx = route_curriculum("nervo ulnar e plexo braquial", "faminas_bh", 1)
        assert ctx["curriculum"] == "faminas_bh"
        assert ctx["period"] == 1
        assert ctx["specialty"] == "anatomia", ctx
        assert ctx["module"] == "Bases Anatômicas do Corpo Humano I", ctx
        # Instruction must weave everything together
        instr = ctx["instruction"]
        assert "FAMINAS BH" in instr
        assert "período 1" in instr
        assert "Bases Anatômicas do Corpo Humano I" in instr
        assert "anatomia" in instr.lower()

    def test_fcmmg_p2_fisiologia_barorreceptor(self):
        ctx = route_curriculum(
            "feedback barorreceptor e débito cardíaco", "fcmmg", 2
        )
        assert ctx["curriculum"] == "fcmmg"
        assert ctx["period"] == 2
        assert ctx["specialty"] == "fisiologia", ctx
        assert ctx["module"] == "Fisiologia Humana I", ctx
        assert "FCMMG" in ctx["instruction"]

    def test_faminas_p3_bioestatistica_confidence_interval(self):
        ctx = route_curriculum(
            "incidência e intervalo de confiança", "faminas_bh", 3
        )
        # 'incidência' hits epidemiologia and 'intervalo' hits bioestatistica —
        # tie-break by keyword order → epidemiologia. Either is acceptable
        # here because the module target is the same 'Fundamentos da Pesquisa
        # Médica: Bioestatística'.
        assert ctx["specialty"] in {"bioestatistica", "epidemiologia"}, ctx
        assert ctx["module"] == "Fundamentos da Pesquisa Médica: Bioestatística", ctx

    def test_system_integration_respiratory(self):
        ctx = route_curriculum(
            "asma e sistema respiratório na criança", "faminas_bh", 1
        )
        assert ctx["system"] == "respiratório"
        assert "ventilatória" in ctx["instruction"]

    def test_unknown_topic_falls_back_to_clinica(self):
        ctx = route_curriculum("dúvida geral", "faminas_bh", 1)
        assert ctx["specialty"] == "clinica_medica"

    # 2. Explicit module override wins
    def test_explicit_module_override_preserved(self):
        ctx = route_curriculum(
            "nervo ulnar",
            "faminas_bh",
            1,
            module="Habilidades Médicas I: Comunicação",
        )
        assert ctx["module"] == "Habilidades Médicas I: Comunicação"


# ── 3. Endpoint: monkeypatch smart_chat and inspect payload ────────
class TestFullReviewCurriculumWiring:
    def test_focused_endpoint_wires_curriculum_and_strips_instruction(self, monkeypatch):
        captured = {}

        async def fake_smart_chat(**kwargs):
            captured.update(kwargs)
            return {
                "text": (
                    '{"topic":"asma","discipline":"Pneumologia",'
                    '"detailed_explanation":{"paragraphs":["p"]},'
                    '"smart_summary":{"one_line":"ok","bullets":["b"]},'
                    '"high_yield_points":["h"],'
                    '"flashcards":[{"front":"q","back":"a"}],'
                    '"practice_questions":[],'
                    '"clinical_case":{"vignette":"","question":"","answer":""},'
                    '"common_mistakes":[],"spaced_review_days":[1,3,7]}'
                ),
                "provider": "groq", "model": "mock", "latency_ms": 3,
            }

        async def fake_insert(doc):
            return None

        class _Coll:
            insert_one = staticmethod(fake_insert)

        class _DB:
            full_reviews = _Coll()

        monkeypatch.setattr(preceptor_router, "smart_chat", fake_smart_chat)
        monkeypatch.setattr(preceptor_router, "db", _DB())

        body = preceptor_router.FullReviewIn(
            topic="asma brônquica e sistema respiratório",
            discipline="Pneumologia",
            mode="focused",
            focus="explanation",
            curriculum="faminas_bh",
            period=1,
        )
        user = {"user_id": QA_USER_ID, "subscription_plan": "free"}
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(preceptor_router.full_review(body, user))
        finally:
            loop.close()

        # System prompt received by LLM must include curriculum info
        system = captured.get("system", "")
        assert "Contexto curricular" in system, system[:400]
        assert "FAMINAS BH" in system
        assert "período 1" in system
        # Specialty for a respiratory topic — anatomia (via 'brônquica'? no)
        # 'sistema respiratório' → system detection; specialty falls back to
        # clinica_medica since none of the keywords match strongly. Accept both.
        assert ("clinica_medica" in system.lower()
                or "pneumolog" in system.lower()
                or "anatomia" in system.lower()), system[:400]
        # Respiratory integration guidance must be woven in
        assert "ventilatória" in system, system[:400]

        # Endpoint response must expose curriculum_context WITHOUT 'instruction'
        ctx = result.get("curriculum_context")
        assert isinstance(ctx, dict), result
        assert "instruction" not in ctx, ctx
        assert ctx["curriculum"] == "faminas_bh"
        assert ctx["period"] == 1
        assert ctx["module"], ctx
        assert ctx["system"] == "respiratório"

        # delivery_mode should be 'focused' (no quota consumed)
        assert result["delivery_mode"] == "focused"

    def test_explicit_module_survives_endpoint(self, monkeypatch):
        captured = {}

        async def fake_smart_chat(**kwargs):
            captured.update(kwargs)
            return {
                "text": '{"topic":"x","discipline":"y",'
                        '"smart_summary":{"one_line":"","bullets":[]},'
                        '"detailed_explanation":{"paragraphs":[]},'
                        '"high_yield_points":[],"flashcards":[],'
                        '"practice_questions":[],'
                        '"clinical_case":{"vignette":"","question":"","answer":""},'
                        '"common_mistakes":[],"spaced_review_days":[]}',
                "provider": "groq", "model": "mock", "latency_ms": 1,
            }

        async def fake_insert(doc):
            return None

        class _Coll:
            insert_one = staticmethod(fake_insert)

        class _DB:
            full_reviews = _Coll()

        monkeypatch.setattr(preceptor_router, "smart_chat", fake_smart_chat)
        monkeypatch.setattr(preceptor_router, "db", _DB())

        override = "Integração Curricular II"
        body = preceptor_router.FullReviewIn(
            topic="dor abdominal",
            discipline="Clínica",
            mode="focused",
            focus="explanation",
            curriculum="fcmmg",
            period=2,
            curriculum_module=override,
        )
        user = {"user_id": QA_USER_ID, "subscription_plan": "free"}
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(preceptor_router.full_review(body, user))
        finally:
            loop.close()

        assert result["curriculum_context"]["module"] == override
        assert override in captured["system"]
