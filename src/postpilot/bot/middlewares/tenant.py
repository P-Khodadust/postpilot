"""Inject a DB session + TenantContext into every handler. The tenant boundary.

`account_id` is derived from the authenticated Telegram user id, never from message content.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from postpilot.bot.services.identity import get_or_create_context
from postpilot.core.db import session_scope


class TenantMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        async with session_scope() as session:
            ctx = await get_or_create_context(
                session, tg_user_id=user.id, username=user.username
            )
            data["session"] = session
            data["ctx"] = ctx
            return await handler(event, data)
