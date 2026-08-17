"""MedFlow — Copiloto Acadêmico backend (thin orchestrator).

Domain logic lives under `routes/`. This file only:
- creates the FastAPI app,
- includes each domain router,
- registers CORS,
- starts the push scheduler at startup and closes the Mongo client at shutdown.

REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
"""
from __future__ import annotations

import os

from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

from core import _iso, _now, client, db, logger, require_user

if os.environ.get("SENTRY_DSN"):
    import sentry_sdk

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        environment=os.environ.get("SENTRY_ENVIRONMENT", "development"),
        release=os.environ.get("SENTRY_RELEASE") or None,
        max_request_body_size="small",
        send_default_pii=False,
        traces_sample_rate=0.1,
    )

from push_notifications import (
    build_push_router,
    fire_mental_health_alert_push,  # noqa: F401 — re-exported for routes/checkin.py backward hooks
    start_scheduler as start_push_scheduler,
)
from routes.academic import router as academic_router
from routes.auth import router as auth_router, seed_admin
from routes.checkin import router as checkin_router
from routes.iea import router as iea_router
from routes.priority import router as priority_router
from routes.habits import router as habits_router
from routes.admin import router as admin_router
from routes.admin_business import router as admin_business_router
from routes.questions import router as questions_router
from routes.confidence import router as confidence_router
from routes.profile import router as profile_router
from routes.resources import router as resources_router
from routes.support import router as support_router
from routes.tutor import router as tutor_router
from routes.pomodoro import router as pomodoro_router
from routes.insights import router as insights_router
from routes.experience import router as experience_router
from routes.telemetry import router as telemetry_router
from routes.recommendations import router as recommendations_router
from routes.learning import router as learning_router
from routes.reschedule import router as reschedule_router
from routes.integrations import router as integrations_router
from routes.smart_review import router as smart_review_router
from routes.preceptor_router import router as preceptor_router_router
from routes.missions import router as missions_router
from routes.planner import router as planner_router
from routes.community import router as community_router
from routes.resume import router as resume_router
from routes.download import router as download_router
from mip.router import router as mip_phase1_router
from mip.phase2_router import router as mip_phase2_router

app = FastAPI(title="MedFlow Copiloto Acadêmico")

# ─── P0: validação de ambiente na subida do serviço ────────────────────────
# Falha rápido com mensagem clara em vez de estourar KeyError no meio de uma
# requisição (ex.: chat do Preceptor, devolutiva, seed de admin).
_REQUIRED_ENV = [
    "MONGO_URL",
    "DB_NAME",
    "EMERGENT_LLM_KEY",
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "ADMIN_EDER_EMAIL",
    "ADMIN_EDER_PASSWORD",
    "ADMIN_CARINE_EMAIL",
    "ADMIN_CARINE_PASSWORD",
    "AI_TUTOR_DAILY_LIMIT",
    "AI_FEEDBACK_DAILY_LIMIT",
    "PREMIUM_FULL_REVIEW_QUALITY_LIMIT",
    "MIP_PHASE2_ESTIMATED_GENERATION_USD",
]
_INT_ENV = [
    "AI_TUTOR_DAILY_LIMIT",
    "AI_FEEDBACK_DAILY_LIMIT",
    "PREMIUM_FULL_REVIEW_QUALITY_LIMIT",
]


def validate_required_env() -> None:
    missing = [name for name in _REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Variáveis de ambiente obrigatórias ausentes: "
            + ", ".join(missing)
            + ". Configure-as (ver backend/.env.example) antes de iniciar o serviço."
        )
    bad_int = []
    for name in _INT_ENV:
        try:
            int(os.environ[name])
        except (TypeError, ValueError):
            bad_int.append(name)
    if bad_int:
        raise RuntimeError(
            "Variáveis que devem ser inteiras têm valor inválido: "
            + ", ".join(bad_int)
        )


@app.on_event("startup")
async def startup_validate_env() -> None:
    validate_required_env()
    logger.info("env validation ok — required variables present")


# Root ping (kept simple — no auth)
_root = APIRouter(prefix="/api")


@_root.get("/")
async def root() -> dict:
    return {"service": "medflow-copiloto-academico", "status": "ok"}


app.include_router(_root)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(academic_router)
app.include_router(iea_router)
app.include_router(checkin_router)
app.include_router(support_router)
app.include_router(resources_router)
app.include_router(priority_router)
app.include_router(habits_router)
app.include_router(admin_router)
app.include_router(admin_business_router)
app.include_router(questions_router)
app.include_router(confidence_router)
app.include_router(tutor_router)
app.include_router(pomodoro_router)
app.include_router(insights_router)
app.include_router(experience_router)
app.include_router(telemetry_router)
app.include_router(recommendations_router)
app.include_router(learning_router)
app.include_router(reschedule_router)
app.include_router(integrations_router)
app.include_router(smart_review_router)
app.include_router(preceptor_router_router)
app.include_router(missions_router)
app.include_router(planner_router)
app.include_router(community_router)
app.include_router(resume_router)
app.include_router(download_router)
app.include_router(mip_phase1_router)
app.include_router(mip_phase2_router)

# ---- Web Push notifications (Onda 4) --------------------------------------
push_router = build_push_router({
    "db": db,
    "require_user": require_user,
    "now": _now,
    "iso": _iso,
})
app.include_router(push_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client() -> None:  # pragma: no cover
    client.close()


@app.on_event("startup")
async def startup_push_scheduler() -> None:  # pragma: no cover
    try:
        start_push_scheduler(db=db, now_fn=_now, iso_fn=_iso)
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to start push scheduler: %s", exc)


@app.on_event("startup")
async def startup_seed_admin() -> None:  # pragma: no cover
    try:
        await seed_admin()
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to seed admin: %s", exc)


@app.on_event("startup")
async def startup_ai_quota_indexes() -> None:  # pragma: no cover
    try:
        from ai_quota import ensure_ai_quota_indexes

        await ensure_ai_quota_indexes()
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to ensure AI quota indexes: %s", exc)


@app.on_event("startup")
async def startup_content_memory_indexes() -> None:  # pragma: no cover
    """P0.1 — Cria índices do Content Memory Engine na subida do serviço.

    Idempotente e barato: `create_index` é no-op se já existe.
    """
    try:
        from learning_memory import ensure_indexes as ensure_cm_indexes
        result = await ensure_cm_indexes()
        logger.info("content_memory indexes ready: %s", result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to ensure content_memory indexes: %s", exc)


@app.on_event("startup")
async def startup_mip_phase1_indexes() -> None:  # pragma: no cover
    try:
        from mip.trace_store import ensure_shadow_indexes

        await ensure_shadow_indexes()
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to ensure MIP phase1 indexes: %s", exc)


@app.on_event("startup")
async def startup_mip_phase2_indexes() -> None:  # pragma: no cover
    try:
        from mip.phase2_store import ensure_phase2_indexes

        await ensure_phase2_indexes()
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to ensure MIP phase2 indexes: %s", exc)


@app.on_event("startup")
async def startup_confidence_indexes() -> None:  # pragma: no cover
    try:
        from routes.confidence import ensure_confidence_indexes

        await ensure_confidence_indexes()
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to ensure confidence shadow indexes: %s", exc)
