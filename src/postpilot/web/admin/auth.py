"""Admin auth: argon2 password check + signed session cookie (separate from end users)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from postpilot.core.config import get_settings
from postpilot.core.db import session_scope
from postpilot.core.security import sign, verify_signed
from postpilot.models import AdminUser

_ph = PasswordHasher()
COOKIE = "pp_admin"


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


async def authenticate(email: str, password: str) -> AdminUser | None:
    async with session_scope() as s:
        admin = (
            await s.execute(select(AdminUser).where(AdminUser.email == email))
        ).scalar_one_or_none()
        if not admin or not admin.is_active:
            return None
        try:
            _ph.verify(admin.password_hash, password)
        except VerifyMismatchError:
            return None
        return admin


def issue_cookie(resp: RedirectResponse, admin: AdminUser) -> None:
    token = sign(f"{admin.id}:{admin.role}", secret=get_settings().admin_session_secret)
    resp.set_cookie(COOKIE, token, httponly=True, samesite="strict",
                    secure=get_settings().is_production, max_age=8 * 3600)


async def current_admin(request: Request):
    """Dependency: returns (admin_id, role) or raises a redirect to /admin/login."""
    raw = request.cookies.get(COOKIE)
    value = verify_signed(raw, secret=get_settings().admin_session_secret) if raw else None
    if not value:
        return None
    admin_id, _, role = value.partition(":")[0], None, value.partition(":")[2]
    return {"id": admin_id, "role": role}
