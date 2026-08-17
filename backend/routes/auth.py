"""Auth routes: Google session exchange + /auth/me + logout + admin email/password.

REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
"""
from __future__ import annotations

import os
import uuid
from datetime import timedelta
from typing import Optional

import bcrypt
import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from core import (
    EMERGENT_AUTH_SESSION_URL,
    SESSION_TTL_DAYS,
    _get_user_from_token,
    _iso,
    _now,
    db,
    logger,
    require_user,
)

router = APIRouter(prefix="/api", tags=["auth"])


# ─── password helpers (see /app/auth_testing.md) ───────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:  # noqa: BLE001
        return False


async def _issue_session_cookie(user_id: str, response: Response, prefix: str = "sess", request: Optional[Request] = None) -> str:
    """Cria user_sessions doc + set-cookie httpOnly. Retorna o token.

    O cookie só recebe a flag ``secure`` quando a requisição já trafega
    sobre HTTPS — por trás de proxy reverso, o esquema real é informado
    pelo header ``X-Forwarded-Proto`` (FastAPI ``root_path``/proxy headers
    padrão). Sem isso, clientes httpOnly + secure em ambiente http
    (testes, proxy local, staging sem TLS) nunca enviam o cookie e o
    login aparentemente "funciona" mas a sessão não autentica.
    """
    from fastapi import Request as _Request
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "access_blocked": 1})
    if user is None or user.get("access_blocked"):
        raise HTTPException(status_code=403, detail="Acesso bloqueado")
    session_token = f"{prefix}_{uuid.uuid4().hex}"
    expires_at = _now() + timedelta(days=SESSION_TTL_DAYS)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": _iso(expires_at),
        "created_at": _iso(_now()),
    })
    secure = False
    if request is not None:
        proto = str(request.headers.get("x-forwarded-proto", "")).split(",")[0].strip().lower()
        secure = proto == "https" or request.url.scheme == "https"
    response.set_cookie(
        key="session_token", value=session_token, httponly=True, secure=secure,
        samesite="lax", max_age=SESSION_TTL_DAYS * 24 * 60 * 60, path="/",
    )
    return session_token


# ─── Google OAuth (Emergent-managed) ───────────────────────────────
@router.post("/auth/session")
async def auth_session(request: Request, response: Response) -> dict:
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.get(EMERGENT_AUTH_SESSION_URL, headers={"X-Session-ID": session_id})
    if r.status_code != 200:
        logger.warning("Emergent auth exchange failed: %s %s", r.status_code, r.text)
        raise HTTPException(status_code=401, detail="Failed to validate session")
    data = r.json()

    email = data["email"]
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        if existing.get("access_blocked"):
            raise HTTPException(status_code=403, detail="Acesso bloqueado")
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": data.get("name"), "picture": data.get("picture")}},
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one(
            {
                "user_id": user_id,
                "email": email,
                "name": data.get("name"),
                "picture": data.get("picture"),
                "subscription_plan": "free",
                "created_at": _iso(_now()),
            }
        )

    session_token = data["session_token"]
    expires_at = _now() + timedelta(days=SESSION_TTL_DAYS)
    await db.user_sessions.update_one(
        {"session_token": session_token},
        {"$set": {"user_id": user_id, "session_token": session_token,
                  "expires_at": _iso(expires_at), "created_at": _iso(_now())}},
        upsert=True,
    )
    response.set_cookie(
        key="session_token", value=session_token, httponly=True, secure=True,
        samesite="none", max_age=SESSION_TTL_DAYS * 24 * 60 * 60, path="/",
    )
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"user": user}


@router.get("/auth/me")
async def auth_me(user: dict = Depends(require_user)) -> dict:
    return {"user": user}


@router.get("/auth/status")
async def auth_status(session_token: Optional[str] = Cookie(default=None)) -> dict:
    """Retorna o estado da sessão sem gerar um erro para visitantes anônimos."""
    user = await _get_user_from_token(session_token) if session_token else None
    return {"authenticated": bool(user), "user": user}


