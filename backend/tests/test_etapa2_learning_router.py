"""ETAPA 2 — Aprender Hoje integrado ao `ai_router`.

Determinístico: `ai_router.smart_chat` é substituído por um fake local.
NENHUM provider externo é chamado.

Valida:
  • generate_via_llm usa o ai_router (tier structured) e não LlmChat direto;
  • system = MEDFLOW_CONTENT_POLICY + LEARNING_CONTENT_POLICY + prompt do kind,
    nessa ordem;
  • formato/estrutura por kind preservados (os 7 kinds do Aprender Hoje);
  • parsing de JSON, cercas de código e fallback {"raw": ...} preservados;
  • cache/single-flight de request_content preservado;
  • fallback/erros do router propagados (AIRouterError).
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

import ai_router  # noqa: E402
import learning_memory as lm  # noqa: E402
from content_policy import MEDFLOW_CONTENT_POLICY  # noqa: E402

LEARNING_KINDS = [
    "question", "flashcard", "summary", "explanation",
    "mindmap", "review", "clinical_case",
]

_LOOP = asyncio.new_event_loop()


def _run(coro):
    async def wrapper():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        original_db = lm.db
        lm.db = client[os.environ["DB_NAME"]]
        try:
            return await coro
        finally:
            lm.db = original_db
            client.close()

    return _LOOP.run_until_complete(wrapper())


class _FakeRouter:
    """Captura as chamadas e devolve um texto controlado."""

    def __init__(self, text='{"bullets":["a","b","c"]}'):
        self.text = text
        self.calls: list[dict] = []

    async def __call__(self, *, system, user_msg, tier="fast", temperature=0.3,
                       max_tokens=800, prefer=None, response_format=None):
        self.calls.append({
            "system": system, "user_msg": user_msg, "tier": tier,
            "temperature": temperature, "max_tokens": max_tokens, "prefer": prefer,
        })
        return {"text": self.text, "provider": "fake", "model": "fake-1",
                "latency_ms": 1, "tier": tier, "attempts": []}


def _with_fake_router(fake):
    """Substitui smart_chat no módulo ai_router (importado sob demanda)."""
    original = ai_router.smart_chat
    ai_router.smart_chat = fake
    return original


def _gen(kind="summary", *, text='{"bullets":["a","b","c"]}'):
    fake = _FakeRouter(text)
    original = _with_fake_router(fake)
    try:
        payload = _run(lm.generate_via_llm(kind, "Cardiologia", "Insuficiência cardíaca", None, "clinico"))
    finally:
        ai_router.smart_chat = original
    return payload, fake


# ─── Arquitetura: passa pelo router ─────────────────────────────────
def test_generate_via_llm_uses_ai_router():
    payload, fake = _gen()
    assert len(fake.calls) == 1, "generate_via_llm não passou pelo ai_router"
    assert payload == {"bullets": ["a", "b", "c"]}


def test_router_tier_and_tuning():
    _, fake = _gen()
    call = fake.calls[0]
    assert call["tier"] == "structured"
    assert call["temperature"] == lm.LEARNING_ROUTER_TEMPERATURE
    assert call["max_tokens"] == lm.LEARNING_ROUTER_MAX_TOKENS


def test_no_direct_provider_call_in_learning_memory():
    """Nenhuma chamada direta a LlmChat/EMERGENT_LLM_KEY no módulo."""
    src = open(lm.__file__, encoding="utf-8").read()
    assert "LlmChat" not in src, "learning_memory ainda instancia LlmChat direto"
    assert "EMERGENT_LLM_KEY" not in src, "learning_memory ainda lê a chave do provider"
    assert "from ai_router import smart_chat" in src


# ─── Composição do system prompt ────────────────────────────────────
def test_system_prompt_composition_order():
    _, fake = _gen("question")
    system = fake.calls[0]["system"]
    assert MEDFLOW_CONTENT_POLICY in system, "política central ausente no Aprender Hoje"
    assert lm.LEARNING_CONTENT_POLICY in system, "política específica do Learning ausente"
    i_policy = system.index(MEDFLOW_CONTENT_POLICY)
    i_learning = system.index(lm.LEARNING_CONTENT_POLICY)
    i_kind = system.index("questão de múltipla escolha")
    assert i_policy < i_learning < i_kind, "ordem da composição incorreta"


def test_policy_includes_unknown_entity_rule():
    _, fake = _gen("summary")
    system = fake.calls[0]["system"].lower()
    assert "não for reconhecido" in system or "nao for reconhecido" in system


@pytest.mark.parametrize("kind,marker", [
    ("question", "questão de múltipla escolha"),
    ("flashcard", "flashcard"),
    ("summary", "resumo em bullets"),
    ("explanation", "2 a 5 parágrafos"),
    ("mindmap", "mapa mental"),
    ("review", "roteiro de revisão"),
    ("clinical_case", "caso clínico"),
])
def test_kind_specific_prompt_preserved(kind, marker):
    _, fake = _gen(kind)
    assert marker in fake.calls[0]["system"], f"prompt do kind {kind} foi alterado"


def test_unknown_kind_falls_back_to_summary_prompt():
    _, fake = _gen("kind_inexistente")
    assert "resumo em bullets" in fake.calls[0]["system"]


def test_build_learning_system_prompt_helper():
    out = lm.build_learning_system_prompt("PROMPT_DO_KIND")
    assert out.index(MEDFLOW_CONTENT_POLICY) < out.index(lm.LEARNING_CONTENT_POLICY) \
        < out.index("PROMPT_DO_KIND")


# ─── Contexto pedagógico preservado no user prompt ───────────────────
def test_user_prompt_keeps_pedagogical_context():
    fake = _FakeRouter()
    original = _with_fake_router(fake)
    try:
        _run(lm.generate_via_llm("summary", "Cardiologia", "IC", "IC descompensada", "clinico"))
    finally:
        ai_router.smart_chat = original
    msg = fake.calls[0]["user_msg"]
    assert "Disciplina: Cardiologia" in msg
    assert "Tema: IC" in msg
    assert "Subtema: IC descompensada" in msg
    assert "clinico" in msg


def test_user_prompt_omits_subtopic_when_absent():
    _, fake = _gen()
    assert "Subtema:" not in fake.calls[0]["user_msg"]


# ─── Parsing / formato estruturado preservado ────────────────────────
def test_json_parsing_preserved():
    payload, _ = _gen("question", text='{"stem":"s","options":["A","B","C","D"],"correct_index":0,"explanation":"e"}')
    assert payload["options"] == ["A", "B", "C", "D"]
    assert payload["correct_index"] == 0


def test_code_fences_are_stripped():
    payload, _ = _gen("summary", text='```json\n{"bullets":["x","y","z"]}\n```')
    assert payload == {"bullets": ["x", "y", "z"]}


def test_invalid_json_falls_back_to_raw():
    payload, _ = _gen("summary", text="isso não é json")
    assert payload == {"raw": "isso não é json"}


def test_empty_text_falls_back_to_raw():
    payload, _ = _gen("summary", text="")
    assert payload == {"raw": ""}


# ─── Erro / fallback do router propagado ─────────────────────────────
def test_router_error_propagates():
    async def boom(**kwargs):
        raise ai_router.AIRouterError("todos os providers falharam (structured): []")

    original = _with_fake_router(boom)
    try:
        with pytest.raises(ai_router.AIRouterError):
            _run(lm.generate_via_llm("summary", "Cardio", "IC", None, "clinico"))
    finally:
        ai_router.smart_chat = original


# ─── Cache preservado no caminho request_content ─────────────────────
def test_request_content_cache_miss_then_hit_through_router():
    async def run():
        discipline = f"etapa2_{uuid.uuid4().hex[:8]}"
        key_fields = {"discipline": discipline, "topic": "ic", "subtopic": "", "period_bucket": "clinico"}
        fp = lm.compute_fingerprint_generic("summary", key_fields, "default")
        await lm.db.content_memory.delete_many({"fingerprint": fp})
        try:
            first = await lm.request_content("u_etapa2", "summary", discipline, "ic", None, 5)
            second = await lm.request_content("u_etapa2", "summary", discipline, "ic", None, 5)
            return first, second, fp
        finally:
            await lm.db.content_memory.delete_many({"fingerprint": fp})
            await lm.db.student_content_events.delete_many({"user_id": "u_etapa2"})

    fake = _FakeRouter()
    original = _with_fake_router(fake)
    try:
        first, second, _ = _run(run())
    finally:
        ai_router.smart_chat = original

    assert first["source"] == "generated"
    assert second["source"] == "reused", "cache do Aprender Hoje foi quebrado"
    assert len(fake.calls) == 1, f"router chamado {len(fake.calls)}x — cache não evitou a 2ª geração"
    assert second["content"]["id"] == first["content"]["id"]


def test_request_content_generator_label_reflects_router():
    async def run():
        discipline = f"etapa2_{uuid.uuid4().hex[:8]}"
        key_fields = {"discipline": discipline, "topic": "ic", "subtopic": "", "period_bucket": "clinico"}
        fp = lm.compute_fingerprint_generic("flashcard", key_fields, "default")
        await lm.db.content_memory.delete_many({"fingerprint": fp})
        try:
            return await lm.request_content("u_etapa2b", "flashcard", discipline, "ic", None, 5)
        finally:
            await lm.db.content_memory.delete_many({"fingerprint": fp})
            await lm.db.student_content_events.delete_many({"user_id": "u_etapa2b"})

    fake = _FakeRouter('{"front":"f","back":"b"}')
    original = _with_fake_router(fake)
    try:
        res = _run(run())
    finally:
        ai_router.smart_chat = original
    assert res["content"]["generator"] == "ai:router-structured"


def test_request_content_single_flight_still_dedupes():
    async def run():
        discipline = f"etapa2_{uuid.uuid4().hex[:8]}"
        key_fields = {"discipline": discipline, "topic": "ic", "subtopic": "", "period_bucket": "clinico"}
        fp = lm.compute_fingerprint_generic("summary", key_fields, "default")
        await lm.db.content_memory.delete_many({"fingerprint": fp})
        try:
            tasks = [lm.request_content(f"u_sf_{i}", "summary", discipline, "ic", None, 5) for i in range(20)]
            return await asyncio.gather(*tasks)
        finally:
            await lm.db.content_memory.delete_many({"fingerprint": fp})
            await lm.db.student_content_events.delete_many({"discipline": lm._slug(discipline)})

    class _SlowFake(_FakeRouter):
        async def __call__(self, **kwargs):
            await asyncio.sleep(0.05)
            return await super().__call__(**kwargs)

    fake = _SlowFake()
    original = _with_fake_router(fake)
    try:
        results = _run(run())
    finally:
        ai_router.smart_chat = original

    assert len(fake.calls) == 1, f"stampede: router chamado {len(fake.calls)}x"
    assert sum(1 for r in results if r["source"] == "generated") == 1
    assert sum(1 for r in results if r["source"] == "reused") == 19


def test_request_content_rejects_invalid_kind():
    with pytest.raises(ValueError):
        _run(lm.request_content("u", "kind_invalido", "Cardio", "ic", None, 5))
