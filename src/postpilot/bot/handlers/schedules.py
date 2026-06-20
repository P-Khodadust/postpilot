"""Recurring open/close schedule creation + listing."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.ai.client import AIClient
from postpilot.ai.prompts import BrandProfile
from postpilot.bot.keyboards import back_to_menu, confirm, days_picker, main_menu, time_picker
from postpilot.bot.states import ScheduleCreate
from postpilot.models import Account, ConnectedXAccount, MessageVariant, RecurringSchedule
from postpilot.tenancy.context import Role, TenantContext
from postpilot.tenancy.repo import require

router = Router()
OPEN_TIMES = ["07:00", "08:00", "09:00", "10:00"]
CLOSE_TIMES = ["16:00", "17:00", "18:00", "19:00"]


async def _connected(session: AsyncSession, ctx: TenantContext) -> ConnectedXAccount | None:
    return (
        await session.execute(
            select(ConnectedXAccount).where(
                ConnectedXAccount.account_id == ctx.account_id,
                ConnectedXAccount.status == "connected",
            )
        )
    ).scalars().first()


@router.message(Command("schedule"))
async def cmd_schedule(message: Message, session: AsyncSession, ctx: TenantContext):
    await _render_list(message, session, ctx)


@router.callback_query(F.data == "sch:list")
async def cb_list(cb: CallbackQuery, session: AsyncSession, ctx: TenantContext):
    await _render_list(cb, session, ctx)
    await cb.answer()


async def _render_list(event, session: AsyncSession, ctx: TenantContext):
    rows = (
        await session.execute(
            select(RecurringSchedule).where(RecurringSchedule.account_id == ctx.account_id)
        )
    ).scalars().all()
    if not rows:
        text = "🗓 Nothing scheduled yet. Want to set up your open/close posts?"
    else:
        lines = ["🗓 Your schedules:"]
        for s in rows:
            state = "▶️ active" if s.is_active else "⏸ paused"
            lines.append(f"• {s.name} - {state}")
        text = "\n".join(lines)
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    b = InlineKeyboardBuilder()
    b.button(text="➕ New open/close schedule", callback_data="sch:new")
    b.button(text="🏠 Menu", callback_data="nav:menu")
    b.adjust(1, 1)
    await _edit_or_send(event, text, b.as_markup())


@router.callback_query(F.data == "sch:new")
async def sch_new(cb: CallbackQuery, state: FSMContext, session: AsyncSession, ctx: TenantContext):
    require(ctx, Role.member)
    if not await _connected(session, ctx):
        await cb.message.edit_text("Connect your X account first: /connect", reply_markup=back_to_menu())
        await cb.answer()
        return
    await state.set_state(ScheduleCreate.days)
    await state.update_data(days=[])
    await cb.message.edit_text("🌓 Which days are you open?", reply_markup=days_picker(set()))
    await cb.answer()


@router.callback_query(ScheduleCreate.days, F.data.startswith("sch:day:"))
async def sch_toggle_day(cb: CallbackQuery, state: FSMContext):
    day = int(cb.data.split(":")[2])
    data = await state.get_data()
    days = set(data.get("days", []))
    days.symmetric_difference_update({day})
    await state.update_data(days=sorted(days))
    await cb.message.edit_reply_markup(reply_markup=days_picker(days))
    await cb.answer()


@router.callback_query(ScheduleCreate.days, F.data == "sch:days_done")
async def sch_days_done(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ScheduleCreate.open_time)
    await cb.message.edit_text("⏰ What time do you open?", reply_markup=time_picker("open", OPEN_TIMES))
    await cb.answer()


@router.callback_query(ScheduleCreate.open_time, F.data.startswith("sch:time:open:"))
async def sch_open(cb: CallbackQuery, state: FSMContext):
    await state.update_data(open=cb.data.split(":", 3)[3])
    await state.set_state(ScheduleCreate.close_time)
    await cb.message.edit_text("⏰ What time do you close?", reply_markup=time_picker("close", CLOSE_TIMES))
    await cb.answer()


@router.callback_query(ScheduleCreate.close_time, F.data.startswith("sch:time:close:"))
async def sch_close(cb: CallbackQuery, state: FSMContext):
    await state.update_data(close=cb.data.split(":", 3)[3])
    data = await state.get_data()
    days = ", ".join(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d] for d in data["days"])
    await state.set_state(ScheduleCreate.confirm)
    await cb.message.edit_text(
        f"Here's your plan:\n\n🌓 Open {days} at {data['open']}\n🌓 Close {days} at {data['close']}\n"
        "I'll write a few rotating versions of each. Turn it on?",
        reply_markup=confirm("sch:create"),
    )
    await cb.answer()


@router.callback_query(ScheduleCreate.confirm, F.data == "sch:create:yes")
async def sch_create(cb: CallbackQuery, state: FSMContext, session: AsyncSession, ctx: TenantContext):
    data = await state.get_data()
    acct = await _connected(session, ctx)
    account = await session.get(Account, ctx.account_id)
    tz = account.default_timezone if account else "UTC"

    schedule_cfg = {"schedule": {}, "append_date": True}
    for d in data["days"]:
        schedule_cfg["schedule"][str(d)] = {"open": data["open"], "close": data["close"]}

    sched = RecurringSchedule(
        account_id=ctx.account_id, x_account_id=acct.id, name="Open/Close",
        timezone=tz, config=schedule_cfg, is_active=True,
    )
    session.add(sched)
    await session.flush()

    ai = AIClient()
    brand = BrandProfile(
        business_name=account.name if account else "the business",
        business_type="local business", tone_words=["friendly", "warm"],
        sample_posts=[], avoid=[],
    )
    for slot, intent in (("open", "We're open"), ("close", "We're closed for today")):
        variants = await ai.generate_variants(brand, intent, n=3)
        session.add(MessageVariant(
            account_id=ctx.account_id, schedule_id=sched.id, slot=slot,
            variants=variants, cursor=0,
        ))

    await state.clear()
    await cb.message.edit_text(
        "🎉 You're all set. Your open/close posts will go out automatically.",
        reply_markup=main_menu(),
    )
    await cb.answer()


async def _edit_or_send(event, text, markup):
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=markup)
    else:
        await event.answer(text, reply_markup=markup)