@router.post("/auth/logout")
async def auth_logout(response: Response, session_token: Optional[str] = Cookie(default=None)) -> dict:
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie("session_token", path="/", samesite="none", secure=True)
    return {"ok": True}


# ─── Dev-only login (bypass Google) ────────────────────────────────
@router.post("/auth/dev-login")
async def auth_dev_login(request: Request, response: Response) -> dict:
    if os.environ.get("ENABLE_DEV_LOGIN", "false").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="Not found")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    email = (body.get("email") or "dev@medflow.local").strip().lower()
    name = body.get("name") or "Dev Student"
    # HARDENING: o cliente NUNCA define is_admin. Autoridade admin vem
    # exclusivamente do servidor (seed_admin / admin-login). Qualquer
    # `is_admin` enviado no payload é ignorado de propósito.

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        if existing.get("access_blocked"):
            raise HTTPException(status_code=403, detail="Acesso bloqueado")
        user_id = existing["user_id"]
        await db.users.update_one({"user_id": user_id}, {"$set": {"name": name}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id, "email": email, "name": name,
            "picture": None, "is_admin": False,
            "created_at": _iso(_now()),
        })

    session_token = await _issue_session_cookie(user_id, response, prefix="dev", request=request)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"user": user, "session_token": session_token}


# ─── Admin email + password login ──────────────────────────────────
class AdminLoginIn(BaseModel):
    email: str
    password: str


@router.post("/auth/admin-login")
async def auth_admin_login(request: Request, body: AdminLoginIn, response: Response) -> dict:
    """Login exclusivo do painel administrativo (email + senha, bcrypt).

    Mantém o mesmo mecanismo de sessão do restante do app (`user_sessions`
    + cookie httpOnly `session_token`), então `require_user`/`require_admin`
    funcionam sem alteração.
    """
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    if user.get("access_blocked"):
        raise HTTPException(status_code=403, detail="Acesso bloqueado")
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Usuário sem permissão de admin")

    session_token = await _issue_session_cookie(user["user_id"], response, prefix="adm", request=request)
    user.pop("password_hash", None)
    return {"user": user, "session_token": session_token}


async def _seed_admin_account(
    email: str,
    password: str,
    name: str,
    is_technical_admin: bool,
) -> None:
    """Cria ou confirma uma conta administrativa sem promover estudantes."""
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing is None:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": None,
            "is_admin": True,
            "is_technical_admin": is_technical_admin,
            "password_hash": hash_password(password),
            "created_at": _iso(_now()),
        })
        logger.info("seed_admin: admin criado (%s)", email)
        return

    updates: dict = {}
    if not existing.get("is_admin"):
        updates["is_admin"] = True
    if bool(existing.get("is_technical_admin")) != is_technical_admin:
        updates["is_technical_admin"] = is_technical_admin
    if not existing.get("name"):
        updates["name"] = name
    if not existing.get("password_hash") or not verify_password(password, existing["password_hash"]):
        updates["password_hash"] = hash_password(password)
    if updates:
        await db.users.update_one({"user_id": existing["user_id"]}, {"$set": updates})
        logger.info("seed_admin: admin atualizado (%s) fields=%s", email, list(updates.keys()))


# ─── Idempotent admin seeding ──────────────────────────────────────
async def seed_admin() -> None:
    """Garante exclusivamente as contas administrativas declaradas no ambiente."""
    accounts = [
        (
            os.environ["ADMIN_EMAIL"].strip().lower(),
            os.environ["ADMIN_PASSWORD"],
            "MedFlow Admin",
            False,
        ),
        (
            os.environ["ADMIN_EDER_EMAIL"].strip().lower(),
            os.environ["ADMIN_EDER_PASSWORD"],
            "Eder",
            True,
        ),
        (
            os.environ["ADMIN_CARINE_EMAIL"].strip().lower(),
            os.environ["ADMIN_CARINE_PASSWORD"],
            "Carine",
            False,
        ),
    ]
    for email, password, name, is_technical_admin in accounts:
        if not email or not password:
            raise RuntimeError("Conta administrativa sem e-mail ou senha configurada")
        await _seed_admin_account(email, password, name, is_technical_admin)
