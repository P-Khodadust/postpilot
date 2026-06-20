"""Onboarding wizard: /start -> value prop -> connect X -> (timezone/schedule handled elsewhere)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.bot.handlers.connect import begin_connect
from postpilot.bot.keyboards import back_to_menu, main_menu, onboarding_intro
from postpilot.bot.services.identity import is_onboarded
from postpilot.bot.states import Onboarding
from postpilot.bot.i18n import t
from postpilot.tenancy.context import TenantContext

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, ctx: TenantContext):
    if await is_onboarded(session, ctx.account_id):
        await message.answer("👋 Welcome back!", reply_markup=main_menu())
        return
    await state.set_state(Onboarding.intro)
    await message.answer(t("welcome"), reply_markup=onboarding_intro())


@router.callback_query(F.data == "ob:start")
async def ob_value_prop(cb: CallbackQuery, state: FSMContext):
    from postpilot.bot.keyboards import InlineKeyboardBuilder  # local to avoid cycle

    await state.set_state(Onboarding.awaiting_oauth)
    b = InlineKeyboardBuilder()
    b.button(text="🔗 Connect my X account", callback_data="ob:connect")
    await cb.message.edit_text(t("value_prop"), reply_markup=b.as_markup())
    await cb.answer()


@router.callback_query(F.data == "ob:connect")
async def ob_connect(cb: CallbackQuery, session: AsyncSession, ctx: TenantContext):
    await begin_connect(cb, session, ctx)


@router.callback_query(F.data == "ob:check")
async def ob_check(cb: CallbackQuery, session: AsyncSession, ctx: TenantContext):
    if await is_onboarded(session, ctx.account_id):
        await cb.message.edit_text(
            "✅ You're connected! Use the menu to set your open/close posts.",
            reply_markup=main_menu(),
        )
    else:
        await cb.answer("Not yet - finish in the browser, then tap again.", show_alert=True)
