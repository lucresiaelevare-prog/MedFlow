"""Content Memory Engine v2 — tests for P0/P1/P2 upgrades.

Cobertura:
- P0.1: índices MongoDB criados no startup
- P0.1: fingerprint inclui CONTENT_SCHEMA_VERSION
- P0.1: schema upgrade → cache miss (invalidação silenciosa)
- P0.3: quarentena automática por reports_count >= 3
- P0.3: quarentena automática por reports_count / usage_count > 0.15
- P0.3: doc quarentenado NÃO é reutilizado
- P2:   TTL por kind expira docs
- P1:   endpoint admin /api/admin/content-memory retorna schema correto
- P1:   Content Memory Engine unificado via remember_or_generate
- Compat: docs legados sem `status` são tratados como ACTIVE

Todos os testes assíncronos compartilham um único event loop de módulo
(o `motor` client em `learning_memory.core.db` é bound à primeira loop
que o toca — fechá-la corromperia acessos subsequentes).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
import learning_memory as lm  # noqa: E402

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

TIMEOUT = 20


# ─── Shared event loop (module-scoped) ──────────────────────────────
_LOOP = asyncio.new_event_loop()


def _run(coro):
    """Execute a coroutine on the shared loop."""
    return _LOOP.run_until_complete(coro)


# ─── Sync helpers ───────────────────────────────────────────────────
def _db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _admin_token() -> str:
    r = requests.post(
        f"{API}/auth/admin-login",
        json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"admin-login failed: {r.status_code} {r.text}"
    return r.json()["session_token"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# P0.1 — Indexes
# ═══════════════════════════════════════════════════════════════════
def test_p01_indexes_content_memory():
    """content_memory has index on `fingerprint` and `status`."""
    names = [i["name"] for i in _db().content_memory.list_indexes()]
    assert "fingerprint_1" in names, f"missing fingerprint index. Got: {names}"
    assert "status_1" in names, f"missing status index. Got: {names}"


def test_p01_indexes_student_content_events():
    """student_content_events has compound index (user_id, content_id)."""
    names = [i["name"] for i in _db().student_content_events.list_indexes()]
    assert "user_id_1_content_id_1" in names, f"missing user_content index. Got: {names}"


def test_p01_query_uses_index_not_collscan():
    """Fingerprint lookup uses IXSCAN, not COLLSCAN."""
    db = _db()
    plan = db.command(
        "explain",
        {"find": "content_memory", "filter": {"fingerprint": "probe_fp_deadbeef"}},
        verbosity="executionStats",
    )
    winning = plan["queryPlanner"]["winningPlan"]
    winning = winning.get("queryPlan", winning)
    stage = winning
    seen_stages = []
    while stage:
        seen_stages.append(stage.get("stage"))
        if stage.get("stage") == "IXSCAN":
            assert stage.get("indexName") == "fingerprint_1", f"wrong index: {stage.get('indexName')}"
            return
        stage = stage.get("inputStage")
    pytest.fail(f"expected IXSCAN in plan, got stages: {seen_stages}. Full winning: {winning}")


# ═══════════════════════════════════════════════════════════════════
# P0.1 — Schema versioning
# ═══════════════════════════════════════════════════════════════════
def test_p01_fingerprint_includes_schema_version():
    """Fingerprint changes when CONTENT_SCHEMA_VERSION changes."""
    original = lm.CONTENT_SCHEMA_VERSION
    fp_current = lm.compute_fingerprint(
        "flashcard", "Anatomia", "Coração", "Válvulas", "clinico", "default"
    )
    lm.CONTENT_SCHEMA_VERSION = "v-test-999"
    try:
        fp_bumped = lm.compute_fingerprint(
            "flashcard", "Anatomia", "Coração", "Válvulas", "clinico", "default"
        )
        assert fp_current != fp_bumped, "bumping CONTENT_SCHEMA_VERSION must invalidate fingerprint"
    finally:
        lm.CONTENT_SCHEMA_VERSION = original


def test_p01_generic_fingerprint_stable_across_key_order():
    """compute_fingerprint_generic must be order-independent for keys."""
    fp_a = lm.compute_fingerprint_generic("checkin_rec", {"a": "1", "b": "2", "c": "3"}, "default")
    fp_b = lm.compute_fingerprint_generic("checkin_rec", {"c": "3", "a": "1", "b": "2"}, "default")
    assert fp_a == fp_b, "generic fingerprint must be stable regardless of key insertion order"


def test_p01_schema_upgrade_invalidates_old_cache():
    """After bumping schema_version, an old-version doc yields cache MISS on lookup."""
    doc_id = f"cm_upg_{uuid.uuid4().hex[:8]}"
    # Compute fingerprint with old version
    lm.CONTENT_SCHEMA_VERSION = "v1-old"
    fp_old = lm.compute_fingerprint("summary", "test-upgrade", "topic-u", None, "basico", "default")
    _db().content_memory.insert_one({
        "id": doc_id, "fingerprint": fp_old, "schema_version": "v1-old",
        "status": lm.STATUS_ACTIVE, "kind": "summary", "discipline": "test-upgrade",
        "topic": "topic-u", "subtopic": "", "period_bucket": "basico", "variant": "default",
        "payload": {"bullets": ["old"]}, "generator": "test", "prompt_used": "",
        "usage_count": 5, "completion_count": 5, "attempts_count": 0, "correct_count": 0,
        "reports_count": 0, "created_at": _now_iso(), "last_used_at": None,
    })
    try:
        # Now bump to a new version — lookup should MISS the old doc
        lm.CONTENT_SCHEMA_VERSION = "v2-new"
        docs = _run(lm.search_content("summary", "test-upgrade", "topic-u", None, "basico", "default"))
        assert docs == [], "post-upgrade lookup must NOT find old-version doc"
    finally:
        lm.CONTENT_SCHEMA_VERSION = "v2"
        _db().content_memory.delete_one({"id": doc_id})


# ═══════════════════════════════════════════════════════════════════
# P0.3 — Quarantine
# ═══════════════════════════════════════════════════════════════════
def test_p03_should_quarantine_by_absolute_reports():
    """reports_count >= 3 triggers quarantine regardless of usage."""
    assert lm._should_quarantine({"reports_count": 3, "usage_count": 100}) is True
    assert lm._should_quarantine({"reports_count": 2, "usage_count": 100}) is False


def test_p03_should_quarantine_by_ratio():
    """reports_count / usage_count > 0.15 triggers quarantine."""
    # 2/10 = 0.20 > 0.15 → quarantined even though absolute < 3
    assert lm._should_quarantine({"reports_count": 2, "usage_count": 10}) is True
    # 1/10 = 0.10 < 0.15 → not quarantined
    assert lm._should_quarantine({"reports_count": 1, "usage_count": 10}) is False


def test_p03_quarantined_docs_not_reused():
    """A quarantined doc must NOT be returned by search_content."""
    doc_id = f"cm_q_{uuid.uuid4().hex[:8]}"
    fp = lm.compute_fingerprint("question", "test-quarantine-x", "topic-x", "sub-x", "basico", "default")
    _db().content_memory.insert_one({
        "id": doc_id, "fingerprint": fp, "schema_version": lm.CONTENT_SCHEMA_VERSION,
        "status": lm.STATUS_QUARANTINED, "kind": "question", "discipline": "test-quarantine-x",
        "topic": "topic-x", "subtopic": "sub-x", "period_bucket": "basico", "variant": "default",
        "payload": {"stem": "should not be reused"}, "generator": "test", "prompt_used": "",
        "usage_count": 5, "completion_count": 0, "attempts_count": 5, "correct_count": 5,
        "reports_count": 5, "created_at": _now_iso(), "last_used_at": None, "quarantined_at": _now_iso(),
    })
    try:
        docs = _run(lm.search_content(
            "question", "test-quarantine-x", "topic-x", "sub-x", "basico", "default"
        ))
        assert docs == [], f"quarantined doc should be filtered. Got: {docs}"
    finally:
        _db().content_memory.delete_one({"id": doc_id})


def test_p03_register_report_auto_quarantines_at_threshold():
    """Calling register_report 3× moves status → QUARANTINED."""
    doc_id = f"cm_reg_{uuid.uuid4().hex[:8]}"
    fp = lm.compute_fingerprint("flashcard", "test-report-y", "topic-y", None, "basico", "default")
    _db().content_memory.insert_one({
        "id": doc_id, "fingerprint": fp, "schema_version": lm.CONTENT_SCHEMA_VERSION,
        "status": lm.STATUS_ACTIVE, "kind": "flashcard", "discipline": "test-report-y",
        "topic": "topic-y", "subtopic": "", "period_bucket": "basico", "variant": "default",
        "payload": {"front": "x", "back": "y"}, "generator": "test", "prompt_used": "",
        "usage_count": 10, "completion_count": 0, "attempts_count": 0, "correct_count": 0,
        "reports_count": 0, "created_at": _now_iso(), "last_used_at": None,
    })
    try:
        for _ in range(3):
            _run(lm.register_report(doc_id))
        doc = _db().content_memory.find_one({"id": doc_id})
        assert doc["reports_count"] == 3
        assert doc["status"] == lm.STATUS_QUARANTINED
        assert doc.get("quarantined_at") is not None
    finally:
        _db().content_memory.delete_one({"id": doc_id})


# ═══════════════════════════════════════════════════════════════════
# P2 — TTL
# ═══════════════════════════════════════════════════════════════════
def test_p02_is_expired_by_kind_ttl():
    """flashcard TTL=180d — doc criado há 200d é considerado expirado."""
    old_iso = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    fresh_iso = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    assert lm._is_expired({"kind": "flashcard", "created_at": old_iso}) is True
    assert lm._is_expired({"kind": "flashcard", "created_at": fresh_iso}) is False


def test_p02_expired_docs_not_reused():
    """Doc expirado por TTL não aparece em search_content."""
    doc_id = f"cm_exp_{uuid.uuid4().hex[:8]}"
    fp = lm.compute_fingerprint("clinical_case", "test-ttl", "topic-ttl", None, "basico", "default")
    # clinical_case TTL is 60d → seed with 90 days old
    old_iso = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    _db().content_memory.insert_one({
        "id": doc_id, "fingerprint": fp, "schema_version": lm.CONTENT_SCHEMA_VERSION,
        "status": lm.STATUS_ACTIVE, "kind": "clinical_case", "discipline": "test-ttl",
        "topic": "topic-ttl", "subtopic": "", "period_bucket": "basico", "variant": "default",
        "payload": {"case": "stale"}, "generator": "test", "prompt_used": "",
        "usage_count": 5, "completion_count": 0, "attempts_count": 0, "correct_count": 0,
        "reports_count": 0, "created_at": old_iso, "last_used_at": None,
    })
    try:
        docs = _run(lm.search_content(
            "clinical_case", "test-ttl", "topic-ttl", None, "basico", "default"
        ))
        assert docs == [], f"expired clinical_case should be filtered. Got {len(docs)}"
    finally:
        _db().content_memory.delete_one({"id": doc_id})


# ═══════════════════════════════════════════════════════════════════
# Compat — legacy docs
# ═══════════════════════════════════════════════════════════════════
def test_compat_legacy_docs_treated_as_active():
    """Docs sem campo `status` (pre-v2) devem ser reutilizáveis normalmente."""
    doc_id = f"cm_legacy_{uuid.uuid4().hex[:8]}"
    fp = lm.compute_fingerprint("summary", "test-legacy", "topic-l", None, "basico", "default")
    # No `status`, no `schema_version`, no `quarantined_at` — legacy shape
    _db().content_memory.insert_one({
        "id": doc_id, "fingerprint": fp,
        "kind": "summary", "discipline": "test-legacy",
        "topic": "topic-l", "subtopic": "", "period_bucket": "basico", "variant": "default",
        "payload": {"bullets": ["ok"]}, "generator": "test", "prompt_used": "",
        "usage_count": 5, "completion_count": 5, "attempts_count": 0, "correct_count": 0,
        "reports_count": 0, "created_at": _now_iso(), "last_used_at": None,
    })
    try:
        docs = _run(lm.search_content("summary", "test-legacy", "topic-l", None, "basico", "default"))
        assert any(d["id"] == doc_id for d in docs), "legacy doc without status must still be found"
    finally:
        _db().content_memory.delete_one({"id": doc_id})


# ═══════════════════════════════════════════════════════════════════
# P1 — Admin endpoint
# ═══════════════════════════════════════════════════════════════════
def test_p1_admin_content_memory_endpoint_shape():
    """GET /api/admin/content-memory returns full shape."""
    tok = _admin_token()
    r = requests.get(
        f"{API}/admin/content-memory",
        headers={"Authorization": f"Bearer {tok}"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    data = r.json()
    for key in (
        "content_count", "cache_hits", "cache_misses", "reuse_ratio",
        "quarantined_count", "top_reused", "top_reported",
        "tokens_saved_estimated", "usd_saved_estimated",
        "current_schema_version",
    ):
        assert key in data, f"missing key: {key}. Got keys: {list(data.keys())}"
    assert "config" in data
    for cfg_key in (
        "current_schema_version", "quarantine_min_reports",
        "quarantine_report_ratio", "ttl_by_kind_days",
    ):
        assert cfg_key in data["config"], f"missing config key: {cfg_key}"


def test_p1_admin_content_memory_requires_admin():
    """Non-admin cannot access /api/admin/content-memory."""
    r = requests.post(
        f"{API}/auth/dev-login",
        json={"email": "notadmin@test.local", "name": "Not Admin"},
        timeout=TIMEOUT,
    )
    tok = r.json()["session_token"]
    r2 = requests.get(
        f"{API}/admin/content-memory",
        headers={"Authorization": f"Bearer {tok}"},
        timeout=TIMEOUT,
    )
    assert r2.status_code in (401, 403), f"expected 401/403, got {r2.status_code}"


# ═══════════════════════════════════════════════════════════════════
# P1 — Unified engine (remember_or_generate)
# ═══════════════════════════════════════════════════════════════════
def test_p1_remember_or_generate_cache_miss_then_hit():
    """First call generates, second call reuses. Generator invoked once."""
    unique_topic = f"topic_uog_{uuid.uuid4().hex[:8]}"
    key_fields = {
        "discipline": "unit-test-uog",
        "topic": unique_topic,
        "subtopic": "unit-sub",
        "period_bucket": "basico",
    }
    call_counter = {"n": 0}

    async def _fake_gen():
        call_counter["n"] += 1
        return {"marker": "generated_once", "n": call_counter["n"]}

    try:
        first = _run(lm.remember_or_generate("flashcard", key_fields, _fake_gen, variant="uv1"))
        assert first["source"] == "generated"
        assert call_counter["n"] == 1

        second = _run(lm.remember_or_generate("flashcard", key_fields, _fake_gen, variant="uv1"))
        assert second["source"] == "reused"
        assert call_counter["n"] == 1, "generator MUST NOT be called on cache hit"
        assert second["content"]["id"] == first["content"]["id"]
    finally:
        _db().content_memory.delete_many({"topic": lm._slug(unique_topic)})
