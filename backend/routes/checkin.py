"""Check-in + recommendations + feedback + mood + history + legacy modes + mindfulness."""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from core import EMERGENT_LLM_KEY, _clean, _iso, _now, _today_str, db, require_user
from models import (
    CheckinInput,
    ExamModeInput,
    FeedbackInput,
    MindfulnessLogInput,
    MoodLogInput,
    OnCallInput,
)
from routes.iea import maybe_award_badges
from routes.profile import get_profile_doc
from routes.support import (
    detect_high_risk,
    detect_medium_risk_keywords,
    llm_classify_mental_health,
    mental_health_message,
    persist_mental_health_alert,
)

logger = logging.getLogger("medflow.checkin")
router = APIRouter(prefix="/api", tags=["checkin"])


DOMAIN_RULES_LEGACY = """
Você é o MedFlow. Responda sempre em pt-BR com uma única ação executável agora, em uma frase curta (máx 22 palavras). Sem emojis, aspas, markdown. Nada de diagnósticos.

Devolva EXCLUSIVAMENTE um JSON válido:
{"action": "<frase única>", "category": "<rest|study|mindfulness|movement|hydration|social|admin>", "rationale": "<porquê curto>"}
""".strip()


def _quota_fallback_recommendation() -> dict:
    return {
        "action": "Escolha uma tarefa de até 10 minutos e comece pelo primeiro passo agora.",
        "category": "study",
        "rationale": "Seu limite diário de recomendações inteligentes foi atingido.",
        "generation_source": "quota_fallback",
        "quota_limited": True,
    }


async def _generate_recommendation(prompt: str, user_id: str) -> dict:
    from ai_quota import consume_ai_quota
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    await consume_ai_quota(user_id, "feedback")
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"medflow-rec-{uuid.uuid4().hex[:10]}",
        system_message=DOMAIN_RULES_LEGACY,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")
    try:
        reply = await chat.send_message(UserMessage(text=prompt))
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM call failed: %s", exc)
        return {
            "action": "Beba um copo de água e faça 3 respirações profundas antes do próximo passo.",
            "category": "mindfulness",
            "rationale": "pausa breve estabiliza o foco",
            "generation_source": "fallback_static",
        }
    text = reply.strip() if isinstance(reply, str) else str(reply)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            return {
                "action": str(data.get("action", "")).strip(),
                "category": str(data.get("category", "rest")).strip(),
                "rationale": str(data.get("rationale", "")).strip(),
                "generation_source": "llm",
            }
        except Exception:
            pass
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), text)
    return {
        "action": line[:220],
        "category": "rest",
        "rationale": "",
        "generation_source": "llm",
    }


