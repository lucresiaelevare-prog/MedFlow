"""P0 — Isolamento cross-user do cache da Devolutiva (`kind="exam_feedback"`).

Determinístico: NÃO chama LLM nem provider externo (generator é um fake local).
Mongo local é usado apenas para content_memory, com limpeza por fingerprint.

Cobre:
  • reprodução do comportamento ANTIGO (identidade sem user_id colidia);
  • isolamento A/B/C com parâmetros acadêmicos idênticos;
  • reuso intra-user preservado;
  • robustez de `normalize_topics_key` (sem iteração char-a-char / anagrama).
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

import learning_memory as lm  # noqa: E402
from routes.tutor import exam_feedback_key_fields, normalize_topics_key  # noqa: E402

_LOOP = asyncio.new_event_loop()

SUBJECT = "cardiologia"
TOPICS = "insuficiência cardíaca"
PERIOD = "3"
VARIANT = "grade-high"  # bucket determinístico (nota 70/100 → alto)


def _run(coro):
    """Executa no loop deste módulo com um Motor client criado NESTE loop.

    `learning_memory.db` é religado temporariamente (e restaurado) para não
    depender do loop em que o client global foi criado — evita colisão quando
    vários módulos de teste rodam no mesmo worker do xdist.
    """
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


def _kf(user_id: str, *, subject=SUBJECT, topics=TOPICS, period=PERIOD) -> dict:
    return exam_feedback_key_fields(
        user_id=user_id, subject=subject, weak_topics=topics, period_bucket=period
    )


def _legacy_kf(*, subject=SUBJECT, topics=TOPICS, period=PERIOD) -> dict:
    """Identidade ANTIGA (pré-P0): sem user_id. Mantida como evidência."""
    return {
        "discipline": subject,
        "topic": "exam_feedback",
        "subtopic": normalize_topics_key(topics),
        "period_bucket": period,
    }


def _fp(key_fields: dict) -> str:
    return lm.compute_fingerprint_generic("exam_feedback", key_fields, VARIANT)


async def _wipe(*fps: str) -> None:
    await lm.db.content_memory.delete_many({"fingerprint": {"$in": list(fps)}})


def _fake_gen(marker: str):
    async def gen():
        return {"diagnosis": marker, "focus_areas": [], "questions": []}
    return gen


# ─── ETAPA 1 — evidência da reprodução (comportamento que deve deixar de existir)
def test_repro_legacy_identity_without_user_id_collides():
    """ANTES do P0: sem user_id na chave, A e B produziam o MESMO fingerprint."""
    fp_legacy_a = _fp(_legacy_kf())
    fp_legacy_b = _fp(_legacy_kf())
    assert fp_legacy_a == fp_legacy_b, (
        "reprodução do bug: a identidade legada (sem user_id) é idêntica para "
        "quaisquer dois alunos com os mesmos parâmetros acadêmicos"
    )
    # E a identidade ATUAL não pode mais ter esse formato.
    assert "user_id" in _kf("aluno_a"), "P0 regressão: user_id saiu da identidade"


# ─── ETAPA 6 — fingerprints A/B/C distintos
def test_p0_fingerprint_isolated_per_user():
    a, b, c = f"A_{uuid.uuid4().hex[:6]}", f"B_{uuid.uuid4().hex[:6]}", f"C_{uuid.uuid4().hex[:6]}"
    fp_a, fp_b, fp_c = _fp(_kf(a)), _fp(_kf(b)), _fp(_kf(c))
    assert fp_a != fp_b
    assert fp_b != fp_c
    assert fp_a != fp_c


def test_p0_fingerprint_stable_for_same_user():
    a = f"A_{uuid.uuid4().hex[:6]}"
    assert _fp(_kf(a)) == _fp(_kf(a))


# ─── ETAPA 5 — B nunca recebe o conteúdo exclusivo de A
def test_p0_user_b_never_receives_user_a_content():
    async def run():
        a, b = f"A_{uuid.uuid4().hex[:6]}", f"B_{uuid.uuid4().hex[:6]}"
        kf_a, kf_b = _kf(a), _kf(b)
        fp_a, fp_b = _fp(kf_a), _fp(kf_b)
        await _wipe(fp_a, fp_b)
        try:
            r_a = await lm.remember_or_generate(
                "exam_feedback", kf_a, _fake_gen("CONTEUDO_EXCLUSIVO_ALUNO_A"),
                variant=VARIANT, generator_label="fake", user_id=a,
            )
            assert r_a["source"] == "generated"

            r_b = await lm.remember_or_generate(
                "exam_feedback", kf_b, _fake_gen("CONTEUDO_DO_ALUNO_B"),
                variant=VARIANT, generator_label="fake", user_id=b,
            )
            assert r_b["content"]["payload"]["diagnosis"] != "CONTEUDO_EXCLUSIVO_ALUNO_A", (
                "VAZAMENTO CROSS-USER: B recebeu o conteúdo exclusivo de A"
            )
            assert r_b["content"]["fingerprint"] != r_a["content"]["fingerprint"]
            assert r_b["source"] == "generated"
        finally:
            await _wipe(fp_a, fp_b)
    _run(run())


def test_p0_third_user_also_isolated():
    async def run():
        a, b, c = (f"{p}_{uuid.uuid4().hex[:6]}" for p in ("A", "B", "C"))
        keys = {u: _kf(u) for u in (a, b, c)}
        fps = [_fp(k) for k in keys.values()]
        await _wipe(*fps)
        try:
            results = {}
            for u, k in keys.items():
                results[u] = await lm.remember_or_generate(
                    "exam_feedback", k, _fake_gen(f"CONTEUDO_{u}"),
                    variant=VARIANT, generator_label="fake", user_id=u,
                )
            for u, r in results.items():
                assert r["source"] == "generated"
                assert r["content"]["payload"]["diagnosis"] == f"CONTEUDO_{u}"
            assert len({r["content"]["fingerprint"] for r in results.values()}) == 3
        finally:
            await _wipe(*fps)
    _run(run())


# ─── ETAPA 7 — reuso intra-user preservado
def test_p0_intra_user_reuse_still_works():
    async def run():
        a, b = f"A_{uuid.uuid4().hex[:6]}", f"B_{uuid.uuid4().hex[:6]}"
        kf_a, kf_b = _kf(a), _kf(b)
        fp_a, fp_b = _fp(kf_a), _fp(kf_b)
        await _wipe(fp_a, fp_b)
        try:
            first = await lm.remember_or_generate(
                "exam_feedback", kf_a, _fake_gen("CONTEUDO_EXCLUSIVO_ALUNO_A"),
                variant=VARIANT, generator_label="fake", user_id=a,
            )
            second = await lm.remember_or_generate(
                "exam_feedback", _kf(a), _fake_gen("NAO_DEVE_SER_CHAMADO"),
                variant=VARIANT, generator_label="fake", user_id=a,
            )
            assert first["source"] == "generated"
            assert second["source"] == "reused", "reuso intra-user foi quebrado"
            assert second["content"]["id"] == first["content"]["id"]
            assert second["content"]["payload"]["diagnosis"] == "CONTEUDO_EXCLUSIVO_ALUNO_A"

            third = await lm.remember_or_generate(
                "exam_feedback", kf_b, _fake_gen("CONTEUDO_DO_ALUNO_B"),
                variant=VARIANT, generator_label="fake", user_id=b,
            )
            assert third["source"] == "generated"
            assert third["content"]["id"] != first["content"]["id"]
        finally:
            await _wipe(fp_a, fp_b)
    _run(run())


# ─── ETAPA 8 — normalize_topics_key
@pytest.mark.parametrize("value", [None, "", "   ", [], (), set()])
def test_topics_key_empty_inputs(value):
    assert normalize_topics_key(value) == ""


def test_topics_key_order_insensitive():
    assert normalize_topics_key(["choque", "insuficiência cardíaca"]) == \
        normalize_topics_key(["insuficiência cardíaca", "choque"])


def test_topics_key_accepts_free_text_string():
    assert normalize_topics_key("insuficiência cardíaca, choque") == \
        normalize_topics_key(["insuficiência cardíaca", "choque"])


def test_topics_key_distinct_topics_differ():
    assert normalize_topics_key(["insuficiência cardíaca"]) != normalize_topics_key(["choque"])


def test_topics_key_no_char_iteration_and_no_anagram_collision():
    """P0: string não pode virar multiset de caracteres."""
    k = normalize_topics_key("insuficiência cardíaca")
    assert k == "insuficiência cardíaca"
    assert "," not in k, "string foi quebrada em caracteres (bug char-a-char)"
    assert normalize_topics_key("insuficiência cardíaca") != \
        normalize_topics_key("cardíaca insuficiência")


def test_topics_key_normalizes_whitespace_and_dedupes():
    assert normalize_topics_key("  Choque ,, choque ,\n CHOQUE  ") == "choque"
    assert normalize_topics_key("choque   séptico") == "choque séptico"


def test_topics_key_multiple_separators():
    assert normalize_topics_key("choque; sepse / anemia\npneumonia") == \
        normalize_topics_key(["anemia", "choque", "pneumonia", "sepse"])


# ─── ETAPA 3 — outros kinds mantêm reuso cross-user (economia preservada)
def test_other_kinds_remain_cross_user_shareable():
    key = {"discipline": "cardiologia", "topic": "ic", "period_bucket": "clinico"}
    assert lm.compute_fingerprint_generic("flashcard", key, "default") == \
        lm.compute_fingerprint_generic("flashcard", key, "default")
    assert "user_id" not in key
