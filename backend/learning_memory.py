"""MedFlow — Learning Memory Engine (P0.2.2).

Ponte entre a memória de decisão (P0.2.1) e a memória de aprendizagem.
Objetivo: acumular conhecimento gerado, evitar geração repetida por IA,
descobrir dificuldades coletivas.

Três camadas (ver /app/memory/PRD.md):

  1. content_memory        — banco compartilhado de conteúdos gerados.
  2. student_content_events — log individual do que cada aluno viu / acertou.
  3. Métricas agregadas    — reuso, dificuldade coletiva, mastery pessoal.

Regras invioláveis:
- Nunca duplicar geração se conteúdo equivalente existe com eficácia aceitável.
- Nunca perder o evento individual (é o insumo da mastery + hipóteses).
- Nunca personalizar antes de acumular ≥3 usos com o mesmo fingerprint.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import re
import time
import unicodedata
import uuid
from collections import deque
from typing import Any, Optional

from core import _iso, _now, db, logger

try:  # duplicate-key handling for the UNIQUE fingerprint index (P0.1 stampede net)
    from pymongo.errors import DuplicateKeyError  # type: ignore
except Exception:  # pragma: no cover - fallback if pymongo not present
    class DuplicateKeyError(Exception):  # type: ignore
        pass

# ─── Constantes de negócio ──────────────────────────────────────────
VALID_KINDS = {
    "question", "flashcard", "summary", "explanation", "mindmap", "review",
    "clinical_case",
    # extended kinds — unified Content Memory Engine (P1)
    "checkin_rec", "exam_feedback", "support_reply", "insights_coaching",
}

# Só reutilizamos conteúdo se a eficácia observada estiver acima disso.
# Abaixo de 3 usos ainda é "learning" — devolvemos igual (não é penalidade).
REUSE_EFFICACY_THRESHOLD = 0.35
REUSE_MIN_SAMPLE = 3

# ─── P0.1: Schema versioning ────────────────────────────────────────
# Bump CONTENT_SCHEMA_VERSION whenever prompts/models/normalization change.
# All lookups with the new version become cache misses → forced regeneration.
# Old docs remain in Mongo (auditable), but stop being served.
CONTENT_SCHEMA_VERSION = os.environ.get("CONTENT_SCHEMA_VERSION", "v2")

# ─── P0.3: Quarantine thresholds ────────────────────────────────────
# A content is auto-quarantined when either condition holds:
#   • reports_count >= QUARANTINE_MIN_REPORTS  (absolute floor)
#   • reports_count / max(1, usage_count) > QUARANTINE_REPORT_RATIO  (relative)
QUARANTINE_MIN_REPORTS = 3
QUARANTINE_REPORT_RATIO = 0.15
STATUS_ACTIVE = "ACTIVE"
STATUS_QUARANTINED = "QUARANTINED"

# ─── P2: TTL by kind (days). 0/None means "never expires". ──────────
# Rationale: clinical cases evolve with guidelines faster than flashcards.
# Coaching phrases are inherently ephemeral. Questions test canonical
# knowledge and can be reused for a full academic year.
TTL_BY_KIND: dict[str, int] = {
    "flashcard": 180,
    "clinical_case": 60,
    "question": 365,
    "summary": 120,
    "explanation": 180,
    "mindmap": 180,
    "review": 90,
    # extended kinds
    "checkin_rec": 1,          # daily context — barely reusable, but bucketed
    "insights_coaching": 7,    # weekly regenerate
    "exam_feedback": 30,
    "support_reply": 30,
}
DEFAULT_TTL_DAYS = 90


# ─── P0.1: Single-flight state (in-process) ─────────────────────────
# Guarantees that only ONE coroutine at a time generates content for a
# given fingerprint within a single Python process. The UNIQUE partial
# index (see ensure_indexes) is the cross-process safety net when
# multiple uvicorn workers race.
_fp_locks: dict[str, asyncio.Lock] = {}
_fp_locks_guard: asyncio.Lock = asyncio.Lock()


async def _acquire_fp_lock(fp: str) -> asyncio.Lock:
    """Returns the per-fingerprint asyncio.Lock, creating it on first use."""
    async with _fp_locks_guard:
        lock = _fp_locks.get(fp)
        if lock is None:
            lock = asyncio.Lock()
            _fp_locks[fp] = lock
    return lock


async def _release_fp_lock_if_idle(fp: str) -> None:
    """Best-effort GC of unused locks to keep memory bounded."""
    async with _fp_locks_guard:
        lock = _fp_locks.get(fp)
        if lock is not None and not lock.locked():
            _fp_locks.pop(fp, None)


# ─── P0.4: Circuit-breaker + retry policy for LLM calls ─────────────
# Three states: CLOSED (normal), OPEN (fail-fast), HALF_OPEN (probe one).
CB_FAILURE_THRESHOLD = int(os.environ.get("LLM_CB_FAILURE_THRESHOLD", "5"))
CB_OPEN_SECONDS = float(os.environ.get("LLM_CB_OPEN_SECONDS", "30"))
CB_RETRY_ATTEMPTS = int(os.environ.get("LLM_RETRY_ATTEMPTS", "3"))
CB_RETRY_BASE_DELAY = float(os.environ.get("LLM_RETRY_BASE_DELAY", "0.5"))
CB_MAX_DELAY = float(os.environ.get("LLM_RETRY_MAX_DELAY", "8"))
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "45"))


class CircuitOpenError(RuntimeError):
    """Raised when the LLM circuit is OPEN — caller should fail fast."""


class _CircuitBreaker:
    __slots__ = ("state", "failures", "opened_at", "half_open_probe")

    def __init__(self) -> None:
        self.state: str = "CLOSED"     # CLOSED | OPEN | HALF_OPEN
        self.failures: int = 0
        self.opened_at: float = 0.0
        self.half_open_probe: bool = False

    def snapshot(self) -> dict:
        return {
            "state": self.state,
            "failures": self.failures,
            "opened_at": self.opened_at,
        }

    def before_call(self) -> None:
        if self.state == "OPEN":
            if (time.monotonic() - self.opened_at) >= CB_OPEN_SECONDS:
                self.state = "HALF_OPEN"
                self.half_open_probe = False
                logger.warning("LLM circuit → HALF_OPEN (recovery probe)")
            else:
                raise CircuitOpenError("LLM circuit is OPEN")
        if self.state == "HALF_OPEN":
            if self.half_open_probe:
                raise CircuitOpenError("LLM circuit HALF_OPEN — probe in flight")
            self.half_open_probe = True

    def on_success(self) -> None:
        if self.state in ("OPEN", "HALF_OPEN"):
            logger.info("LLM circuit → CLOSED (recovered)")
        self.state = "CLOSED"
        self.failures = 0
        self.half_open_probe = False

    def on_failure(self) -> None:
        if self.state == "HALF_OPEN":
            self.state = "OPEN"
            self.opened_at = time.monotonic()
            self.half_open_probe = False
            logger.warning("LLM circuit → OPEN (probe failed)")
            return
        self.failures += 1
        if self.failures >= CB_FAILURE_THRESHOLD:
            self.state = "OPEN"
            self.opened_at = time.monotonic()
            logger.warning(
                "LLM circuit → OPEN (failures=%d threshold=%d)",
                self.failures, CB_FAILURE_THRESHOLD,
            )


_llm_cb = _CircuitBreaker()


async def call_llm_with_retry(coro_factory, *, label: str = "llm"):
    """Wraps an async LLM call with retries + circuit-breaker + timeout.

    `coro_factory` must be a **callable that returns a coroutine** on each
    invocation (so we can retry). Not a coroutine itself.
    """
    _llm_cb.before_call()
    attempt = 0
    while True:
        attempt += 1
        try:
            result = await asyncio.wait_for(coro_factory(), timeout=LLM_TIMEOUT_SECONDS)
            _llm_cb.on_success()
            return result
        except CircuitOpenError:
            raise
        except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
            _llm_cb.on_failure()
            if attempt >= CB_RETRY_ATTEMPTS or isinstance(exc, asyncio.CancelledError):
                logger.error("LLM %s failed after %d attempts: %s", label, attempt, exc)
                raise
            delay = min(CB_MAX_DELAY, CB_RETRY_BASE_DELAY * (2 ** (attempt - 1)))
            delay *= 0.75 + random.random() * 0.5  # jitter
            logger.warning("LLM %s attempt %d timed out; retry in %.2fs", label, attempt, delay)
            await asyncio.sleep(delay)
        except Exception as exc:  # noqa: BLE001 – any other failure
            _llm_cb.on_failure()
            # Retry only on transient-ish exceptions; hard errors we re-raise.
            transient = any(
                token in (repr(exc).lower() + str(exc).lower())
                for token in ("timeout", "connection", "econnreset", "429", "500", "502", "503", "504", "temporarily")
            )
            if attempt >= CB_RETRY_ATTEMPTS or not transient:
                logger.error("LLM %s failed non-retriable: %r", label, exc)
                raise
            delay = min(CB_MAX_DELAY, CB_RETRY_BASE_DELAY * (2 ** (attempt - 1)))
            delay *= 0.75 + random.random() * 0.5
            logger.warning("LLM %s attempt %d failed (%s); retry in %.2fs", label, attempt, type(exc).__name__, delay)
            await asyncio.sleep(delay)


# ─── P1: Observability counters (in-process) ────────────────────────
_metrics: dict[str, Any] = {
    "cache_hits": 0,
    "cache_misses": 0,
    "singleflight_waits": 0,
    "stampede_prevented": 0,      # peers that blocked on lock and reused the winner
    "duplicate_key_saves": 0,     # cross-process races caught by UNIQUE index
    "llm_calls_ok": 0,
    "llm_calls_failed": 0,
    "circuit_open_rejections": 0,
    "reports_rejected_duplicate": 0,
}
# Rolling latency samples (max 512 each) for P95/P99.
_lat_gen_ms: deque = deque(maxlen=512)
_lat_hit_ms: deque = deque(maxlen=512)
_lat_miss_ms: deque = deque(maxlen=512)


def _record_latency(bucket: deque, ms: float) -> None:
    bucket.append(float(ms))


def _pcile(bucket: deque, p: float) -> float | None:
    if not bucket:
        return None
    arr = sorted(bucket)
    idx = min(len(arr) - 1, int(len(arr) * p))
    return round(arr[idx], 3)


def get_engine_metrics() -> dict:
    """Snapshot dos contadores/latências para o painel admin."""
    return {
        "counters": dict(_metrics),
        "latency_ms": {
            "generation_p50": _pcile(_lat_gen_ms, 0.50),
            "generation_p95": _pcile(_lat_gen_ms, 0.95),
            "generation_p99": _pcile(_lat_gen_ms, 0.99),
            "cache_hit_p50": _pcile(_lat_hit_ms, 0.50),
            "cache_hit_p95": _pcile(_lat_hit_ms, 0.95),
            "cache_hit_p99": _pcile(_lat_hit_ms, 0.99),
            "cache_miss_p50": _pcile(_lat_miss_ms, 0.50),
            "cache_miss_p95": _pcile(_lat_miss_ms, 0.95),
        },
        "circuit_breaker": _llm_cb.snapshot(),
        "sample_sizes": {
            "gen": len(_lat_gen_ms),
            "hit": len(_lat_hit_ms),
            "miss": len(_lat_miss_ms),
        },
    }


def _slug(value: str) -> str:
    """Normalização: minúscula + sem acentos + sem espaços — canoniza chaves.

    Vira o insumo do `fingerprint` de conteúdo (mesmo tema/subtema devem
    colidir mesmo escritos com variação de capitalização/acentuação).
    """
    if value is None:
        return ""
    v = str(value).strip().lower()
    v = unicodedata.normalize("NFKD", v).encode("ascii", "ignore").decode("ascii")
    v = re.sub(r"[^a-z0-9]+", "-", v).strip("-")
    return v


def _period_bucket(period: int | None) -> str:
    """Buckets grandes — anonimização por generalização (LGPD)."""
    if period is None:
        return "unspecified"
    try:
        p = int(period)
    except Exception:
        return "unspecified"
    if p <= 2:
        return "basico"
    if p <= 6:
        return "clinico"
    if p <= 10:
        return "internato"
    return "outros"


def compute_fingerprint(
    kind: str,
    discipline: str,
    topic: str,
    subtopic: str | None = None,
    period_bucket: str = "unspecified",
    variant: str = "default",
) -> str:
    """Hash estável do "pedido de conteúdo".

    Fingerprint identifica uma NECESSIDADE (não uma instância única).
    Múltiplas gerações podem existir com o mesmo fingerprint — escolhemos
    a de maior eficácia na hora de reutilizar.

    P0.1: schema version é o primeiro token. Bump da versão invalida
    silenciosamente todo cache antigo (miss → regeração).
    """
    key = "|".join([
        CONTENT_SCHEMA_VERSION,
        _slug(kind), _slug(discipline), _slug(topic),
        _slug(subtopic or ""), _slug(period_bucket), _slug(variant),
    ])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


def compute_fingerprint_generic(kind: str, key_fields: dict, variant: str = "default") -> str:
    """Fingerprint genérico para o Content Memory Engine unificado (P1).

    `key_fields` — dict arbitrário com os inputs que definem a "necessidade".
    Chaves são ordenadas para estabilidade e cada valor é slugificado.
    A ordem canonical é: `v{SCHEMA}|kind|k1=v1|k2=v2|...|variant`.

    Uso: endpoints como /checkin, /support, /insights, /tutor/exam-feedback
    que não se encaixam em (discipline, topic, subtopic) mas ainda querem
    memoização cross-user com buckets grossos.
    """
    parts = [CONTENT_SCHEMA_VERSION, _slug(kind)]
    for k in sorted(key_fields.keys()):
        parts.append(f"{_slug(k)}={_slug(str(key_fields[k]))}")
    parts.append(_slug(variant))
    key = "|".join(parts)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


# ─── P0.3: Quarantine + P2: TTL helpers ─────────────────────────────
def _should_quarantine(doc: dict) -> bool:
    """True se o doc atinge o gatilho de quarentena (relatórios ruins)."""
    reports = int(doc.get("reports_count") or 0)
    usage = max(1, int(doc.get("usage_count") or 0))
    if reports >= QUARANTINE_MIN_REPORTS:
        return True
    return (reports / usage) > QUARANTINE_REPORT_RATIO


def _is_expired(doc: dict) -> bool:
    """True se o doc passou do TTL para seu kind. Sem TTL → False."""
    from datetime import datetime, timezone
    ttl = TTL_BY_KIND.get(doc.get("kind"), DEFAULT_TTL_DAYS)
    if not ttl or ttl <= 0:
        return False
    created = doc.get("created_at")
    if not created:
        return False
    try:
        # ISO strings emitidos pelo _iso() já vêm com timezone
        dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
    except Exception:
        return False
    return (datetime.now(timezone.utc) - dt).days > ttl


# ─── P0.1: Index bootstrap (idempotente, seguro para chamar no startup) ─
async def ensure_indexes() -> dict:
    """Cria índices necessários para o Content Memory Engine.

    Idempotente: `create_index` é no-op quando o índice já existe.
    Retorna dict com o log das operações — útil para observabilidade
    de startup e testes.

    Índices UNIQUE (P0.2):
      • `content_memory.id` UNIQUE — cada doc tem um id ObjectId-free único.
      • `content_memory.(fingerprint, status)` UNIQUE parcial em ACTIVE —
        cross-process safety net contra cache stampede. Docs QUARANTINED
        são ignorados pelo constraint (podem coexistir com um ACTIVE novo).

    Índices de auth (fora do escopo v2, mas eliminados os COLLSCANs quentes):
      • `users.user_id` UNIQUE, `users.email` UNIQUE
      • `user_sessions.session_token` UNIQUE
      • `user_sessions.expires_at` TTL (limpeza automática)
    """
    created: list[str] = []
    skipped: list[str] = []

    async def _try_create(coll, spec, **kwargs):
        try:
            name = await coll.create_index(spec, **kwargs)
            created.append(f"{coll.name}.{name}")
        except Exception as exc:  # noqa: BLE001 – legacy dup keys shouldn't crash startup
            logger.warning("ensure_indexes: could not create %s %s: %s", coll.name, spec, exc)
            skipped.append(f"{coll.name}.{spec}")

    # content_memory ─ hot path
    await _try_create(db.content_memory, "id", unique=True)
    # UNIQUE parcial: só docs ACTIVE competem pelo fingerprint (permite regeneração
    # após quarentena/expiração sem quebrar o insert).
    await _try_create(
        db.content_memory,
        [("fingerprint", 1), ("schema_version", 1)],
        unique=True,
        partialFilterExpression={"status": STATUS_ACTIVE},
        name="fp_schema_active_uniq",
    )
    # Índice não-UNIQUE tradicional (retrocompat – docs sem status contam)
    await _try_create(db.content_memory, "fingerprint")
    await _try_create(db.content_memory, "status")
    await _try_create(db.content_memory, [("kind", 1), ("last_used_at", -1)])

    # student_content_events
    await _try_create(db.student_content_events, [("user_id", 1), ("content_id", 1)])
    await _try_create(db.student_content_events, [("content_id", 1), ("event_type", 1)])
    # Índice para o rate-limit de reports (P0.3)
    await _try_create(
        db.student_content_events,
        [("user_id", 1), ("content_id", 1), ("event_type", 1)],
        name="user_content_event",
    )
    # UNIQUE parcial: garante que cada (user, content) só possa gerar UM único
    # evento `reported_error` — impede cache poisoning por spam concorrente.
    await _try_create(
        db.student_content_events,
        [("user_id", 1), ("content_id", 1)],
        unique=True,
        partialFilterExpression={"event_type": "reported_error"},
        name="user_content_reported_uniq",
    )

    # auth — quentes em toda request
    await _try_create(db.user_sessions, "session_token", unique=True)
    # TTL: Mongo expira automaticamente ao passar de expires_at. Se o campo não
    # existir num doc legado, nada acontece (comportamento seguro).
    await _try_create(db.user_sessions, "expires_at", expireAfterSeconds=0)
    await _try_create(db.users, "user_id", unique=True)
    await _try_create(db.users, "email", unique=True)

    logger.info("content_memory indexes ensured: created=%s skipped=%s", created, skipped)
    return {"created_or_verified": created, "skipped": skipped}


# ─── content_memory (Camada 1) ─────────────────────────────────────
def _compute_efficacy(doc: dict) -> tuple[float | None, int]:
    """Devolve (score, sample_size) para um documento content_memory.

    Fórmulas dependem do kind:
      question/flashcard → correct/attempts (só com >=3 attempts)
      summary/explanation/mindmap/review → completion/usage (só com >=3 usage)
    Retorna (None, n) enquanto n < 3 (ainda aprendendo).
    """
    kind = doc.get("kind")
    if kind in ("question", "flashcard"):
        attempts = int(doc.get("attempts_count") or 0)
        correct = int(doc.get("correct_count") or 0)
        if attempts < REUSE_MIN_SAMPLE:
            return None, attempts
        return round(correct / attempts, 3), attempts
    usage = int(doc.get("usage_count") or 0)
    completed = int(doc.get("completion_count") or 0)
    if usage < REUSE_MIN_SAMPLE:
        return None, usage
    return round(completed / usage, 3), usage


async def search_content(
    kind: str,
    discipline: str,
    topic: str,
    subtopic: str | None,
    period_bucket: str,
    variant: str = "default",
    limit: int = 5,
) -> list[dict]:
    """Busca conteúdos candidatos por fingerprint. Ordenados por eficácia desc.

    Empates são desempatados por `usage_count` desc (mais provado).
    Devolve lista de dicts crus da memória compartilhada (sem `_id`).
    """
    fp = compute_fingerprint(kind, discipline, topic, subtopic, period_bucket, variant)
    docs: list[dict] = []
    # P0.3: só considera ACTIVE (compat: docs sem status são tratados como ACTIVE)
    query = {
        "fingerprint": fp,
        "$or": [{"status": {"$exists": False}}, {"status": STATUS_ACTIVE}],
    }
    async for d in db.content_memory.find(query, {"_id": 0}):
        # P2: pula expirados (TTL por kind)
        if _is_expired(d):
            continue
        eff, n = _compute_efficacy(d)
        d["_efficacy"] = eff
        d["_sample"] = n
        docs.append(d)
    docs.sort(key=lambda x: (
        (x["_efficacy"] if x["_efficacy"] is not None else -1),
        int(x.get("usage_count") or 0),
    ), reverse=True)
    return docs[:limit]


async def pick_best_content(*args, **kwargs):  # pragma: no cover - back-compat shim
    """DEPRECATED (P2 cleanup): use `remember_or_generate` ou `search_content`.

    Mantido como thin wrapper por compatibilidade externa; internamente
    o único caller (`request_content`) foi migrado para `remember_or_generate`,
    que já implementa cache-lookup + single-flight numa passada só.
    """
    raise NotImplementedError(
        "pick_best_content foi removido no P2. Use remember_or_generate."
    )


async def persist_content(*args, **kwargs):  # pragma: no cover - back-compat shim
    """DEPRECATED (P2 cleanup): substituído pelo insert atômico dentro de
    `remember_or_generate`. Mantido como stub para pegar callers residuais
    em falha rápida (loud failure > silent bug)."""
    raise NotImplementedError(
        "persist_content foi removido no P2. Use remember_or_generate."
    )


async def increment_usage(content_id: str) -> None:
    await db.content_memory.update_one(
        {"id": content_id},
        {"$inc": {"usage_count": 1}, "$set": {"last_used_at": _iso(_now())}},
    )


async def increment_completion(content_id: str) -> None:
    await db.content_memory.update_one(
        {"id": content_id},
        {"$inc": {"completion_count": 1}},
    )


async def register_attempt(content_id: str, correct: bool) -> None:
    updates: dict = {"$inc": {"attempts_count": 1}}
    if correct:
        updates["$inc"]["correct_count"] = 1
    await db.content_memory.update_one({"id": content_id}, updates)


async def register_report(content_id: str) -> dict:
    """Registra um report e aplica quarentena automática se atingir threshold.

    Retorna dict com o estado pós-update: `{"reports_count", "status",
    "quarantined": bool}`.
    """
    await db.content_memory.update_one(
        {"id": content_id}, {"$inc": {"reports_count": 1}}
    )
    doc = await db.content_memory.find_one({"id": content_id}, {"_id": 0})
    if not doc:
        return {"reports_count": 0, "status": None, "quarantined": False}
    if doc.get("status") == STATUS_QUARANTINED:
        return {"reports_count": doc["reports_count"], "status": STATUS_QUARANTINED, "quarantined": True}
    if _should_quarantine(doc):
        await db.content_memory.update_one(
            {"id": content_id},
            {"$set": {"status": STATUS_QUARANTINED, "quarantined_at": _iso(_now())}},
        )
        logger.warning(
            "content quarantined: id=%s kind=%s reports=%s usage=%s",
            content_id, doc.get("kind"), doc.get("reports_count"), doc.get("usage_count"),
        )
        return {
            "reports_count": int(doc.get("reports_count") or 0),
            "status": STATUS_QUARANTINED,
            "quarantined": True,
        }
    return {
        "reports_count": int(doc.get("reports_count") or 0),
        "status": doc.get("status") or STATUS_ACTIVE,
        "quarantined": False,
    }


# ─── P0.3: Rate-limited report registration ─────────────────────────
async def register_report_rate_limited(user_id: str, content_id: str) -> dict:
    """Registra o report SOMENTE se este `user_id` ainda não reportou o `content_id`.

    Contract atômica (P0.3): usamos o UNIQUE partial index em
    `student_content_events(user_id, content_id) where event_type='reported_error'`
    como fonte da verdade. Ganhador da corrida = quem consegue o insert;
    perdedores caem em `DuplicateKeyError` e não incrementam o contador global.

    Retorno:
      `{ "accepted": bool, "reason": str|None, "state": <register_report result>|None }`.
    """
    if not user_id:
        return {"accepted": False, "reason": "missing_user_id", "state": None}
    # Confirma que o conteúdo existe (retorna 404 no endpoint, não usa slot do UNIQUE)
    content = await db.content_memory.find_one({"id": content_id}, {"_id": 0, "id": 1, "kind": 1, "discipline": 1, "topic": 1, "subtopic": 1})
    if not content:
        return {"accepted": False, "reason": "content_not_found", "state": None}

    evt_id = f"sce_{uuid.uuid4().hex[:16]}"
    doc = {
        "id": evt_id,
        "user_id": user_id,
        "content_id": content_id,
        "kind": content["kind"],
        "discipline": content["discipline"],
        "topic": content["topic"],
        "subtopic": content.get("subtopic", ""),
        "event_type": "reported_error",
        "correct": None,
        "time_spent_sec": None,
        "meta": {},
        "created_at": _iso(_now()),
    }
    try:
        await db.student_content_events.insert_one(doc)
    except DuplicateKeyError:
        _metrics["reports_rejected_duplicate"] += 1
        return {"accepted": False, "reason": "already_reported", "state": None}

    state = await register_report(content_id)
    return {"accepted": True, "reason": None, "state": state}


# ─── student_content_events (Camada 2) ─────────────────────────────
async def log_event(
    user_id: str,
    content_id: str,
    event_type: str,
    correct: bool | None = None,
    time_spent_sec: int | None = None,
    meta: dict | None = None,
) -> str:
    """Registra o evento individual do aluno. Nunca falha silenciosamente."""
    if event_type not in ("shown", "answered", "reviewed", "skipped", "reported_error", "completed"):
        raise ValueError(f"Invalid event_type: {event_type}")
    content = await db.content_memory.find_one({"id": content_id}, {"_id": 0})
    if not content:
        raise LookupError(f"content_memory {content_id} not found")

    evt_id = f"sce_{uuid.uuid4().hex[:16]}"
    await db.student_content_events.insert_one({
        "id": evt_id,
        "user_id": user_id,
        "content_id": content_id,
        "kind": content["kind"],
        "discipline": content["discipline"],
        "topic": content["topic"],
        "subtopic": content.get("subtopic", ""),
        "event_type": event_type,
        "correct": correct,
        "time_spent_sec": time_spent_sec,
        "meta": meta or {},
        "created_at": _iso(_now()),
    })
    return evt_id


# ─── Mastery pessoal (agregado sob demanda) ─────────────────────────
async def student_mastery(user_id: str, discipline: str | None = None) -> dict:
    """Agrupa eventos individuais por (disciplina, tema, subtema).

    Mastery score = (correct - incorrect) / max(seen, 1), clamp [-1, 1] → normalizado 0..1.
    Só reportado quando `seen >= 3` (senão o campo vira None e a UI sabe que ainda está aprendendo).
    """
    q: dict = {"user_id": user_id}
    if discipline:
        q["discipline"] = _slug(discipline)

    by_topic: dict[str, dict[str, Any]] = {}
    async for e in db.student_content_events.find(q, {"_id": 0}):
        disc = e.get("discipline") or "sem-disciplina"
        topic = e.get("topic") or "sem-topico"
        subt = e.get("subtopic") or ""
        key = f"{disc}/{topic}/{subt}"
        d = by_topic.setdefault(key, {
            "discipline": disc, "topic": topic, "subtopic": subt,
            "seen": 0, "correct": 0, "incorrect": 0, "last_seen_at": None,
        })
        if e.get("event_type") in ("shown", "reviewed", "answered", "completed"):
            d["seen"] += 1
        if e.get("event_type") == "answered":
            if e.get("correct") is True:
                d["correct"] += 1
            elif e.get("correct") is False:
                d["incorrect"] += 1
        ts = e.get("created_at")
        if ts and (d["last_seen_at"] is None or ts > d["last_seen_at"]):
            d["last_seen_at"] = ts

    topics_out = []
    for _key, d in by_topic.items():
        seen = d["seen"]
        if seen == 0:
            continue
        answered = d["correct"] + d["incorrect"]
        if answered >= REUSE_MIN_SAMPLE:
            raw = (d["correct"] - d["incorrect"]) / max(answered, 1)
            score = round((raw + 1) / 2, 3)  # 0..1
        else:
            score = None
        d["mastery_score"] = score
        d["answered"] = answered
        topics_out.append(d)

    # Ordena: mestrados no topo, aprendendo depois, sem answered no fim
    def _rank(t):
        s = t["mastery_score"]
        return (0 if s is None else 1, -(s or 0), -t["seen"])
    topics_out.sort(key=_rank)

    return {
        "user_id": user_id,
        "discipline": _slug(discipline) if discipline else None,
        "topics_count": len(topics_out),
        "topics": topics_out,
    }


async def weakest_topic(user_id: str, discipline: str | None = None) -> dict | None:
    """Tópico com menor mastery entre os com sample suficiente.

    Usado pelo motor de decisão para enriquecer P3 `subject_neglected`
    com o subtema mais crítico. Se nada está classificável, devolve None
    (motor cai no comportamento antigo — genérico).
    """
    mastery = await student_mastery(user_id, discipline)
    scored = [t for t in mastery["topics"] if t["mastery_score"] is not None]
    if not scored:
        return None
    scored.sort(key=lambda t: t["mastery_score"])
    weakest = scored[0]
    if weakest["mastery_score"] >= 0.75:
        return None  # todos dominados — nada crítico
    return weakest


# ─── Dificuldade coletiva (Camada 3 / MedFlow Research) ─────────────
async def collective_difficulty(period_bucket: str | None = None, min_sample: int = 20) -> list[dict]:
    """Top tópicos com dificuldade coletiva agregada.

    Sinais: soma de attempts_count e correct_count por (discipline, topic, subtopic)
    de content_memory. `difficulty = 1 - (correct / attempts)`. Só entra em rank
    quando `attempts >= min_sample` (senão o número é ruído).

    Se `period_bucket` for informado, filtra apenas conteúdos daquele grupo.
    """
    q: dict = {}
    if period_bucket:
        q["period_bucket"] = period_bucket

    agg: dict[str, dict[str, Any]] = {}
    async for d in db.content_memory.find(q, {"_id": 0}):
        key = f"{d['discipline']}/{d['topic']}/{d.get('subtopic') or ''}"
        a = agg.setdefault(key, {
            "discipline": d.get("discipline_label") or d["discipline"],
            "topic": d.get("topic_label") or d["topic"],
            "subtopic": d.get("subtopic_label") or d.get("subtopic") or "",
            "attempts": 0, "correct": 0, "usage": 0, "content_count": 0,
        })
        a["attempts"] += int(d.get("attempts_count") or 0)
        a["correct"] += int(d.get("correct_count") or 0)
        a["usage"] += int(d.get("usage_count") or 0)
        a["content_count"] += 1

    out = []
    for _k, a in agg.items():
        if a["attempts"] < min_sample:
            continue
        difficulty = round(1 - (a["correct"] / a["attempts"]), 3)
        a["difficulty"] = difficulty
        out.append(a)
    out.sort(key=lambda t: t["difficulty"], reverse=True)
    return out


async def content_reuse_metrics() -> dict:
    """Métricas globais de reuso para o painel Research + admin/content-memory.

    Inclui P0.3 (quarentena) e estimativas de economia de custo de IA.
    P1 adiciona: redundant_generations, tempo médio real de geração, snapshot
    dos counters em memória (stampede_prevented, singleflight_waits, CB state).
    """
    total_contents = await db.content_memory.count_documents({})
    total_usage = 0
    generator_dist: dict[str, int] = {}
    kind_dist: dict[str, int] = {}
    quarantined_count = 0
    version_dist: dict[str, int] = {}
    top_reused: list[dict] = []
    top_reported: list[dict] = []
    gen_ms_samples: list[float] = []
    unique_fingerprints: set[str] = set()

    async for d in db.content_memory.find(
        {},
        {"_id": 0, "id": 1, "usage_count": 1, "reports_count": 1, "generator": 1,
         "kind": 1, "status": 1, "schema_version": 1, "topic_label": 1,
         "discipline_label": 1, "created_at": 1, "last_used_at": 1,
         "fingerprint": 1, "generation_ms": 1},
    ):
        total_usage += int(d.get("usage_count") or 0)
        g = d.get("generator") or "unknown"
        generator_dist[g] = generator_dist.get(g, 0) + 1
        k = d.get("kind") or "unknown"
        kind_dist[k] = kind_dist.get(k, 0) + 1
        if d.get("status") == STATUS_QUARANTINED:
            quarantined_count += 1
        v = d.get("schema_version") or "legacy"
        version_dist[v] = version_dist.get(v, 0) + 1
        if d.get("fingerprint"):
            unique_fingerprints.add(d["fingerprint"])
        if isinstance(d.get("generation_ms"), (int, float)):
            gen_ms_samples.append(float(d["generation_ms"]))
        top_reused.append({
            "id": d.get("id"), "kind": k,
            "discipline": d.get("discipline_label"),
            "topic": d.get("topic_label"),
            "usage_count": int(d.get("usage_count") or 0),
        })
        if int(d.get("reports_count") or 0) > 0:
            top_reported.append({
                "id": d.get("id"), "kind": k,
                "discipline": d.get("discipline_label"),
                "topic": d.get("topic_label"),
                "reports_count": int(d.get("reports_count") or 0),
                "usage_count": int(d.get("usage_count") or 0),
                "status": d.get("status") or STATUS_ACTIVE,
            })

    top_reused.sort(key=lambda x: x["usage_count"], reverse=True)
    top_reported.sort(key=lambda x: x["reports_count"], reverse=True)

    total_events = await db.student_content_events.count_documents({})
    events_shown = await db.student_content_events.count_documents({"event_type": "shown"})

    reuses = max(0, total_usage - total_contents)
    cache_hits = reuses
    cache_misses = total_contents
    reuse_ratio = round(reuses / total_usage, 3) if total_usage else 0

    # P1: redundant_generations = quantos docs a mais existem por fingerprint
    # (evidencia stampede histórico — depois do P0.1 deve tender a zero).
    redundant_generations = max(0, total_contents - len(unique_fingerprints))

    # Latência real de geração (baseada em generation_ms gravado no doc — P1).
    def _p(arr, p):
        if not arr: return None
        arr = sorted(arr)
        return round(arr[min(len(arr)-1, int(len(arr)*p))], 2)
    gen_avg = round(sum(gen_ms_samples)/len(gen_ms_samples), 2) if gen_ms_samples else None
    gen_p50 = _p(gen_ms_samples, 0.50)
    gen_p95 = _p(gen_ms_samples, 0.95)
    gen_p99 = _p(gen_ms_samples, 0.99)

    AVG_TOKENS_PER_GEN = 1500
    USD_PER_TOKEN = 9.0 / 1_000_000
    tokens_saved = reuses * AVG_TOKENS_PER_GEN
    usd_saved = round(tokens_saved * USD_PER_TOKEN, 4)

    # Engine metrics snapshot (in-process counters)
    engine = get_engine_metrics()

    return {
        "content_count": total_contents,
        "total_usage": total_usage,
        "reuses": reuses,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "reuse_ratio": reuse_ratio,
        "quarantined_count": quarantined_count,
        "unique_fingerprints": len(unique_fingerprints),
        "redundant_generations": redundant_generations,
        "kind_distribution": kind_dist,
        "generator_distribution": generator_dist,
        "schema_version_distribution": version_dist,
        "current_schema_version": CONTENT_SCHEMA_VERSION,
        "top_reused": top_reused[:10],
        "top_reported": top_reported[:10],
        "tokens_saved_estimated": tokens_saved,
        "usd_saved_estimated": usd_saved,
        "assumptions": {
            "avg_tokens_per_generation": AVG_TOKENS_PER_GEN,
            "usd_per_token": USD_PER_TOKEN,
            "note": "Claude Sonnet ~US$9/M tokens combined; conservative.",
        },
        "events": {"total": total_events, "shown": events_shown},
        # P1 additions
        "engine": engine,
        "generation_time_ms": {
            "avg": gen_avg, "p50": gen_p50, "p95": gen_p95, "p99": gen_p99,
            "samples": len(gen_ms_samples),
        },
        "stampede_prevention": {
            "singleflight_waits": engine["counters"]["singleflight_waits"],
            "stampede_prevented": engine["counters"]["stampede_prevented"],
            "duplicate_key_saves": engine["counters"]["duplicate_key_saves"],
        },
    }


# ─── Geração via IA (fallback quando memória não tem nada) ──────────
# ETAPA 2: a geração do Aprender Hoje passa pelo `ai_router` (Groq → OpenAI →
# Emergent), com a política central de qualidade + a política específica do
# Learning compostas ANTES do prompt do kind. Não é uma persona nova: o prompt
# por kind (formato/estrutura) permanece exatamente o mesmo.
#
#   MEDFLOW_CONTENT_POLICY + LEARNING_CONTENT_POLICY + prompt do kind
#        → ai_router (tier structured) → Groq / OpenAI / Emergent
LEARNING_CONTENT_POLICY = """[POLÍTICA ESPECÍFICA — CONTEÚDO DE ESTUDO (APRENDER HOJE)]
- O conteúdo é material de estudo autônomo: precisa ser correto sem supervisão.
- Fique estritamente dentro da disciplina/tema/subtema informados. Não troque o
  tema nem amplie o escopo por conta própria.
