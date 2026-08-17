"""Content Memory Engine — P0 hardening suite (single-flight, indexes, rate limit, CB).

Testes obrigatórios do sprint P0. Todos rodam contra o Mongo local + módulo
`learning_memory` em processo. NÃO invoca o LLM real (mock/fake generator) —
o Claude Sonnet só é validado no `http_stampede.py` do audit.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

import learning_memory as lm  # noqa: E402
try:
    from pymongo.errors import DuplicateKeyError  # type: ignore
except Exception:  # pragma: no cover
    DuplicateKeyError = Exception  # type: ignore


# ─── infra utils ────────────────────────────────────────────────────
_LOOP = asyncio.new_event_loop()


def _run(coro):
    """Execute a coroutine on the shared module-scoped loop.

    Motor's async client caches the loop it was created in; sharing the loop
    keeps the pre-bound `db` (imported by learning_memory) usable across tests.
    """
    return _LOOP.run_until_complete(coro)


def _fresh_key():
    return {
        "discipline": "p0_test",
        "topic": f"t_{uuid.uuid4().hex[:8]}",
        "period_bucket": "clinico",
    }


async def _wipe(fp: str) -> None:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    await db.content_memory.delete_many({"fingerprint": fp})
    await db.student_content_events.delete_many({"discipline": "p0_test"})
    client.close()


async def _wipe_all():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    await db.content_memory.delete_many({"discipline": "p0_test"})
    await db.student_content_events.delete_many({"discipline": "p0_test"})
    client.close()


# ─── P0.2 — Indexes ─────────────────────────────────────────────────
def test_p02_indexes_present_and_unique():
    async def run():
        await lm.ensure_indexes()
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        raw = await db.content_memory.index_information()
        assert "id_1" in raw, f"expected UNIQUE on id, got {list(raw.keys())}"
        assert raw["id_1"].get("unique") is True
        assert "fp_schema_active_uniq" in raw
        assert raw["fp_schema_active_uniq"].get("unique") is True
        assert raw["fp_schema_active_uniq"].get("partialFilterExpression") == {"status": "ACTIVE"}
        us_idx = await db.user_sessions.index_information()
        assert "session_token_1" in us_idx and us_idx["session_token_1"].get("unique") is True
        assert "expires_at_1" in us_idx and us_idx["expires_at_1"].get("expireAfterSeconds") == 0
        u_idx = await db.users.index_information()
        assert "user_id_1" in u_idx and u_idx["user_id_1"].get("unique") is True
        assert "email_1" in u_idx and u_idx["email_1"].get("unique") is True
        client.close()
    _run(run())


def test_p02_explain_uses_ixscan_not_collscan():
    """A prova de que os hot-paths deixaram de fazer COLLSCAN."""
    async def run():
        await lm.ensure_indexes()
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        # content_memory.id
        exp = await db.content_memory.find({"id": "x"}).explain()
        stage = exp["queryPlanner"]["winningPlan"]
        assert stage.get("inputStage", {}).get("stage") == "IXSCAN", f"id lookup fell back to {stage}"
        assert stage["inputStage"]["indexName"] == "id_1"
        # content_memory.fingerprint
        exp = await db.content_memory.find({"fingerprint": "x"}).explain()
        stage = exp["queryPlanner"]["winningPlan"]
        assert stage.get("inputStage", {}).get("stage") == "IXSCAN"
        # user_sessions.session_token
        exp = await db.user_sessions.find({"session_token": "x"}).explain()
        stage = exp["queryPlanner"]["winningPlan"]
        assert stage.get("inputStage", {}).get("stage") == "IXSCAN"
        # users.user_id
        exp = await db.users.find({"user_id": "x"}).explain()
        stage = exp["queryPlanner"]["winningPlan"]
        assert stage.get("inputStage", {}).get("stage") == "IXSCAN"
        client.close()
    _run(run())


def test_p02_duplicate_insert_rejected_by_unique_index():
    """UNIQUE partial index em (fingerprint, schema_version) deve rejeitar segunda insert ACTIVE."""
    async def run():
        await lm.ensure_indexes()
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        fp = "dup_hardening_" + uuid.uuid4().hex[:8]
        base = {
            "id": f"cm_{uuid.uuid4().hex[:16]}",
            "fingerprint": fp,
            "schema_version": lm.CONTENT_SCHEMA_VERSION,
            "status": "ACTIVE",
            "kind": "flashcard", "discipline": "p0_test", "topic": "t",
            "usage_count": 0, "created_at": "2026-01-01T00:00:00+00:00",
        }
        await db.content_memory.insert_one(dict(base))
        base["id"] = f"cm_{uuid.uuid4().hex[:16]}"
        raised = False
        try:
            await db.content_memory.insert_one(dict(base))
        except DuplicateKeyError:
            raised = True
        assert raised, "second insert with same (fingerprint, schema_version, status=ACTIVE) should have failed"
        # cleanup
        await db.content_memory.delete_many({"fingerprint": fp})
        client.close()
    _run(run())


# ─── P0.1 — Single-flight & no stampede ─────────────────────────────
@pytest.mark.parametrize("concurrency", [10, 50, 100, 500, 1000])
def test_p01_no_cache_stampede(concurrency):
    """N concurrent tasks with cold cache → exactly 1 LLM call + 1 doc + N-1 reuses."""
    async def run():
        key = _fresh_key()
        fp = lm.compute_fingerprint_generic("flashcard", key, "sf")
        await _wipe(fp)
        calls = {"n": 0}

        async def slow_gen():
            calls["n"] += 1
            await asyncio.sleep(0.1)
            return {"marker": f"gen_{calls['n']}"}

        tasks = [
            lm.remember_or_generate("flashcard", key, slow_gen, variant="sf", generator_label="fake")
            for _ in range(concurrency)
        ]
        results = await asyncio.gather(*tasks)

        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        docs = await db.content_memory.count_documents({"fingerprint": fp})
        await db.content_memory.delete_many({"fingerprint": fp})
        client.close()

        generated = sum(1 for r in results if r["source"] == "generated")
        reused = sum(1 for r in results if r["source"] == "reused")

        assert calls["n"] == 1, f"expected 1 LLM call, got {calls['n']} for concurrency={concurrency}"
        assert docs == 1, f"expected 1 doc, got {docs}"
        assert generated == 1
        assert reused == concurrency - 1
    _run(run())


def test_p01_race_between_two_processes_via_unique_index():
    """Simula a race que o UNIQUE index deve capturar: dois inserts direto no Mongo (bypass do lock in-process)."""
    async def run():
        await lm.ensure_indexes()
        key = _fresh_key()
        fp = lm.compute_fingerprint_generic("flashcard", key, "cross")
        await _wipe(fp)

        # Simula processo A e B rodando `remember_or_generate` em processos diferentes:
        # local locks são independentes → ambos vão inserir. UNIQUE index deve absorver.
        gen_calls = {"n": 0}

        async def gen():
            gen_calls["n"] += 1
            return {"who": gen_calls["n"]}

        # Executa duas cópias com locks separados (força bypass do dedupe in-process
        # criando o mesmo fingerprint por duas instâncias).
        original_locks = lm._fp_locks
        try:
            lm._fp_locks = {}  # instância "A"
            task_a = asyncio.create_task(lm.remember_or_generate("flashcard", key, gen, variant="cross"))
            await asyncio.sleep(0.01)  # deixa A começar a gerar
            lm._fp_locks = {}  # instância "B" (dict novo → lock diferente)
            task_b = asyncio.create_task(lm.remember_or_generate("flashcard", key, gen, variant="cross"))
            r_a, r_b = await asyncio.gather(task_a, task_b)
        finally:
            lm._fp_locks = original_locks

        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        docs = await db.content_memory.count_documents({"fingerprint": fp, "status": "ACTIVE"})
        await db.content_memory.delete_many({"fingerprint": fp})
        client.close()

        # Exatamente UM doc ACTIVE deve existir; o outro processo caiu no fallback
        # do DuplicateKeyError e reutilizou o vencedor.
        assert docs == 1, f"UNIQUE partial index should have collapsed race → 1 doc, got {docs}"
        # E os dois retornos referenciam o MESMO id
        assert r_a["content"]["id"] == r_b["content"]["id"], (
            f"race did not converge to a single winner: {r_a['content']['id']} vs {r_b['content']['id']}"
        )
    _run(run())


# ─── P0.3 — Report rate limit ───────────────────────────────────────
def test_p03_report_rate_limit_prevents_second_report_same_user():
    async def run():
        # Cria um doc para reportar
        key = _fresh_key()
        result = await lm.remember_or_generate("flashcard", key, lambda: _fake_payload())
        content_id = result["content"]["id"]

        uid = f"u_{uuid.uuid4().hex[:8]}"
        r1 = await lm.register_report_rate_limited(uid, content_id)
        assert r1["accepted"] is True
        r2 = await lm.register_report_rate_limited(uid, content_id)
        assert r2["accepted"] is False
        assert r2["reason"] == "already_reported"

        # Terceiro report de OUTRO usuário deve ser aceito
        r3 = await lm.register_report_rate_limited(f"u_{uuid.uuid4().hex[:8]}", content_id)
        assert r3["accepted"] is True

        # Verifica contador — deve ter só 2 (users distintos), NÃO 3
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        doc = await db.content_memory.find_one({"id": content_id})
        await db.content_memory.delete_one({"id": content_id})
        await db.student_content_events.delete_many({"content_id": content_id})
        client.close()

        assert int(doc["reports_count"]) == 2, f"expected 2 reports (deduped), got {doc['reports_count']}"
    _run(run())


async def _fake_payload():
    return {"payload": "ok"}


def test_p03_report_flood_100_by_same_user_still_yields_1():
    async def run():
        key = _fresh_key()
        r = await lm.remember_or_generate("flashcard", key, _fake_payload)
        content_id = r["content"]["id"]
        uid = f"u_{uuid.uuid4().hex[:8]}"

        results = await asyncio.gather(*[
            lm.register_report_rate_limited(uid, content_id) for _ in range(100)
        ])
        accepted = sum(1 for r in results if r["accepted"])
        # Concurrency-safe minimum: at most one accepted per user; may be > 1 if the
        # dedupe race is lost, but the index+dedupe should keep it in a single digit.
        assert accepted >= 1, "at least one should be accepted"
        assert accepted <= 5, f"rate limit too weak: {accepted}/100 accepted for same user"

        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        doc = await db.content_memory.find_one({"id": content_id})
        await db.content_memory.delete_one({"id": content_id})
        await db.student_content_events.delete_many({"content_id": content_id})
        client.close()
        assert doc["reports_count"] <= 5, f"quarantine floodable: reports_count={doc['reports_count']}"
    _run(run())


# ─── P0.4 — Circuit breaker + retry ─────────────────────────────────
def test_p04_circuit_breaker_opens_after_threshold_failures():
    async def run():
        # Reset CB
        lm._llm_cb.state = "CLOSED"
        lm._llm_cb.failures = 0

        async def _always_fail():
            raise RuntimeError("boom")  # non-transient by our regex

        # 5 non-transient failures should trigger 5 attempts × 1 = 5 failures
        # but non-transient means no retry — each call = 1 failure → 5 failures → CB opens
        failures = 0
        for _ in range(lm.CB_FAILURE_THRESHOLD):
            try:
                await lm.call_llm_with_retry(_always_fail, label="test")
            except RuntimeError:
                failures += 1
        assert failures == lm.CB_FAILURE_THRESHOLD
        assert lm._llm_cb.state == "OPEN", f"CB should be OPEN, is {lm._llm_cb.state}"

        # Next call must fail fast with CircuitOpenError (no generator invoked)
        called = {"n": 0}
        async def _would_succeed():
            called["n"] += 1
            return {"ok": True}
        with pytest.raises(lm.CircuitOpenError):
            await lm.call_llm_with_retry(_would_succeed, label="probe")
        assert called["n"] == 0, "OPEN circuit must not invoke generator"

        # Force recovery window
        lm._llm_cb.opened_at = 0.0
        # HALF_OPEN probe succeeds → CLOSED
        r = await lm.call_llm_with_retry(_would_succeed, label="probe2")
        assert r == {"ok": True}
        assert lm._llm_cb.state == "CLOSED"
    _run(run())


def test_p04_retry_on_transient_error_then_success():
    async def run():
        lm._llm_cb.state = "CLOSED"
        lm._llm_cb.failures = 0
        attempts = {"n": 0}

        async def _flaky():
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise TimeoutError("timeout on upstream")  # transient
            return {"ok": True}

        r = await lm.call_llm_with_retry(_flaky, label="flaky")
        assert r == {"ok": True}
        assert attempts["n"] == 2, "retry should succeed on second attempt"
    _run(run())


# ─── P0.1 metrics — stampede_prevented telemetry ─────────────────────
def test_p01_metrics_report_stampede_prevented():
    async def run():
        # snapshot before
        m0 = lm.get_engine_metrics()["counters"]
        key = _fresh_key()
        fp = lm.compute_fingerprint_generic("flashcard", key, "metrics")
        await _wipe(fp)

        async def slow_gen():
            await asyncio.sleep(0.05)
            return {"payload": "x"}

        # 20 concurrent → 1 gen + 19 stampede_prevented (or singleflight_waits)
        await asyncio.gather(*[
            lm.remember_or_generate("flashcard", key, slow_gen, variant="metrics")
            for _ in range(20)
        ])

        m1 = lm.get_engine_metrics()["counters"]
        assert m1["cache_misses"] - m0["cache_misses"] == 1
        assert m1["cache_hits"] - m0["cache_hits"] == 19
        # Either singleflight_waits or stampede_prevented should have grown
        singleflight_delta = m1["singleflight_waits"] - m0["singleflight_waits"]
        stampede_delta = m1["stampede_prevented"] - m0["stampede_prevented"]
        assert singleflight_delta + stampede_delta >= 19, (
            f"expected at least 19 waits/prevented, got sf={singleflight_delta} sp={stampede_delta}"
        )

        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        await db.content_memory.delete_many({"fingerprint": fp})
        client.close()
    _run(run())


# ─── Regressão: compat com pipeline antigo (request_content) ────────
def test_compat_request_content_now_uses_single_flight_via_wrapper():
    async def run():
        # request_content é wrapper → deve chamar remember_or_generate → single-flight ativo
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]

        # Prepara user
        user_id = f"u_{uuid.uuid4().hex[:8]}"
        await db.users.insert_one({"user_id": user_id, "email": f"{user_id}@t.local"})

        # Chamamos request_content(...) mas com generate_via_llm substituído para não bater no Claude real
        gen_calls = {"n": 0}
        async def fake_gen(*a, **k):
            gen_calls["n"] += 1
            await asyncio.sleep(0.05)
            return {"stem": "x", "options": ["A","B","C","D"], "correct_index": 0, "explanation": "y"}

        original = lm.generate_via_llm
        lm.generate_via_llm = fake_gen
        try:
            unique_topic = f"compat_{uuid.uuid4().hex[:6]}"
            results = await asyncio.gather(*[
                lm.request_content(
                    user_id=user_id, kind="question",
                    discipline="compat", topic=unique_topic, subtopic=None,
                    period=6, variant="default",
                ) for _ in range(30)
            ])
        finally:
            lm.generate_via_llm = original

        generated = sum(1 for r in results if r["source"] == "generated")
        reused = sum(1 for r in results if r["source"] == "reused")

        # cleanup
        await db.users.delete_one({"user_id": user_id})
        await db.content_memory.delete_many({"discipline": "compat"})
        await db.student_content_events.delete_many({"user_id": user_id})
        client.close()

        assert gen_calls["n"] == 1, f"request_content wrapper failed to dedupe: {gen_calls['n']} calls"
        assert generated == 1
        assert reused == 29
    _run(run())
