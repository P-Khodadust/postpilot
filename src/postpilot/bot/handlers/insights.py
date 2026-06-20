"""AI insights: best times + weekly summary (quota-gated, code-computed stats)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.ai.client import AIClient
from postpilot.bot.keyboards import back_to_menu
from postpilot.core.errors import QuotaError
from postpilot.entitlements.limits import LimitKey
from postpilot.entitlements.service import check_quota
from postpilot.metering.service import increment_quota
from postpilot.models import PostHistory
from postpilot.tenancy.context import TenantContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()


def _home_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🕐 Best times", callback_data="ins:best")
    b.button(text="📅 This week", callback_data="ins:weekly")
    b.button(text="🏠 Menu", callback_data="nav:menu")
    b.adjust(2, 1)
    return b.as_markup()


@router.message(Command("insights"))
async def cmd_insights(message: Message):
    await message.answer("📊 Insights", reply_markup=_home_kb())


@router.callback_query(F.data == "ins:home")
async def cb_home(cb: CallbackQuery):
    await cb.message.edit_text("📊 Insights", reply_markup=_home_kb())
    await cb.answer()


async def _gate(session: AsyncSession, ctx: TenantContext, cb: CallbackQuery) -> bool:
    try:
        await check_quota(session, ctx.account_id, LimitKey.AI_INSIGHT_CALLS_PER_MONTH)
    except QuotaError as e:
        from postpilot.bot.keyboards import upgrade_keyboard

        await cb.message.edit_text(e.user_message, reply_markup=upgrade_keyboard())
        await cb.answer()
        return False
    return True


@router.callback_query(F.data == "ins:best")
async def cb_best(cb: CallbackQuery, session: AsyncSession, ctx: TenantContext):
    if not await _gate(session, ctx, cb):
        return
    await cb.message.edit_text("⏳ Crunching your numbers…")
    sent = (
        await session.execute(
            select(func.count()).select_from(PostHistory).where(
                PostHistory.account_id == ctx.account_id, PostHistory.status == "succeeded"
            )
        )
    ).scalar_one()
    data = {"posts_analyzed": sent, "note": "cold-start" if sent < 10 else "ok"}
    tips = await AIClient().best_time_tips("local business", data)
    await increment_quota(session, account_id=ctx.account_id, limit_key=LimitKey.AI_INSIGHT_CALLS_PER_MONTH)
    body = f"📊 {tips.get('headline', 'Best times')}\n" + "\n".join(
        f"• {x.get('when')} - {x.get('why')}" for x in tips.get("tips", [])
    )
    await cb.message.edit_text(body, reply_markup=back_to_menu())
    await cb.answer()


@router.callback_query(F.data == "ins:weekly")
async def cb_weekly(cb: CallbackQuery, session: AsyncSession, ctx: TenantContext):
    if not await _gate(session, ctx, cb):
        return
    sent = (
        await session.execute(
            select(func.count()).select_from(PostHistory).where(
                PostHistory.account_id == ctx.account_id, PostHistory.status == "succeeded"
            )
        )
    ).scalar_one()
    summary = await AIClient().weekly_summary({"posts_sent": sent})
    await increment_quota(session, account_id=ctx.account_id, limit_key=LimitKey.AI_INSIGHT_CALLS_PER_MONTH)
    await cb.message.edit_text(
        f"📊 Your week\n{summary.get('summary')}\n\n💡 {summary.get('suggestion')}",
        reply_markup=back_to_menu(),
    )
    await cb.answer()
