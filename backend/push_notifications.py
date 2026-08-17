"""Web Push notifications (VAPID) + APScheduler jobs for MedFlow Copiloto.

Design goals:
- Fully additive to server.py: no changes to existing endpoints beyond one hook.
- Idempotent: every send is deduped via notification_log with a stable dedup_key.
- Robust: 404/410 responses from push service delete the subscription.
- User control: preferences per event class stored on user_profiles.notification_prefs.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from pywebpush import WebPushException, webpush

logger = logging.getLogger("medflow.push")

# --- VAPID configuration ---------------------------------------------------
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:copiloto@medflow.app")
VAPID_CLAIMS = {"sub": VAPID_SUBJECT}

# Event classes users can toggle
EVENT_CLASSES = {
    "checkin",         # daily reminder
    "missions",        # end-of-day pending missions
    "exams",           # 3d and 24h before an exam
    "mental_health",   # instant on new alert
    "streak",          # streak at risk (no check-in in 24h)
    "digest",          # weekly digest (Sunday)
}

DEFAULT_PREFS: Dict[str, bool] = {c: True for c in EVENT_CLASSES}


class SubscribeInput(BaseModel):
    endpoint: str
    expirationTime: Optional[int] = None
    keys: Dict[str, str]
    user_agent: Optional[str] = None
    tz: Optional[str] = None


class PreferencesInput(BaseModel):
    checkin: Optional[bool] = None
    missions: Optional[bool] = None
    exams: Optional[bool] = None
    mental_health: Optional[bool] = None
    streak: Optional[bool] = None
    digest: Optional[bool] = None
    tz: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    wake_hour: Optional[int] = None  # 5..11
    exam_alert_lead_days: Optional[int] = None  # 1 or 3


class TestPushInput(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None


class OnboardingInput(BaseModel):
    wake_hour: int = Field(ge=4, le=12)
    exam_alert_lead_days: int  # 1 or 3
    digest_sunday: bool
    tz: Optional[str] = None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
def build_push_router(deps: Dict[str, Any]) -> APIRouter:
    """Router factory. Deps contains: db, require_user, now, iso.

    Kept factory-based so this module has no import-time coupling to server.py.
    """
    db = deps["db"]
    require_user = deps["require_user"]
    now_fn = deps["now"]
    iso_fn = deps["iso"]

    router = APIRouter(prefix="/api/push", tags=["push"])

    @router.get("/config")
    async def push_config(user: dict = Depends(require_user)) -> dict:
        if not VAPID_PUBLIC_KEY:
            raise HTTPException(status_code=503, detail="Push service não configurado")
        return {
            "vapid_public_key": VAPID_PUBLIC_KEY,
            "subject": VAPID_SUBJECT,
            "supported_events": sorted(EVENT_CLASSES),
        }

    @router.post("/subscribe")
    async def push_subscribe(
        payload: SubscribeInput = Body(...),
        user: dict = Depends(require_user),
    ) -> dict:
        if not VAPID_PUBLIC_KEY:
            raise HTTPException(status_code=503, detail="Push service não configurado")
        doc = {
            "user_id": user["user_id"],
            "endpoint": payload.endpoint,
            "keys": payload.keys,
            "expiration_time": payload.expirationTime,
            "user_agent": payload.user_agent,
            "created_at": iso_fn(now_fn()),
            "last_success_at": None,
            "failure_count": 0,
        }
        await db.push_subscriptions.update_one(
            {"user_id": user["user_id"], "endpoint": payload.endpoint},
            {"$set": doc},
            upsert=True,
        )
        # Update profile prefs if tz provided
        if payload.tz:
            await db.user_profiles.update_one(
                {"user_id": user["user_id"]},
                {"$set": {"tz": payload.tz, "updated_at": iso_fn(now_fn())}},
                upsert=True,
            )
        # Ensure notifications are enabled and prefs default to True on first subscribe
        await db.user_profiles.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"notifications_enabled": True}, "$setOnInsert": {"notification_prefs": DEFAULT_PREFS}},
            upsert=True,
        )
        return {"ok": True}

    @router.delete("/subscribe")
    async def push_unsubscribe(
        endpoint: str, user: dict = Depends(require_user)
    ) -> dict:
        await db.push_subscriptions.delete_one(
            {"user_id": user["user_id"], "endpoint": endpoint}
        )
        return {"ok": True}

    @router.get("/preferences")
    async def get_preferences(user: dict = Depends(require_user)) -> dict:
        prof = await db.user_profiles.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
        prefs = {**DEFAULT_PREFS, **(prof.get("notification_prefs") or {})}
        return {
            "notifications_enabled": bool(prof.get("notifications_enabled", False)),
            "tz": prof.get("tz", "America/Sao_Paulo"),
            "wake_hour": int(prof.get("wake_hour", 8)),
            "exam_alert_lead_days": int(prof.get("exam_alert_lead_days", 3)),
            "onboarding_completed": bool(prof.get("onboarding_completed", False)),
            "preferences": prefs,
        }

    @router.patch("/preferences")
    async def patch_preferences(
        payload: PreferencesInput = Body(...),
        user: dict = Depends(require_user),
    ) -> dict:
        data = payload.model_dump(exclude_none=True)
        updates: Dict[str, Any] = {"updated_at": iso_fn(now_fn())}
        if "tz" in data:
            tz = data.pop("tz")
            try:
                pytz.timezone(tz)
            except Exception:
                raise HTTPException(status_code=400, detail="Timezone inválido")
            updates["tz"] = tz
        if "notifications_enabled" in data:
            updates["notifications_enabled"] = bool(data.pop("notifications_enabled"))
        if "wake_hour" in data:
            wh = int(data.pop("wake_hour"))
            if not (4 <= wh <= 12):
                raise HTTPException(status_code=400, detail="wake_hour fora do intervalo")
            updates["wake_hour"] = wh
        if "exam_alert_lead_days" in data:
            lead = int(data.pop("exam_alert_lead_days"))
            if lead not in (1, 3):
                raise HTTPException(status_code=400, detail="exam_alert_lead_days deve ser 1 ou 3")
            updates["exam_alert_lead_days"] = lead
        prefs_update: Dict[str, Any] = {}
        for k, v in data.items():
            if k in EVENT_CLASSES:
                prefs_update[f"notification_prefs.{k}"] = bool(v)
        updates.update(prefs_update)
        await db.user_profiles.update_one(
            {"user_id": user["user_id"]}, {"$set": updates}, upsert=True
        )
        prof = await db.user_profiles.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
        prefs = {**DEFAULT_PREFS, **(prof.get("notification_prefs") or {})}
        return {
            "notifications_enabled": bool(prof.get("notifications_enabled", False)),
            "tz": prof.get("tz", "America/Sao_Paulo"),
            "wake_hour": int(prof.get("wake_hour", 8)),
            "exam_alert_lead_days": int(prof.get("exam_alert_lead_days", 3)),
            "onboarding_completed": bool(prof.get("onboarding_completed", False)),
            "preferences": prefs,
        }

    @router.post("/test")
    async def push_test(
        payload: TestPushInput = Body(default_factory=TestPushInput),
        user: dict = Depends(require_user),
    ) -> dict:
        result = await send_to_user(
            db=db,
            user_id=user["user_id"],
            title=payload.title or "MedFlow — teste de notificação",
            body=payload.body or "Se você recebeu isto, o push está funcionando.",
            url="/dashboard",
            tag="test",
            event_class="checkin",  # bypass class dedup — test always fires
            dedup_key=f"test_{iso_fn(now_fn())}",
            override_prefs=True,
            now_fn=now_fn,
            iso_fn=iso_fn,
        )
        return result

    @router.post("/onboarding")
    async def onboarding_complete(
        payload: OnboardingInput = Body(...),
        user: dict = Depends(require_user),
    ) -> dict:
        if payload.exam_alert_lead_days not in (1, 3):
            raise HTTPException(status_code=400, detail="exam_alert_lead_days deve ser 1 ou 3")
        # Ensure profile exists with default prefs first (so we can safely $set sub-paths after).
        await db.user_profiles.update_one(
            {"user_id": user["user_id"]},
            {"$setOnInsert": {
                "user_id": user["user_id"],
                "notification_prefs": DEFAULT_PREFS,
                "created_at": iso_fn(now_fn()),
            }},
            upsert=True,
        )
        updates: Dict[str, Any] = {
            "wake_hour": int(payload.wake_hour),
            "exam_alert_lead_days": int(payload.exam_alert_lead_days),
            "onboarding_completed": True,
            "notifications_enabled": True,
            "notification_prefs.digest": bool(payload.digest_sunday),
            "updated_at": iso_fn(now_fn()),
        }
        if payload.tz:
            try:
                pytz.timezone(payload.tz)
                updates["tz"] = payload.tz
            except Exception:
                raise HTTPException(status_code=400, detail="Timezone inválido")
        await db.user_profiles.update_one(
            {"user_id": user["user_id"]}, {"$set": updates}
        )
        prof = await db.user_profiles.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
        prefs = {**DEFAULT_PREFS, **(prof.get("notification_prefs") or {})}
        return {
            "ok": True,
            "notifications_enabled": True,
            "tz": prof.get("tz", "America/Sao_Paulo"),
            "wake_hour": int(prof.get("wake_hour", 8)),
            "exam_alert_lead_days": int(prof.get("exam_alert_lead_days", 3)),
            "onboarding_completed": True,
            "preferences": prefs,
        }

    @router.get("/stats")
    async def push_stats(user: dict = Depends(require_user)) -> dict:
        """Delivered notifications counter for the current user (used in Profile)."""
        delivered = await db.notification_log.count_documents({"user_id": user["user_id"]})
        subs = await db.push_subscriptions.count_documents({"user_id": user["user_id"]})
        # Last delivered
        last = await db.notification_log.find_one(
            {"user_id": user["user_id"]},
            {"_id": 0, "created_at": 1, "title": 1, "event_class": 1},
            sort=[("created_at", -1)],
        )
        return {
            "delivered_total": delivered,
            "subscriptions": subs,
            "last_delivered": last,
        }

    return router


# ---------------------------------------------------------------------------
# Core send functions
# ---------------------------------------------------------------------------
async def send_to_user(
    *,
    db,
    user_id: str,
    title: str,
    body: str,
    url: str = "/dashboard",
    tag: Optional[str] = None,
    event_class: str = "checkin",
    dedup_key: Optional[str] = None,
    override_prefs: bool = False,
    icon: str = "/favicon.png",
    now_fn=None,
    iso_fn=None,
) -> Dict[str, int]:
    """Send a push to all subscriptions of a user, respecting prefs + dedup."""
    if now_fn is None:
        now_fn = lambda: datetime.now(timezone.utc)  # noqa: E731
    if iso_fn is None:
        iso_fn = lambda d: d.astimezone(timezone.utc).isoformat()  # noqa: E731

    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        logger.warning("push disabled — VAPID keys missing")
        return {"sent": 0, "failed": 0}

    # Load profile + check prefs
    prof = await db.user_profiles.find_one({"user_id": user_id}, {"_id": 0}) or {}
    if not override_prefs:
        if not prof.get("notifications_enabled", True):
            return {"sent": 0, "failed": 0}
        prefs = {**DEFAULT_PREFS, **(prof.get("notification_prefs") or {})}
        if event_class in EVENT_CLASSES and not prefs.get(event_class, True):
            return {"sent": 0, "failed": 0}

    # Dedup
    if dedup_key:
        exists = await db.notification_log.find_one(
            {"user_id": user_id, "dedup_key": dedup_key}, {"_id": 1}
        )
        if exists:
            return {"sent": 0, "failed": 0, "skipped_dedup": 1}

    subs = await db.push_subscriptions.find({"user_id": user_id}).to_list(20)
    if not subs:
        return {"sent": 0, "failed": 0}

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "tag": tag or event_class,
        "icon": icon,
    }).encode("utf-8")

    sent = 0
    failed = 0
    loop = asyncio.get_running_loop()
    # Retry policy: for transient failures (5xx, timeouts) — 3 tries with backoff 1s, 2s, 4s.
    # 404/410 => remove sub, no retry. 4xx (400/401/403/413/etc) => no retry, count failure.
    MAX_ATTEMPTS = 3
    RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
    for sub in subs:
        attempt = 0
        delivered = False
        last_status: Optional[int] = None
        while attempt < MAX_ATTEMPTS and not delivered:
            attempt += 1
            try:
                def _send():
                    webpush(
                        subscription_info={
                            "endpoint": sub["endpoint"],
                            "keys": sub["keys"],
                        },
                        data=payload,
                        vapid_private_key=VAPID_PRIVATE_KEY,
                        vapid_claims={"sub": VAPID_SUBJECT},
                        ttl=60 * 60 * 24,
                    )
                await loop.run_in_executor(None, _send)
                delivered = True
                sent += 1
                await db.push_subscriptions.update_one(
                    {"_id": sub["_id"]},
                    {"$set": {
                        "last_success_at": iso_fn(now_fn()),
                        "last_error": None,
                        "failure_count": 0,
                    }, "$inc": {"delivered_count": 1}},
                )
            except WebPushException as exc:
                last_status = getattr(exc.response, "status_code", None) if exc.response is not None else None
                if last_status in (404, 410):
                    await db.push_subscriptions.delete_one({"_id": sub["_id"]})
                    logger.info("push subscription gone (%s), deleted for %s", last_status, user_id)
                    break
                if last_status in RETRYABLE_STATUS and attempt < MAX_ATTEMPTS:
                    backoff = 2 ** (attempt - 1)  # 1s, 2s, 4s
                    logger.info("push retry %d/%d in %ds (status=%s) for %s",
                                attempt, MAX_ATTEMPTS, backoff, last_status, user_id)
                    await asyncio.sleep(backoff)
                    continue
                # non-retryable or exhausted
                await db.push_subscriptions.update_one(
                    {"_id": sub["_id"]},
                    {"$inc": {"failure_count": 1},
                     "$set": {"last_error": f"status={last_status}", "last_error_at": iso_fn(now_fn())}},
                )
                logger.warning("push send failed (%s, attempt %d) for %s: %s",
                               last_status, attempt, user_id, exc)
                break
            except Exception as exc:  # noqa: BLE001
                # Network-level errors: retry with backoff
                if attempt < MAX_ATTEMPTS:
                    backoff = 2 ** (attempt - 1)
                    logger.info("push retry %d/%d in %ds (network) for %s: %s",
                                attempt, MAX_ATTEMPTS, backoff, user_id, exc)
                    await asyncio.sleep(backoff)
                    continue
                logger.exception("unexpected push failure after %d attempts: %s", attempt, exc)
                await db.push_subscriptions.update_one(
                    {"_id": sub["_id"]},
                    {"$inc": {"failure_count": 1},
                     "$set": {"last_error": "network", "last_error_at": iso_fn(now_fn())}},
                )
                break
        if not delivered:
            failed += 1

    if dedup_key and sent > 0:
        await db.notification_log.insert_one({
            "user_id": user_id,
            "event_class": event_class,
            "dedup_key": dedup_key,
            "title": title,
            "body": body,
            "url": url,
            "created_at": iso_fn(now_fn()),
        })
    return {"sent": sent, "failed": failed}


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
_scheduler: Optional[AsyncIOScheduler] = None


def _local_hour(tz_name: str, now_utc: datetime) -> int:
    try:
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = pytz.timezone("America/Sao_Paulo")
    return now_utc.astimezone(tz).hour


def _local_dow(tz_name: str, now_utc: datetime) -> int:
    """Monday=0 ... Sunday=6 in the user's local time."""
    try:
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = pytz.timezone("America/Sao_Paulo")
    return now_utc.astimezone(tz).weekday()


