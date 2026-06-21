"""FastAPI app: OAuth callback, Telegram & billing webhooks, admin, health."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from postpilot.core.config import get_settings
from postpilot.core.errors import AppError
from postpilot.core.logging import configure_logging, correlation_id, get_logger

log = get_logger("web")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.require_for_production()
    # Build a shared bot + dispatcher for webhook dispatch + proactive pushes.
    # Tolerate a missing/placeholder token (staging/infra-only deploys): the API,
    # OAuth callback, and admin still run; only Telegram dispatch is disabled.
    app.state.bot = None
    app.state.dp = None
    token = settings.telegram_bot_token
    if token and ":" in token and "REPLACE" not in token.upper():
        from postpilot.bot.main import build_bot, build_dispatcher

        app.state.bot = build_bot()
        app.state.dp = build_dispatcher()
    else:
        log.warning("web.bot_disabled", reason="no valid TELEGRAM_BOT_TOKEN")
    log.info("web.startup", env=settings.environment, bot_enabled=app.state.bot is not None)
    yield
    if app.state.bot is not None:
        await app.state.bot.session.close()


def create_app() -> FastAPI:
    app = FastAPI(title="PostPilot", lifespan=lifespan)

    from postpilot.web.routes import billing_webhooks, health, oauth_callback, telegram_webhook

    app.include_router(health.router)
    app.include_router(oauth_callback.router)
    app.include_router(telegram_webhook.router)
    app.include_router(billing_webhooks.router)

    try:
        from postpilot.web.admin import views as admin_views

        app.include_router(admin_views.router, prefix="/admin")
    except Exception as e:  # noqa: BLE001 - admin optional at boot
        log.warning("admin.not_mounted", error=str(e))

    @app.middleware("http")
    async def _correlation(request: Request, call_next):
        correlation_id.set(request.headers.get("x-correlation-id") or uuid.uuid4().hex)
        return await call_next(request)

    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError):
        log.warning("app_error", code=exc.code, message=exc.message)
        return JSONResponse(status_code=exc.http_status, content={"error": exc.code})

    return app


app = create_app()
