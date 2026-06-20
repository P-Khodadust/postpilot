"""X connection: start the OAuth PKCE flow (callback completion lives in web/routes/oauth_callback)."""

from __future__ import annotations

import datetime as dt

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.bot.keyboards import back_to_menu, connect_button
from postpilot.bot.i18n import t
from postpilot.core.config import get_settings
from postpilot.core.security import encrypt
from postpilot.entitlements.service import assert_can_connect_x
from postpilot.models import ConnectedXAccount, OAuthState
from postpilot.tenancy.context import TenantContext
from postpilot.x_api import oauth

router = Router()


async def begin_connect(event: Message | CallbackQuery, session: AsyncSession, ctx: TenantContext):
    from postpilot.core.errors import QuotaError

    try:
        await assert_can_connect_x(session, ctx.account_id)
    except QuotaError as e:
        msg = "You've reached your plan's connected-account limit. Upgrade to add more."
        await _reply(event, msg, reply_markup=back_to_menu())
        return

    settings = get_settings()
    flow = oauth.start_authorization()
    session.add(
        OAuthState(
            state=flow.state,
            account_id=ctx.account_id,
            membership_id=ctx.membership_id,
            code_verifier_enc=encrypt(flow.code_verifier),
            redirect_uri=settings.x_redirect_uri,
            scopes=settings.x_scopes,
            expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10),
        )
    )
    await _reply(event, t("connect_x"), reply_markup=connect_button(flow.authorize_url))


@router.message(Command("connect"))
async def cmd_connect(message: Message, session: AsyncSession, ctx: TenantContext):
    existing = (
        await session.execute(
            select(ConnectedXAccount).where(
                ConnectedXAccount.account_id == ctx.account_id,
                ConnectedXAccount.status == "connected",
            )
        )
    ).scalars().first()
    if existing:
        await message.answer(
            f"🔗 Connected as @{existing.x_handle}. Use the menu to manage posts.",
            reply_markup=back_to_menu(),
        )
        return
    await begin_connect(message, session, ctx)


@router.callback_query(F.data == "conn:start")
async def cb_connect(cb: CallbackQuery, session: AsyncSession, ctx: TenantContext):
    await begin_connect(cb, session, ctx)
    await cb.answer()


async def _reply(event: Message | CallbackQuery, text: str, **kw):
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, **kw)
        await event.answer()
    else:
        await event.answer(text, **kw)