def _local_date_key(tz_name: str, now_utc: datetime) -> str:
    try:
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = pytz.timezone("America/Sao_Paulo")
    return now_utc.astimezone(tz).date().isoformat()


async def _iter_subscribed_users(db) -> List[dict]:
    endpoints = await db.push_subscriptions.aggregate([
        {"$group": {"_id": "$user_id"}},
    ]).to_list(10000)
    user_ids = [e["_id"] for e in endpoints]
    if not user_ids:
        return []
    profs = await db.user_profiles.find({"user_id": {"$in": user_ids}}).to_list(10000)
    prof_by_id = {p["user_id"]: p for p in profs}
    return [
        {
            "user_id": uid,
            "tz": (prof_by_id.get(uid) or {}).get("tz", "America/Sao_Paulo"),
            "prefs": {**DEFAULT_PREFS, **((prof_by_id.get(uid) or {}).get("notification_prefs") or {})},
            "notifications_enabled": bool(
                (prof_by_id.get(uid) or {}).get("notifications_enabled", True)
            ),
            "wake_hour": int((prof_by_id.get(uid) or {}).get("wake_hour", 8)),
            "exam_alert_lead_days": int(
                (prof_by_id.get(uid) or {}).get("exam_alert_lead_days", 3)
            ),
            "remind_water": bool((prof_by_id.get(uid) or {}).get("remind_water", False)),
            "remind_stretch": bool((prof_by_id.get(uid) or {}).get("remind_stretch", False)),
        }
        for uid in user_ids
    ]


