"""Profile + Mode routes. Exposes `get_profile_doc` for other modules."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core import _clean, _iso, _now, db, require_user
from models import ModeInput, ProfileInput, VALID_MODES

router = APIRouter(prefix="/api", tags=["profile"])


async def get_profile_doc(user_id: str) -> dict:
    """Fetch profile, seeding defaults on first access. Shared with mission/context builders."""
    doc = await db.user_profiles.find_one({"user_id": user_id}, {"_id": 0})
    if not doc:
        doc = {
            "user_id": user_id,
            "study_tool": "anki",
            "mode": "rotina",
            "updated_at": _iso(_now()),
        }
        await db.user_profiles.insert_one(dict(doc))
    return doc


@router.get("/profile")
async def get_profile(user: dict = Depends(require_user)) -> dict:
    return {"profile": _clean(await get_profile_doc(user["user_id"]))}


@router.patch("/profile")
async def patch_profile(payload: ProfileInput, user: dict = Depends(require_user)) -> dict:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    updates["updated_at"] = _iso(_now())
    await db.user_profiles.update_one(
        {"user_id": user["user_id"]},
        {"$set": updates, "$setOnInsert": {"user_id": user["user_id"]}},
        upsert=True,
    )
    return {"profile": _clean(await get_profile_doc(user["user_id"]))}


@router.post("/mode")
async def set_mode(payload: ModeInput, user: dict = Depends(require_user)) -> dict:
    if payload.mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail="mode inválido")
    await db.user_profiles.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"mode": payload.mode, "updated_at": _iso(_now())},
         "$setOnInsert": {"user_id": user["user_id"]}},
        upsert=True,
    )
    return {"mode": payload.mode}


@router.get("/mode")
async def get_mode(user: dict = Depends(require_user)) -> dict:
    profile = await get_profile_doc(user["user_id"])
    return {"mode": profile.get("mode", "rotina")}
