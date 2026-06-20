"""aiogram FSM state groups (one per multi-step flow)."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    intro = State()
    awaiting_oauth = State()
    timezone = State()
    days = State()
    open_time = State()
    close_time = State()
    wording = State()
    confirm = State()


class ScheduleCreate(StatesGroup):
    days = State()
    open_time = State()
    close_time = State()
    confirm = State()


class Compose(StatesGroup):
    text = State()
    when = State()
    confirm = State()


class Support(StatesGroup):
    awaiting_msg = State()