@router.post("/checkin")
async def submit_checkin(payload: CheckinInput, user: dict = Depends(require_user)) -> dict:
    # Import push helper lazily to avoid circular init at module load time
    from push_notifications import fire_mental_health_alert_push

    user_id = user["user_id"]
    checkin_id = f"chk_{uuid.uuid4().hex[:12]}"
    now = _now()
    doc = payload.model_dump()
    doc.update({"id": checkin_id, "user_id": user_id, "created_at": _iso(now)})
    await db.checkins.insert_one(dict(doc))

    # ---- Mental-health signal detection (Onda 3.2) ----
    mental_health_alert: Optional[dict] = None
    free_text = (payload.free_text or "").strip()
    detected_level = "none"
    detected_tags: list[str] = []
    detected_summary = ""
    if detect_high_risk(free_text):
        detected_level = "high"
        detected_tags = ["ideacao_suicida"]
        detected_summary = "sinal explícito no free-text"
    elif free_text:
        llm_result = await llm_classify_mental_health(free_text)
        detected_level = llm_result["level"]
        detected_tags = llm_result["tags"]
        detected_summary = llm_result["summary"]
        med_hits = detect_medium_risk_keywords(free_text)
        if med_hits and detected_level == "low":
            detected_level = "medium"
            for h in med_hits[:3]:
                if h not in detected_tags:
                    detected_tags.append(h)

    scale_signal = payload.mood <= 1 and payload.stress >= 5
    if scale_signal and detected_level in {"none", "low"}:
        detected_level = "medium"
        if "sobrecarga" not in detected_tags:
            detected_tags.append("sobrecarga")
        detected_summary = detected_summary or "mood=1 e stress=5 no check-in"
        source = "checkin_scale"
    else:
        source = "checkin_free_text"

    if detected_level in {"medium", "high"}:
        message, suggested = mental_health_message(detected_level)
        alert_doc = await persist_mental_health_alert(
            user_id=user_id, level=detected_level, tags=detected_tags,
            summary=detected_summary, checkin_id=checkin_id,
            source=source, suggested=suggested,
        )
        mental_health_alert = {
            "id": alert_doc["id"],
            "level": detected_level,
            "tags": detected_tags,
            "summary": detected_summary,
            "message": message,
            "suggested_contacts": suggested,
        }
        try:
            await fire_mental_health_alert_push(
                db=db, user_id=user_id, level=detected_level,
                alert_id=alert_doc["id"], now_fn=_now, iso_fn=_iso,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("push MH alert failed: %s", exc)

    profile = await get_profile_doc(user_id)
    parts = [
        f"Sono: {payload.sleep_hours}h",
        f"Energia (1-5): {payload.energy}",
        f"Humor (1-5): {payload.mood}",
        f"Stress (1-5): {payload.stress}",
        f"Modo: {profile.get('mode', 'rotina')}",
    ]
    if payload.upcoming_exam:
        parts.append(f"Prova próxima: {payload.exam_name or ''} em {payload.exam_date or ''}")
    if payload.on_call_today:
        parts.append("Está em plantão hoje.")
    if payload.commitments:
        parts.append(f"Compromissos: {payload.commitments}")
    if payload.free_text:
        parts.append(f"Nota: {payload.free_text}")

    # ── P1: Content Memory Engine unificado ────────────────────────
    # Fingerprint por buckets grossos (não por texto livre) → cross-user
    # reuse alto para estados comuns (ex: dormiu mal + alta ansiedade + prova
    # amanhã). free_text é ignorado no key: o motor já detectou risco em MH.
    import learning_memory as lm
    def _bucket(v, lo, hi):
        try:
            x = int(v)
        except Exception:
            return "unspecified"
        return "low" if x <= lo else "high" if x >= hi else "mid"

    key_fields = {
        "discipline": "checkin",
        "topic": f"mode-{profile.get('mode', 'rotina')}",
        "subtopic": (
            f"sl-{_bucket(payload.sleep_hours, 5, 7)}"
            f"_en-{_bucket(payload.energy, 2, 4)}"
            f"_mo-{_bucket(payload.mood, 2, 4)}"
            f"_st-{_bucket(payload.stress, 2, 4)}"
        ),
        "period_bucket": lm._period_bucket(profile.get("period_number") or profile.get("semester")),
    }
    variant = "exam" if payload.upcoming_exam else ("oncall" if payload.on_call_today else "default")

    prompt_text = "\n".join(parts)
    async def _gen_checkin_rec() -> dict:
        return await _generate_recommendation(prompt_text, user_id)

    from ai_quota import has_ai_quota

    if not await has_ai_quota(user_id, "feedback"):
        rec = _quota_fallback_recommendation()
        memo = {"content": {"id": None}, "source": "quota_fallback"}
    else:
        try:
            memo = await lm.remember_or_generate(
                kind="checkin_rec",
                key_fields=key_fields,
                generator=_gen_checkin_rec,
                variant=variant,
                generator_label="ai:claude-sonnet-4-5",
            )
            rec = memo["content"]["payload"]
        except HTTPException as exc:
            if exc.status_code != 429:
                raise
            rec = _quota_fallback_recommendation()
            memo = {"content": {"id": None}, "source": "quota_fallback"}

    rec_id = f"rec_{uuid.uuid4().hex[:12]}"
    rec_doc = {"id": rec_id, "user_id": user_id, "checkin_id": checkin_id,
               "action": rec["action"], "category": rec["category"],
               "rationale": rec.get("rationale", ""),
               "generation_source": rec.get("generation_source", "llm"),
               "content_id": memo["content"]["id"],
               "content_source": memo["source"],
               "created_at": _iso(now)}
    await db.recommendations.insert_one(dict(rec_doc))

    # Regenerate missions for today (context changed)
    await db.missions_bundles.delete_one({"user_id": user_id, "date": _today_str()})
    return {
        "checkin_id": checkin_id,
        "recommendation": _clean(rec_doc),
        "mental_health_alert": mental_health_alert,
    }


@router.get("/recommendation/latest")
async def latest_recommendation(user: dict = Depends(require_user)) -> dict:
    doc = await db.recommendations.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}, sort=[("created_at", -1)]
    )
    if not doc:
        return {"recommendation": None}
    fb = await db.feedback.find_one(
        {"recommendation_id": doc["id"]}, {"_id": 0}, sort=[("created_at", -1)]
    )
    return {"recommendation": doc, "feedback": fb}