async def _job_selfcare(db, now_fn, iso_fn) -> None:
    """Onda 5 — Lembretes de autocuidado (água / alongue).

    Roda a cada hora (minuto :20). Envia com base no horário local do usuário:
    - Água: a cada 3h dentro da janela wake_hour..22h.
    - Alongue: 3 vezes ao dia — 10h, 14h, 17h.
    """
    users = await _iter_subscribed_users(db)
    now = now_fn()
    for u in users:
        if not u["notifications_enabled"]:
            continue
        lh = _local_hour(u["tz"], now)
        ldate = _local_date_key(u["tz"], now)
        wake = u.get("wake_hour", 8)

        # Água: começa em wake e repete a cada 3h até 22h (usa horários fixos derivados)
        if u["remind_water"] and lh >= wake and lh <= 22:
            water_hours = {wake, wake + 3, wake + 6, wake + 9, wake + 12}
            if lh in water_hours:
                await send_to_user(
                    db=db, user_id=u["user_id"],
                    title="Hora de beber água 💧",
                    body="Um copo agora. Cérebro hidratado = foco melhor.",
                    url="/dashboard",
                    tag="selfcare-water",
                    event_class="selfcare",
                    dedup_key=f"water_{lh}h_{ldate}",
                    now_fn=now_fn, iso_fn=iso_fn,
                )

        # Alongue: 10h / 14h / 17h
        if u["remind_stretch"] and lh in (10, 14, 17):
            await send_to_user(
                db=db, user_id=u["user_id"],
                title="Levante e alongue por 2 minutos",
                body="Pescoço, ombros, costas. Volta melhor pro próximo bloco.",
                url="/dashboard",
                tag="selfcare-stretch",
                event_class="selfcare",
                dedup_key=f"stretch_{lh}h_{ldate}",
                now_fn=now_fn, iso_fn=iso_fn,
            )


