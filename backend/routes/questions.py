"""Plantão de dúvidas do Beta, com consentimento explícito para publicação anônima."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import _iso, _now, db, require_user
from routes.admin import require_admin

router = APIRouter(prefix="/api", tags=["questions"])


class QuestionCreate(BaseModel):
    message: str = Field(min_length=4, max_length=2000)
    category: str = Field(default="geral", max_length=80)
    allow_anonymous_publication: bool = False


class QuestionAdminUpdate(BaseModel):
    reply: str | None = Field(default=None, max_length=2000)
    resolved: bool | None = None
    published_anonymously: bool | None = None


@router.post("/questions")
async def create_question(payload: QuestionCreate, user: dict = Depends(require_user)) -> dict:
    document = {
        "id": f"qst_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "message": payload.message.strip(),
        "category": payload.category.strip() or "geral",
        "allow_anonymous_publication": payload.allow_anonymous_publication,
        "published_anonymously": False,
        "resolved": False,
        "admin_reply": None,
        "created_at": _iso(_now()),
    }
    response_question = {
        key: value for key, value in document.items() if key not in {"user_id", "_id"}
    }
    await db.questions.insert_one(document)
    return {"question": response_question}


@router.get("/admin/business/questions")
async def list_questions(_: dict = Depends(require_admin)) -> dict:
    questions = await db.questions.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"questions": questions, "total": len(questions)}


@router.patch("/admin/business/questions/{question_id}")
async def update_question(
    question_id: str,
    payload: QuestionAdminUpdate,
    _: dict = Depends(require_admin),
) -> dict:
    existing = await db.questions.find_one({"id": question_id}, {"_id": 0})
    if existing is None:
        raise HTTPException(status_code=404, detail="Dúvida não encontrada")
    updates = payload.model_dump(exclude_none=True)
    if updates.get("published_anonymously") and not existing.get("allow_anonymous_publication"):
        raise HTTPException(status_code=400, detail="Aluno não autorizou publicação anônima")
    if not updates:
        raise HTTPException(status_code=400, detail="Nenhuma alteração informada")
    if "reply" in updates:
        updates["admin_reply"] = updates.pop("reply").strip()
    updates["updated_at"] = _iso(_now())
    await db.questions.update_one({"id": question_id}, {"$set": updates})
    question = await db.questions.find_one({"id": question_id}, {"_id": 0})
    return {"question": question}


@router.get("/questions/public")
async def public_questions() -> dict:
    questions = await db.questions.find(
        {"published_anonymously": True},
        {"_id": 0, "id": 1, "message": 1, "category": 1, "admin_reply": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(100)
    return {"questions": questions}