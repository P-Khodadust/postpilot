"""Admin pages: login, overview KPIs, accounts list. FastAPI + Jinja2 + HTMX-ready."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from postpilot.core.db import session_scope
from postpilot.models import Account, PostHistory, Subscription
from postpilot.web.admin.auth import authenticate, current_admin, issue_cookie

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    admin = await authenticate(email, password)
    if not admin:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid credentials"}, status_code=401
        )
    resp = RedirectResponse("/admin/", status_code=302)
    issue_cookie(resp, admin)
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse("/admin/login", status_code=302)
    resp.delete_cookie("pp_admin")
    return resp


@router.get("/", response_class=HTMLResponse)
async def overview(request: Request):
    admin = await current_admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    async with session_scope() as s:
        accounts = (await s.execute(select(func.count()).select_from(Account))).scalar_one()
        active_subs = (
            await s.execute(
                select(func.count()).select_from(Subscription).where(Subscription.status == "active")
            )
        ).scalar_one()
        posts_sent = (
            await s.execute(
                select(func.count()).select_from(PostHistory).where(PostHistory.status == "succeeded")
            )
        ).scalar_one()
        posts_failed = (
            await s.execute(
                select(func.count()).select_from(PostHistory).where(PostHistory.status == "failed")
            )
        ).scalar_one()
    kpis = {
        "Accounts": accounts,
        "Active subs": active_subs,
        "Posts sent": posts_sent,
        "Posts failed": posts_failed,
    }
    return templates.TemplateResponse("overview.html", {"request": request, "kpis": kpis})


@router.get("/accounts", response_class=HTMLResponse)
async def accounts_list(request: Request):
    admin = await current_admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    async with session_scope() as s:
        rows = (await s.execute(select(Account).order_by(Account.created_at.desc()).limit(100))).scalars().all()
    return templates.TemplateResponse("accounts.html", {"request": request, "accounts": rows})
