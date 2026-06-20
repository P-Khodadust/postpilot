"""Menu, help, settings, and shared navigation."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.bot.keyboards import back_to_menu, main_menu
from postpilot.bot.i18n import t
from postpilot.models import ConnectedXAccount
from postpilot.tenancy.context import TenantContext

router = Router()


async def _conn_suffix(session: AsyncSession, ctx: TenantContext) -> str:
    acct = (
        await session.execute(
            select(ConnectedXAccount).where(
                ConnectedXAccount.account_id == ctx.account_id,
                ConnectedXAccount.status == "connected",
            )
        )
    ).scalars().first()
    return f" - @{acct.x_handle} ✅" if acct else t("not_connected")


@router.message(Command("menu"))
async def cmd_menu(message: Message, session: AsyncSession, ctx: TenantContext):
    await message.answer(t("menu", conn=await _conn_suffix(session, ctx)), reply_markup=main_menu())


@router.callback_query(F.data == "nav:menu")
async def cb_menu(cb: CallbackQuery, session: AsyncSession, ctx: TenantContext):
    await cb.message.edit_text(
        t("menu", conn=await _conn_suffix(session, ctx)), reply_markup=main_menu()
    )
    await cb.answer()


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(t("help"), reply_markup=back_to_menu())


@router.callback_query(F.data == "help:home")
async def cb_help(cb: CallbackQuery):
    await cb.message.edit_text(t("help"), reply_markup=back_to_menu())
    await cb.answer()


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    await message.answer(
        "⚙️ Settings\n\nTimezone, language, notifications and X connection are managed here. "
        "Use /connect to reconnect X.",
        reply_markup=back_to_menu(),
    )


@router.callback_query(F.data == "set:home")
async def cb_settings(cb: CallbackQuery):
    await cb.message.edit_text(
        "⚙️ Settings\n\n• Timezone\n• Language\n• Notifications\n• X connection (/connect)",
        reply_markup=back_to_menu(),
    )
    await cb.answer()