- Calibre a profundidade ao período informado, sem reduzir o rigor técnico.
- Se o tema informado não for reconhecível como entidade/conteúdo médico válido,
  NÃO invente conteúdo: responda com o JSON pedido explicitando a limitação no
  campo textual apropriado.
- Saída: SOMENTE o JSON pedido pelo formato do item, sem markdown, sem cercas de
  código, sem texto antes ou depois."""

# Tier/tuning do router para geração estruturada de conteúdo de estudo.
LEARNING_ROUTER_TIER = "structured"
LEARNING_ROUTER_TEMPERATURE = 0.4
LEARNING_ROUTER_MAX_TOKENS = 2400


def build_learning_system_prompt(kind_prompt: str) -> str:
    """`MEDFLOW_CONTENT_POLICY` + política do Learning + prompt do kind."""
    from content_policy import MEDFLOW_CONTENT_POLICY
    return f"{MEDFLOW_CONTENT_POLICY}\n\n{LEARNING_CONTENT_POLICY}\n\n{kind_prompt}"


async def generate_via_llm(
    kind: str,
    discipline: str,
    topic: str,
    subtopic: str | None,
    period_bucket: str,
) -> dict:
    """Gera payload estruturado (dict) via `ai_router` (tier structured).

    NUNCA use isso sem antes chamar `pick_best_content`. A ideia é que
    99% dos alunos batam em conteúdo existente com o tempo.

    Payload:
      question:    { stem, options[4], correct_index, explanation }
      flashcard:   { front, back }
      summary:     { bullets[3..7] }
      explanation: { paragraphs[2..5] }
    """
    sys_prompts = {
        "question": (
            "Você é um professor de Medicina brasileiro criando UMA questão de múltipla escolha estilo Enare/USP para revisão. "
            "Nível apropriado ao período informado. Responda APENAS com JSON válido, sem markdown, no formato: "
            "{\"stem\":\"...\",\"options\":[\"A\",\"B\",\"C\",\"D\"],\"correct_index\":0,\"explanation\":\"...\"}."
        ),
        "flashcard": (
            "Você é um professor de Medicina brasileiro criando UM flashcard curto e clínico. "
            "Responda APENAS com JSON válido: {\"front\":\"pergunta curta\",\"back\":\"resposta curta e precisa\"}."
        ),
        "summary": (
            "Você é um professor de Medicina brasileiro. Gere um resumo em bullets — objetivo, direto, sem enrolação. "
            "Responda APENAS com JSON válido: {\"bullets\":[\"...\",\"...\"]} com 3 a 7 itens."
        ),
        "explanation": (
            "Você é um professor de Medicina brasileiro. Explique o tema em 2 a 5 parágrafos, linguagem clara. "
            "Responda APENAS com JSON válido: {\"paragraphs\":[\"...\",\"...\"]}."
        ),
        "mindmap": (
            "Você é um professor de Medicina brasileiro. Gere um mapa mental hierárquico. "
            "Responda APENAS com JSON válido: {\"root\":\"tema\",\"branches\":[{\"label\":\"...\",\"children\":[\"...\"]}]}."
        ),
        "review": (
            "Você é um professor de Medicina brasileiro. Gere um roteiro de revisão em passos. "
            "Responda APENAS com JSON válido: {\"steps\":[{\"title\":\"...\",\"detail\":\"...\"}]}."
        ),
        "clinical_case": (
            "Você é um professor de Medicina brasileiro criando UM caso clínico curto para prática de raciocínio. "
            "Estrutura em 3 passos: (1) vinheta clínica objetiva com queixa principal, HDA breve, "
            "achados relevantes de exame físico e 1-3 exames complementares chave — 120 a 200 palavras. "
            "(2) UMA pergunta única de conduta (diagnóstico mais provável, próximo passo, ou conduta). "
            "(3) 4 alternativas com feedback individual explicando por que cada uma está certa ou errada. "
            "Termine com um teaching point de 1-2 frases. Nível apropriado ao período informado. "
            "Responda APENAS com JSON válido, sem markdown, no formato: "
            "{\"stem\":\"vinheta completa aqui\",\"question\":\"pergunta única\",\"options\":["
            "{\"letter\":\"A\",\"text\":\"...\",\"correct\":true,\"feedback\":\"por que essa é a certa\"},"
            "{\"letter\":\"B\",\"text\":\"...\",\"correct\":false,\"feedback\":\"por que essa está errada\"},"
            "{\"letter\":\"C\",\"text\":\"...\",\"correct\":false,\"feedback\":\"...\"},"
            "{\"letter\":\"D\",\"text\":\"...\",\"correct\":false,\"feedback\":\"...\"}"
            "],\"teaching_point\":\"síntese do ponto-chave clínico\"}."
        ),
    }
    kind_prompt = sys_prompts.get(kind, sys_prompts["summary"])
    # Composição explícita e auditável: política invariante primeiro, política
    # da operação depois, prompt do kind por último (mantém formato/estrutura).
    system_message = build_learning_system_prompt(kind_prompt)

    user_prompt = (
        f"Disciplina: {discipline}\n"
        f"Tema: {topic}\n"
        + (f"Subtema: {subtopic}\n" if subtopic else "")
        + f"Público: estudante de Medicina — {period_bucket}\n"
        + "Gere o conteúdo agora. Responda SOMENTE com o JSON, sem texto antes ou depois."
    )

    from ai_router import smart_chat

    result = await smart_chat(
        system=system_message,
        user_msg=user_prompt,
        tier=LEARNING_ROUTER_TIER,
        temperature=LEARNING_ROUTER_TEMPERATURE,
        max_tokens=LEARNING_ROUTER_MAX_TOKENS,
    )
    logger.info(
        "learning generate_via_llm: kind=%s provider=%s model=%s latency_ms=%s",
        kind, result.get("provider"), result.get("model"), result.get("latency_ms"),
    )
    raw = (result.get("text") or "").strip()
    # Remove code fences se o modelo insistir
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw).rstrip("`").strip()
    try:
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM returned invalid JSON (%s). Falling back to raw.", exc)
        payload = {"raw": raw}
    return payload


async def request_content(
    user_id: str,
    kind: str,
    discipline: str,
    topic: str,
    subtopic: str | None,
    period: int | None,
    variant: str = "default",
) -> dict:
    """Ponto de entrada único do fluxo memória-antes-de-IA (retrocompat).

    Depois do P0.1, este método é uma **fachada** sobre `remember_or_generate`
    — ganha automaticamente:
      • single-flight lock por fingerprint (não há mais stampede);
      • retry + circuit-breaker no LLM;
      • índice UNIQUE que dedupa cross-process.

    Retorno idêntico ao contrato anterior:
      `{ source: 'reused' | 'generated', content: <content_memory doc>, event_id }`.
    """
    if kind not in VALID_KINDS:
        raise ValueError(f"kind inválido: {kind}. Válidos: {sorted(VALID_KINDS)}")
    pb = _period_bucket(period)
    key_fields = {
        "discipline": discipline,
        "topic": topic,
        "subtopic": subtopic or "",
        "period_bucket": pb,
    }

    async def _gen():
        # Envolve a chamada real ao LLM em circuit-breaker + retry.
        return await call_llm_with_retry(
            lambda: generate_via_llm(kind, discipline, topic, subtopic, pb),
            label=f"llm:{kind}",
        )

    return await remember_or_generate(
        kind=kind,
        key_fields=key_fields,
        generator=_gen,
        variant=variant,
        generator_label="ai:router-structured",
        user_id=user_id,
        log_event_type="shown",
    )


# ─── P1: Unified Content Memory Engine ─────────────────────────────
# High-level API para endpoints que não se encaixam no schema clássico
# (discipline/topic/subtopic). Aceita `key_fields` genérico e um
# `generator` callable — mesma semântica cache-hit/miss + quarentena + TTL.
async def remember_or_generate(
    kind: str,
    key_fields: dict,
    generator,                # async callable → returns payload dict
    variant: str = "default",
    generator_label: str = "custom",
    user_id: str | None = None,
    log_event_type: str | None = None,
) -> dict:
    """Memoização unificada com **single-flight** (P0.1).

    Contrato:
      1) Calcula fingerprint via `compute_fingerprint_generic`.
      2) Lookup fast-path (sem lock): se hit válido → retorna reused.
      3) Cache miss → adquire lock por fingerprint:
         • re-verifica o cache dentro do lock (double-check locking);
         • se algum peer publicou → reutiliza (stampede_prevented++);
         • senão, chama `generator()` UMA vez, persiste, publica.
      4) Cross-process safety net: se o `insert_one` colidir com o
         UNIQUE partial index em (fingerprint, schema_version),
         retorna o vencedor da corrida distribuída.

    Retorno: `{"source": "reused"|"generated", "content": doc, "event_id": str|None}`.
    """
    if kind not in VALID_KINDS:
        raise ValueError(f"kind inválido: {kind}. Válidos: {sorted(VALID_KINDS)}")

    fp = compute_fingerprint_generic(kind, key_fields, variant)

    # ── Fast path (sem lock): 90% dos hits caem aqui ─────────────
    t0 = time.perf_counter()
    hit = await _lookup_active(fp)
    if hit is not None:
        await increment_usage(hit["id"])
        _metrics["cache_hits"] += 1
        _record_latency(_lat_hit_ms, (time.perf_counter() - t0) * 1000)
        evt_id = None
        if user_id and log_event_type:
            evt_id = await log_event(user_id, hit["id"], log_event_type)
        return {"source": "reused", "content": hit, "event_id": evt_id}

    # ── Slow path com single-flight ──────────────────────────────
    lock = await _acquire_fp_lock(fp)
    was_contended = lock.locked()
    async with lock:
        # Double-check dentro do lock: peer pode ter publicado enquanto esperávamos.
        if was_contended:
            _metrics["singleflight_waits"] += 1
        hit = await _lookup_active(fp)
        if hit is not None:
            if was_contended:
                _metrics["stampede_prevented"] += 1
            await increment_usage(hit["id"])
            _metrics["cache_hits"] += 1
            _record_latency(_lat_hit_ms, (time.perf_counter() - t0) * 1000)
            evt_id = None
            if user_id and log_event_type:
                evt_id = await log_event(user_id, hit["id"], log_event_type)
            await _release_fp_lock_if_idle(fp)
            return {"source": "reused", "content": hit, "event_id": evt_id}

        # Legítimo cache-miss ⇒ geramos AGORA. Sozinhos no fingerprint.
        _metrics["cache_misses"] += 1
        gen_t0 = time.perf_counter()
        try:
            payload = await generator()
            _metrics["llm_calls_ok"] += 1
        except CircuitOpenError:
            _metrics["circuit_open_rejections"] += 1
            _metrics["llm_calls_failed"] += 1
            await _release_fp_lock_if_idle(fp)
            raise
        except Exception:
            _metrics["llm_calls_failed"] += 1
            await _release_fp_lock_if_idle(fp)
            raise
        gen_ms = (time.perf_counter() - gen_t0) * 1000
        _record_latency(_lat_gen_ms, gen_ms)
        _record_latency(_lat_miss_ms, (time.perf_counter() - t0) * 1000)

        # Mapeamento canônico
        discipline = str(key_fields.get("discipline") or kind)
        topic = str(key_fields.get("topic") or kind)
        subtopic = str(key_fields.get("subtopic") or "") or None
        period_bucket = str(key_fields.get("period_bucket") or "unspecified")

        doc = {
            "id": f"cm_{uuid.uuid4().hex[:16]}",
            "fingerprint": fp,
            "schema_version": CONTENT_SCHEMA_VERSION,
            "status": STATUS_ACTIVE,
            "kind": kind,
            "discipline": _slug(discipline),
            "discipline_label": discipline,
            "topic": _slug(topic),
            "topic_label": topic,
            "subtopic": _slug(subtopic or ""),
            "subtopic_label": subtopic or "",
            "period_bucket": period_bucket,
            "variant": variant,
            "payload": payload,
            "generator": generator_label,
            "prompt_used": json.dumps({"kind": kind, "key_fields": key_fields, "variant": variant}, ensure_ascii=False),
            "usage_count": 0,
            "completion_count": 0,
            "attempts_count": 0,
            "correct_count": 0,
            "reports_count": 0,
            "generation_ms": round(gen_ms, 2),
            "created_at": _iso(_now()),
            "last_used_at": None,
            "quarantined_at": None,
        }
        try:
            await db.content_memory.insert_one(dict(doc))
        except DuplicateKeyError:
            # Cross-process race caught by UNIQUE (fingerprint, schema_version).
            # Someone else's insert landed first — adopt the winner.
            _metrics["duplicate_key_saves"] += 1
            winner = await _lookup_active(fp)
            if winner is not None:
                await increment_usage(winner["id"])
                _metrics["cache_hits"] += 1
                evt_id = None
                if user_id and log_event_type:
                    evt_id = await log_event(user_id, winner["id"], log_event_type)
                await _release_fp_lock_if_idle(fp)
                return {"source": "reused", "content": winner, "event_id": evt_id}
            # Unexpected: unique index rejected but no ACTIVE doc found.
            # Rare (all ACTIVE quarantined/expired between insert and lookup).
            # Insert with unique salt on schema_version to survive.
            doc["schema_version"] = f"{CONTENT_SCHEMA_VERSION}#salt-{uuid.uuid4().hex[:6]}"
            await db.content_memory.insert_one(dict(doc))

        doc.pop("_id", None)
        await increment_usage(doc["id"])
        evt_id = None
        if user_id and log_event_type:
            evt_id = await log_event(user_id, doc["id"], log_event_type)
        await _release_fp_lock_if_idle(fp)
        return {"source": "generated", "content": doc, "event_id": evt_id}


async def _lookup_active(fp: str) -> dict | None:
    """Retorna o melhor doc ACTIVE (não expirado) para o fingerprint, se houver."""
    query = {
        "fingerprint": fp,
        "$or": [{"status": {"$exists": False}}, {"status": STATUS_ACTIVE}],
    }
    best: dict | None = None
    async for d in db.content_memory.find(query, {"_id": 0}):
        if _is_expired(d):
            continue
        if best is None or int(d.get("usage_count") or 0) > int(best.get("usage_count") or 0):
            best = d
    return best