@router.post("/feedback")
async def submit_feedback(payload: FeedbackInput, user: dict = Depends(require_user)) -> dict:
    rec = await db.recommendations.find_one(
        {"id": payload.recommendation_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    fb_doc = {
        "id": f"fb_{uuid.uuid4().hex[:12]}", "user_id": user["user_id"],
        "recommendation_id": payload.recommendation_id, "followed": payload.followed,
        "helped": payload.helped, "reason": payload.reason, "created_at": _iso(_now()),
    }
    await db.feedback.insert_one(dict(fb_doc))
    return {"feedback": _clean(fb_doc)}


@router.post("/mood")
async def log_mood(payload: MoodLogInput, user: dict = Depends(require_user)) -> dict:
    doc = {"id": f"mood_{uuid.uuid4().hex[:10]}", "user_id": user["user_id"],
           "value": payload.value, "note": payload.note, "created_at": _iso(_now())}
    await db.mood_logs.insert_one(dict(doc))
    await maybe_award_badges(user["user_id"])
    return {"mood": _clean(doc)}


@router.get("/history")
async def get_history(user: dict = Depends(require_user), days: int = 14) -> dict:
    since = _now() - timedelta(days=days)
    since_iso = _iso(since)
    checkins = await db.checkins.find(
        {"user_id": user["user_id"], "created_at": {"$gte": since_iso}}, {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    moods = await db.mood_logs.find(
        {"user_id": user["user_id"], "created_at": {"$gte": since_iso}}, {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    fbs = await db.feedback.find(
        {"user_id": user["user_id"], "created_at": {"$gte": since_iso}}, {"_id": 0}
    ).to_list(500)
    followed = sum(1 for f in fbs if f.get("followed"))
    adherence = round((followed / len(fbs)) * 100) if fbs else 0
    return {"checkins": checkins, "mood_logs": moods, "adherence_pct": adherence,
            "total_feedback": len(fbs)}


# ---- Legacy exam/oncall (kept for backward compat) ------------------------
@router.post("/mode/exam")
async def set_exam_mode(payload: ExamModeInput, user: dict = Depends(require_user)) -> dict:
    doc = {"id": f"emx_{uuid.uuid4().hex[:10]}", "user_id": user["user_id"],
           "exam_name": payload.exam_name, "exam_date": payload.exam_date,
           "created_at": _iso(_now())}
    await db.exam_modes.insert_one(dict(doc))
    await db.user_profiles.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"mode": "prova"}, "$setOnInsert": {"user_id": user["user_id"]}},
        upsert=True,
    )
    return {"exam_mode": _clean(doc)}


@router.get("/mode/exam")
async def get_exam_mode(user: dict = Depends(require_user)) -> dict:
    doc = await db.exam_modes.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}, sort=[("created_at", -1)]
    )
    return {"exam_mode": doc}


@router.delete("/mode/exam")
async def clear_exam_mode(user: dict = Depends(require_user)) -> dict:
    await db.exam_modes.delete_many({"user_id": user["user_id"]})
    return {"ok": True}


@router.post("/mode/oncall")
async def set_oncall(payload: OnCallInput, user: dict = Depends(require_user)) -> dict:
    await db.oncall_states.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"user_id": user["user_id"], "active": payload.active,
                  "updated_at": _iso(_now())}},
        upsert=True,
    )
    if payload.active:
        await db.user_profiles.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"mode": "plantao"}, "$setOnInsert": {"user_id": user["user_id"]}},
            upsert=True,
        )
    return {"on_call": payload.active}


@router.get("/mode/oncall")
async def get_oncall(user: dict = Depends(require_user)) -> dict:
    doc = await db.oncall_states.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return {"on_call": bool(doc and doc.get("active"))}


# ---- Mindfulness ----------------------------------------------------------
MINDFULNESS_LIBRARY = [
    {"slug": "breath-4-7-8", "title": "Respiração 4-7-8", "duration_seconds": 180,
     "description": "Três minutos de respiração guiada para desacelerar antes de estudar ou dormir.",
     "instructions": ["Inspire pelo nariz contando até 4", "Segure o ar contando até 7",
                      "Expire pela boca contando até 8", "Repita por 8 ciclos"]},
    {"slug": "body-scan-2min", "title": "Escaneamento corporal (2 min)", "duration_seconds": 120,
     "description": "Percorra o corpo dos pés à cabeça notando tensões — ideal entre plantões.",
     "instructions": ["Sente-se confortavelmente", "Feche os olhos e respire naturalmente",
                      "Do pé direito à cabeça, note cada região por 10s",
                      "Solte a tensão a cada expiração"]},
    {"slug": "grounding-5-4-3-2-1", "title": "Ancoragem 5-4-3-2-1", "duration_seconds": 240,
     "description": "Reduza ansiedade pré-prova reconectando com os sentidos.",
     "instructions": ["5 coisas que você vê", "4 coisas que você toca", "3 sons que você ouve",
                      "2 aromas que você percebe", "1 sabor que você nota"]},
]


@router.get("/mindfulness/sessions")
async def mindfulness_sessions(user: dict = Depends(require_user)) -> dict:
    return {"sessions": MINDFULNESS_LIBRARY}


@router.post("/mindfulness/log")
async def log_mindfulness(payload: MindfulnessLogInput,
                          user: dict = Depends(require_user)) -> dict:
    doc = {"id": f"mfl_{uuid.uuid4().hex[:10]}", "user_id": user["user_id"],
           "session_slug": payload.session_slug,
           "duration_seconds": payload.duration_seconds,
           "created_at": _iso(_now())}
    await db.mindfulness_logs.insert_one(dict(doc))
    await maybe_award_badges(user["user_id"])
    return {"log": _clean(doc)}