async def _job_reminders(db, now_fn, iso_fn) -> None:
    """Runs every 15 minutes. Fires check-in reminder, streak-at-risk and missions-pending
    based on each user's local time."""
    users = await _iter_subscribed_users(db)
    now = now_fn()
    for u in users:
        if not u["notifications_enabled"]:
            continue
        lh = _local_hour(u["tz"], now)
        ldate = _local_date_key(u["tz"], now)

        # --- Check-in reminder at user's wake_hour and 20h ---
        wake = u.get("wake_hour", 8)
        if u["prefs"].get("checkin", True) and lh in (wake, 20):
            # skip if user already checked in today
            has_checkin = await db.checkins.find_one({
                "user_id": u["user_id"],
                "created_at": {"$regex": f"^{ldate}"},
            }, {"_id": 1})
            if not has_checkin:
                await send_to_user(
                    db=db, user_id=u["user_id"],
                    title="Como você está agora?",
                    body="Um check-in de 30s recalibra o copiloto pro resto do dia.",
                    url="/checkin",
                    tag="checkin-reminder",
                    event_class="checkin",
                    dedup_key=f"checkin_{lh}h_{ldate}",
                    now_fn=now_fn, iso_fn=iso_fn,
                )

        # --- Missions pending at end of day (19h) ---
        if u["prefs"].get("missions", True) and lh == 19:
            bundle = await db.missions_bundles.find_one({
                "user_id": u["user_id"], "date": ldate,
            }, {"_id": 0})
            if bundle:
                pending = [m for m in (bundle.get("missions") or [])
                           if not m.get("completed") and not m.get("skipped")]
                if pending:
                    top = pending[0]
                    await send_to_user(
                        db=db, user_id=u["user_id"],
                        title=f"Ainda dá tempo — {len(pending)} recomendaç{'ões' if len(pending) > 1 else 'ão'} pra hoje",
                        body=top.get("title") or "Abra o dashboard e siga a próxima decisão.",
                        url="/dashboard",
                        tag="missions-pending",
                        event_class="missions",
                        dedup_key=f"missions_{ldate}",
                        now_fn=now_fn, iso_fn=iso_fn,
                    )

        # --- Streak at risk between 20h and 22h ---
        if u["prefs"].get("streak", True) and lh in (20, 21):
            last = await db.checkins.find_one(
                {"user_id": u["user_id"]},
                {"created_at": 1},
                sort=[("created_at", -1)],
            )
            if last:
                try:
                    last_at = datetime.fromisoformat(str(last["created_at"]).replace("Z", "+00:00"))
                except Exception:
                    last_at = None
                if last_at and (now - last_at).total_seconds() >= 20 * 3600:
                    await send_to_user(
                        db=db, user_id=u["user_id"],
                        title="Seu ritmo está prestes a pausar",
                        body="Um check-in curto agora mantém sua sequência ativa.",
                        url="/checkin",
                        tag="streak-risk",
                        event_class="streak",
                        dedup_key=f"streak_{ldate}",
                        now_fn=now_fn, iso_fn=iso_fn,
                    )


