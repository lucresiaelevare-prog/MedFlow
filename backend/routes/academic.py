"""Subjects + Exams (academic tracking) routes + import de grade curricular."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core import _clean, _iso, _now, db, require_user
from curriculum_data import (
    CURRICULUM,
    UNIVERSITY_LABELS,
    get_semester,
    is_critical,
    list_universities,
)
from models import ExamGradeInput, ExamInput, SubjectInput

router = APIRouter(prefix="/api", tags=["academic"])


# ─── Subjects ────────────────────────────────────────────────

@router.post("/subjects")
async def create_subject(payload: SubjectInput, user: dict = Depends(require_user)) -> dict:
    doc = {
        "id": f"subj_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"],
        "name": payload.name,
        "color": payload.color or "#6B8E76",
        "is_dependency": bool(payload.is_dependency),
        "is_critical": is_critical(payload.name),
        "source": "manual",
        "created_at": _iso(_now()),
    }
    await db.subjects.insert_one(dict(doc))
    return {"subject": _clean(doc)}


@router.get("/subjects")
async def list_subjects(user: dict = Depends(require_user)) -> dict:
    items = await db.subjects.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(200)
    return {"subjects": items}


class SubjectFlagsInput(BaseModel):
    is_critical: Optional[bool] = None
    is_dependency: Optional[bool] = None
    color: Optional[str] = None


@router.patch("/subjects/{subject_id}")
async def patch_subject(subject_id: str, payload: SubjectFlagsInput,
                        user: dict = Depends(require_user)) -> dict:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Nada para atualizar")
    updates["updated_at"] = _iso(_now())
    res = await db.subjects.update_one(
        {"id": subject_id, "user_id": user["user_id"]}, {"$set": updates}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada")
    subj = await db.subjects.find_one({"id": subject_id}, {"_id": 0})
    return {"subject": subj}


@router.delete("/subjects/{subject_id}")
async def delete_subject(subject_id: str, user: dict = Depends(require_user)) -> dict:
    await db.subjects.delete_one({"id": subject_id, "user_id": user["user_id"]})
    await db.exams.delete_many({"subject_id": subject_id, "user_id": user["user_id"]})
    return {"ok": True}


# ─── Curriculum templates ─────────────────────────────────────

@router.get("/academic/curriculum-templates")
async def curriculum_templates(_: dict = Depends(require_user)) -> dict:
    universities = list_universities()
    return {"universities": universities}


class ImportCurriculumInput(BaseModel):
    university: str  # "faminas-bh" | "fcmmg"
    semester: int
    replace: Optional[bool] = False  # se True, apaga disciplinas source=curriculum antes


@router.post("/academic/import-curriculum")
async def import_curriculum(payload: ImportCurriculumInput,
                            user: dict = Depends(require_user)) -> dict:
    uni = (payload.university or "").lower().strip()
    if uni not in CURRICULUM:
        raise HTTPException(status_code=400, detail="Universidade não suportada")
    subjects = get_semester(uni, payload.semester)
    if not subjects:
        raise HTTPException(status_code=404, detail="Período não encontrado para essa faculdade")

    if payload.replace:
        # Só remove os de origem curriculum, mantém os manuais
        await db.subjects.delete_many({
            "user_id": user["user_id"], "source": "curriculum",
        })

    # Evita duplicatas (por nome + source=curriculum)
    existing_names = {
        s["name"].strip().lower()
        for s in await db.subjects.find(
            {"user_id": user["user_id"], "source": "curriculum"},
            {"_id": 0, "name": 1},
        ).to_list(500)
    }

    now_iso = _iso(_now())
    to_insert = []
    for s in subjects:
        if s["name"].strip().lower() in existing_names:
            continue
        to_insert.append({
            "id": f"subj_{uuid.uuid4().hex[:10]}",
            "user_id": user["user_id"],
            "name": s["name"],
            "hours": s.get("hours"),
            "kind": s.get("kind", "teorica"),
            "color": "#DC6B4C" if s.get("is_critical") else "#6B8E76",
            "is_dependency": False,
            "is_critical": bool(s.get("is_critical")),
            "source": "curriculum",
            "curriculum_university": uni,
            "curriculum_semester": int(payload.semester),
            "created_at": now_iso,
        })
    if to_insert:
        await db.subjects.insert_many([dict(x) for x in to_insert])

    # Salva marcadores no perfil
    await db.user_profiles.update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "university": UNIVERSITY_LABELS.get(uni, uni),
            "university_slug": uni,
            "semester": int(payload.semester),
            "updated_at": now_iso,
        }, "$setOnInsert": {"user_id": user["user_id"]}},
        upsert=True,
    )
    return {
        "imported": len(to_insert),
        "skipped": len(subjects) - len(to_insert),
        "university": UNIVERSITY_LABELS.get(uni, uni),
        "semester": int(payload.semester),
    }


# ─── Exams ────────────────────────────────────────────────────

@router.post("/exams")
async def create_exam(payload: ExamInput, user: dict = Depends(require_user)) -> dict:
    subj = await db.subjects.find_one(
        {"id": payload.subject_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not subj:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada")
    doc = {
        "id": f"exam_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"],
        "subject_id": payload.subject_id,
        "subject_name": subj["name"],
        "subject_is_critical": bool(subj.get("is_critical")),
        "name": payload.name,
        "exam_date": payload.exam_date,
        "weight": payload.weight or 1.0,
        "grade": None,
        "weak_topics": None,
        "created_at": _iso(_now()),
    }
    await db.exams.insert_one(dict(doc))
    return {"exam": _clean(doc)}


@router.get("/exams")
async def list_exams(user: dict = Depends(require_user)) -> dict:
    items = await db.exams.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("exam_date", 1).to_list(500)
    return {"exams": items}


@router.patch("/exams/{exam_id}")
async def grade_exam(exam_id: str, payload: ExamGradeInput,
                     user: dict = Depends(require_user)) -> dict:
    result = await db.exams.update_one(
        {"id": exam_id, "user_id": user["user_id"]},
        {"$set": {"grade": payload.grade, "weak_topics": payload.weak_topics,
                  "graded_at": _iso(_now())}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Prova não encontrada")
    exam = await db.exams.find_one({"id": exam_id}, {"_id": 0})
    return {"exam": exam}


@router.delete("/exams/{exam_id}")
async def delete_exam(exam_id: str, user: dict = Depends(require_user)) -> dict:
    await db.exams.delete_one({"id": exam_id, "user_id": user["user_id"]})
    return {"ok": True}
