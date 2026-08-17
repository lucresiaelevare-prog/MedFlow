"""Comunidade — feed de vivências entre estudantes.

- Posts com texto + categoria (rotina, saúde-mental, estudo, ócio, plantão, dependência, geral).
- Comentários e likes (curtir/descurtir).
- Não substitui assistente acadêmico; foco em troca de experiências.

Regras:
- Nome exibido = user.name ou 'Estudante anônimo' se profile.anonymous_community = True.
- Sem edição — para simplicidade e integridade do feed.
- Autor pode deletar seu próprio post/comentário; admin pode deletar qualquer um.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core import _clean, _iso, _now, db, require_user
from routes.profile import get_profile_doc

router = APIRouter(prefix="/api/community", tags=["community"])


VALID_CATEGORIES = {"geral", "rotina", "saude-mental", "estudo", "ocio", "plantao", "dependencia"}


class PostInput(BaseModel):
    body: str
    category: Optional[str] = "geral"


class CommentInput(BaseModel):
    body: str


async def _author_meta(user: dict) -> dict:
    profile = await get_profile_doc(user["user_id"])
    anonymous = bool(profile.get("anonymous_community"))
    return {
        "user_id": user["user_id"],
        "name": "Estudante anônimo" if anonymous else (user.get("name") or "Estudante"),
        "picture": None if anonymous else user.get("picture"),
    }


@router.post("/posts")
async def create_post(payload: PostInput, user: dict = Depends(require_user)) -> dict:
    body = (payload.body or "").strip()
    if len(body) < 3:
        raise HTTPException(status_code=400, detail="Escreva pelo menos 3 caracteres")
    if len(body) > 2000:
        raise HTTPException(status_code=400, detail="Post muito longo (max 2000)")
    category = payload.category if payload.category in VALID_CATEGORIES else "geral"
    author = await _author_meta(user)
    doc = {
        "id": f"pst_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"],
        "author": author,
        "body": body,
        "category": category,
        "likes": [],
        "comments_count": 0,
        "created_at": _iso(_now()),
    }
    await db.community_posts.insert_one(dict(doc))
    return {"post": _clean(doc)}


@router.get("/posts")
async def list_posts(
    user: dict = Depends(require_user),
    category: Optional[str] = Query(default=None),
    limit: int = Query(default=30, le=100),
) -> dict:
    q: dict = {}
    if category and category in VALID_CATEGORIES:
        q["category"] = category
    items = await db.community_posts.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    my_id = user["user_id"]
    for it in items:
        likes = it.get("likes") or []
        it["like_count"] = len(likes)
        it["liked_by_me"] = my_id in likes
        it["is_mine"] = it.get("user_id") == my_id
        it.pop("likes", None)
    return {"posts": items}


@router.delete("/posts/{post_id}")
async def delete_post(post_id: str, user: dict = Depends(require_user)) -> dict:
    doc = await db.community_posts.find_one({"id": post_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Post não encontrado")
    if doc["user_id"] != user["user_id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão")
    await db.community_posts.delete_one({"id": post_id})
    await db.community_comments.delete_many({"post_id": post_id})
    return {"ok": True}


@router.post("/posts/{post_id}/like")
async def toggle_like(post_id: str, user: dict = Depends(require_user)) -> dict:
    doc = await db.community_posts.find_one({"id": post_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Post não encontrado")
    uid = user["user_id"]
    already_liked = uid in (doc.get("likes") or [])
    if already_liked:
        await db.community_posts.update_one({"id": post_id}, {"$pull": {"likes": uid}})
        liked = False
    else:
        await db.community_posts.update_one({"id": post_id}, {"$addToSet": {"likes": uid}})
        liked = True
    updated = await db.community_posts.find_one({"id": post_id}, {"_id": 0, "likes": 1})
    like_count = len((updated or {}).get("likes") or [])
    return {"liked": liked, "like_count": like_count}


@router.post("/posts/{post_id}/comments")
async def add_comment(post_id: str, payload: CommentInput, user: dict = Depends(require_user)) -> dict:
    body = (payload.body or "").strip()
    if len(body) < 1 or len(body) > 500:
        raise HTTPException(status_code=400, detail="Comentário deve ter 1-500 caracteres")
    post = await db.community_posts.find_one({"id": post_id}, {"_id": 0})
    if not post:
        raise HTTPException(status_code=404, detail="Post não encontrado")
    author = await _author_meta(user)
    doc = {
        "id": f"cmt_{uuid.uuid4().hex[:10]}",
        "post_id": post_id,
        "user_id": user["user_id"],
        "author": author,
        "body": body,
        "created_at": _iso(_now()),
    }
    await db.community_comments.insert_one(dict(doc))
    await db.community_posts.update_one(
        {"id": post_id}, {"$inc": {"comments_count": 1}}
    )
    return {"comment": _clean(doc)}


@router.get("/posts/{post_id}/comments")
async def list_comments(post_id: str, _: dict = Depends(require_user)) -> dict:
    items = await db.community_comments.find(
        {"post_id": post_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    return {"comments": items}


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, user: dict = Depends(require_user)) -> dict:
    doc = await db.community_comments.find_one({"id": comment_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Comentário não encontrado")
    if doc["user_id"] != user["user_id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão")
    await db.community_comments.delete_one({"id": comment_id})
    await db.community_posts.update_one(
        {"id": doc["post_id"]}, {"$inc": {"comments_count": -1}}
    )
    return {"ok": True}