async def _job_exams(db, now_fn, iso_fn) -> None:
    """Runs hourly. Emits 3d and 24h alerts per user exam."""
    users = await _iter_subscribed_users(db)
    if not users:
        return
    user_map = {u["user_id"]: u for u in users}
    exams = await db.exams.find({"user_id": {"$in": list(user_map)}}).to_list(2000)
    now = now_fn()
    for exam in exams:
        u = user_map.get(exam["user_id"])
        if not u or not u["notifications_enabled"]:
            continue
        if not u["prefs"].get("exams", True):
            continue
        d_str = exam.get("date")
        if not d_str:
            continue
        try:
            due = datetime.fromisoformat(f"{d_str}T09:00:00").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        delta_h = (due - now).total_seconds() / 3600.0
        exam_name = exam.get("name") or "Prova"
        lead = u.get("exam_alert_lead_days", 3)
        if 20 <= delta_h <= 24:
            await send_to_user(
                db=db, user_id=exam["user_id"],
                title=f"{exam_name} em 24h",
                body="Última reta. Prioridade máxima às revisões de fixação.",
                url="/subjects",
                tag=f"exam-{exam.get('id')}",
                event_class="exams",
                dedup_key=f"exam24_{exam.get('id')}",
                now_fn=now_fn, iso_fn=iso_fn,
            )
        elif lead == 3 and 68 <= delta_h <= 72:
            await send_to_user(
                db=db, user_id=exam["user_id"],
                title=f"{exam_name} em 3 dias",
                body="Hora de virar o modo Prova. Distribua revisões espaçadas.",
                url="/subjects",
                tag=f"exam-{exam.get('id')}",
                event_class="exams",
                dedup_key=f"exam3d_{exam.get('id')}",
                now_fn=now_fn, iso_fn=iso_fn,
            )


