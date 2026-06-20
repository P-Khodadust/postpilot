"""Receive Telegram updates (webhook mode) and dispatch them to the shared aiogram Dispatcher."""

from __future__ import annotations

from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request

from postpilot.core.config import get_settings

router = APIRouter()


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    settings = get_settings()
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="bad secret token")
    data = await request.json()
    update = Update.model_validate(data, context={"bot": request.app.state.bot})
    await request.app.state.dp.feed_update(request.app.state.bot, update)
    return {"ok": True}
