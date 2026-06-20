"""Liveness/readiness: checks DB + Redis connectivity."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from postpilot.core.db import session_scope
from postpilot.core.redis import get_redis

router = APIRouter()


@router.get("/healthz")
async def healthz():
    checks = {"db": False, "redis": False}
    try:
        async with session_scope() as s:
            await s.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        await get_redis().ping()
        checks["redis"] = True
    except Exception:  # noqa: BLE001
        pass
    ok = all(checks.values())
    return JSONResponse(status_code=200 if ok else 503, content={"ok": ok, **checks})