async def _job_weekly_digest(db, now_fn, iso_fn) -> None:
    """Runs hourly. Only fires at Sunday 18h local per user."""
    users = await _iter_subscribed_users(db)
    now = now_fn()
    for u in users:
        if not u["notifications_enabled"] or not u["prefs"].get("digest", True):
            continue
        if _local_dow(u["tz"], now) != 6:  # Sunday
            continue
        if _local_hour(u["tz"], now) != 18:
            continue
        ldate = _local_date_key(u["tz"], now)
        # Weekly aggregates
        week_ago = (now - timedelta(days=7)).isoformat()
        checkins = await db.checkins.count_documents({
            "user_id": u["user_id"], "created_at": {"$gte": week_ago},
        })
        bundles = await db.missions_bundles.find({
            "user_id": u["user_id"], "date": {"$gte": (now - timedelta(days=7)).date().isoformat()},
        }).to_list(20)
        completed = sum(1 for b in bundles for m in (b.get("missions") or []) if m.get("completed"))
        await send_to_user(
            db=db, user_id=u["user_id"],
            title="Sua semana no MedFlow",
            body=f"{checkins} check-ins • {completed} recomendações seguidas. Toque para ver os padrões.",
            url="/history",
            tag="weekly-digest",
            event_class="digest",
            dedup_key=f"digest_{ldate}",
            now_fn=now_fn, iso_fn=iso_fn,
        )


