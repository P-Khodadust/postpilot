"""Billing: show plan, present upgrade options, kick off checkout."""

from __future__ import annotations

import uuid

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.bot.keyboards import back_to_menu
from postpilot.billing.telegram_provider import get_provider
from postpilot.entitlements.limits import PLANS_BY_CODE
from postpilot.entitlements.service import get_entitlements
from postpilot.tenancy.context import TenantContext

router = Router()


@router.message(Command("billing"))
async def cmd_billing(message: Message, session: AsyncSession, ctx: TenantContext):
    await _home(message, session, ctx)


@router.callback_query(F.data == "bill:home")
async def cb_billing(cb: CallbackQuery, session: AsyncSession, ctx: TenantContext):
    await _home(cb, session, ctx)
    await cb.answer()


async def _home(event, session: AsyncSession, ctx: TenantContext):
    ent = await get_entitlements(session, ctx.account_id)
    plan = PLANS_BY_CODE.get(ent.plan_code)
    text = f"💳 Your plan: {plan.display_name if plan else ent.plan_code}"
    b = InlineKeyboardBuilder()
    b.button(text="⬆️ Upgrade", callback_data="bill:upgrade")
    b.button(text="🏠 Menu", callback_data="nav:menu")
    b.adjust(2)
    await _send(event, text, b.as_markup())


@router.callback_query(F.data == "bill:upgrade")
async def cb_upgrade(cb: CallbackQuery):
    b = InlineKeyboardBuilder()
    for code, plan in PLANS_BY_CODE.items():
        if code == "free":
            continue
        b.button(text=f"{plan.display_name} - ${plan.price_cents // 100}/mo",
                 callback_data=f"bill:choose:{code}")
    b.button(text="◀️ Back", callback_data="bill:home")
    b.adjust(1)
    await cb.message.edit_text("Choose a plan:", reply_markup=b.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("bill:choose:"))
async def cb_choose(cb: CallbackQuery, session: AsyncSession, ctx: TenantContext):
    plan_code = cb.data.split(":")[2]
    plan = PLANS_BY_CODE[plan_code]
    provider = get_provider("telegram")  # in-bot purchases default to Telegram payments
    result = await provider.create_checkout(
        ctx.account_id, plan_code, trial_days=plan.trial_days, idempotency_key=uuid.uuid4().hex
    )
    if result.telegram_invoice:
        await cb.message.answer(
            f"To subscribe to {plan.display_name}, complete payment in the next message.",
        )
        # bot.send_invoice(**result.telegram_invoice) would follow here in production.
    elif result.redirect_url:
        b = InlineKeyboardBuilder()
        b.button(text="💳 Pay securely", url=result.redirect_url)
        await cb.message.edit_text(f"Complete your {plan.display_name} subscription:",
                                   reply_markup=b.as_markup())
    await cb.answer()


async def _send(event, text, markup):
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=markup)
    else:
        await event.answer(text, reply_markup=markup)
