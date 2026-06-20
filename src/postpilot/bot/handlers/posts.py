"""Compose a one-off post + list upcoming/past posts."""

from __future__ import annotations

import datetime as dt
import uuid

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.bot.keyboards import back_to_menu, confirm
from postpilot.bot.states import Compose
from postpilot.core.errors import QuotaError
from postpilot.entitlements.limits import LimitKey
from postpilot.entitlements.service import check_quota
from postpilot.metering.service import increment_quota
from postpilot.models import ConnectedXAccount, PostHistory, PostQueue
from postpilot.scheduler.materializer import enqueue_adhoc
from postpilot.tenancy.context import TenantContext

router = Router()


@router.message(Command("post"))
async def cmd_post(message: Message, state: FSMContext):
    await state.set_state(Compose.text)
    await message.answer("✍️ What should the post say? Send me the text.", reply_markup=back_to_menu())


@router.callback_query(F.data == "post:new")
async def cb_post(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Compose.text)
    await cb.message.edit_text("✍️ What should the post say? Send me the text.", reply_markup=back_to_menu())
    await cb.answer()


@router.message(Compose.text)
async def compose_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text or "")
    await state.set_state(Compose.confirm)
    await message.answer(
        f"Post this now?\n\n\"{(message.text or '')[:250]}\"", reply_markup=confirm("post:now")
    )


@router.callback_query(Compose.confirm, F.data == "post:now:yes")
async def compose_now(cb: CallbackQuery, state: FSMContext, session: AsyncSession, ctx: TenantContext):
    data = await state.get_data()
    acct = (
        await session.execute(
            select(ConnectedXAccount).where(
                ConnectedXAccount.account_id == ctx.account_id,
                ConnectedXAccount.status == "connected",
            )
        )
    ).scalars().first()
    if not acct:
        await cb.message.edit_text("Connect X first: /connect", reply_markup=back_to_menu())
        await cb.answer()
        return
    try:
        await check_quota(session, ctx.account_id, LimitKey.SCHEDULED_POSTS_PER_MONTH)
    except QuotaError as e:
        from postpilot.bot.keyboards import upgrade_keyboard

        await cb.message.edit_text(e.user_message, reply_markup=upgrade_keyboard())
        await cb.answer()
        return

    await enqueue_adhoc(
        session, account_id=ctx.account_id, x_account_id=acct.id, body=data["text"],
        scheduled_for=dt.datetime.now(dt.timezone.utc), idempotency_key=uuid.uuid4().hex,
    )
    await increment_quota(session, account_id=ctx.account_id, limit_key=LimitKey.SCHEDULED_POSTS_PER_MONTH)
    await state.clear()
    await cb.message.edit_text("✅ Queued - it'll post within a minute.", reply_markup=back_to_menu())
    await cb.answer()


@router.message(Command("posts"))
async def cmd_posts(message: Message, session: AsyncSession, ctx: TenantContext):
    upcoming = (
        await session.execute(
            select(PostQueue)
            .where(PostQueue.account_id == ctx.account_id, PostQueue.status.in_(("pending", "failed")))
            .order_by(PostQueue.scheduled_for)
            .limit(5)
        )
    ).scalars().all()
    past = (
        await session.execute(
            select(PostHistory)
            .where(PostHistory.account_id == ctx.account_id)
            .order_by(PostHistory.created_at.desc())
            .limit(5)
        )
    ).scalars().all()
    lines = ["⏭ Upcoming:"]
    lines += [f"• {p.scheduled_for:%a %H:%M} - {p.body[:50]}" for p in upcoming] or ["(none)"]
    lines.append("\n🕘 Recent:")
    lines += [
        f"• {'✅' if p.status == 'succeeded' else '⚠️'} {p.body[:50]}" for p in past
    ] or ["(none)"]
    await message.answer("\n".join(lines), reply_markup=back_to_menu())