def start_scheduler(*, db, now_fn, iso_fn) -> AsyncIOScheduler:
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler
    scheduler = AsyncIOScheduler(timezone=pytz.utc)
    scheduler.add_job(
        _job_reminders, CronTrigger(minute="0,15,30,45"),
        args=[db, now_fn, iso_fn], id="reminders", replace_existing=True,
        max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        _job_exams, CronTrigger(minute="5"),
        args=[db, now_fn, iso_fn], id="exams", replace_existing=True,
        max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        _job_weekly_digest, CronTrigger(minute="10"),
        args=[db, now_fn, iso_fn], id="digest", replace_existing=True,
        max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        _job_selfcare, CronTrigger(minute="20"),
        args=[db, now_fn, iso_fn], id="selfcare", replace_existing=True,
        max_instances=1, coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("push scheduler started with jobs: reminders/exams/digest/selfcare")
    return scheduler


async def fire_mental_health_alert_push(
    *, db, user_id: str, level: str, alert_id: str, now_fn, iso_fn
) -> Dict[str, int]:
    """Instant push when a new mental-health alert is created."""
    if level == "high":
        title = "Você não precisa passar por isso sozinho"
        body = "CVV 188 atende 24h, sigiloso. Estamos aqui."
    else:
        title = "Um sinal para cuidar hoje"
        body = "Abrimos a Rede de Apoio pra você. Sem pressa."
    return await send_to_user(
        db=db, user_id=user_id,
        title=title, body=body,
        url="/support", tag="mental-health",
        event_class="mental_health",
        dedup_key=f"mh_{alert_id}",
        now_fn=now_fn, iso_fn=iso_fn,
    )
