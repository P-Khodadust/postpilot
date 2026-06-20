"""Inline keyboard builders. Callback scheme: <domain>:<action>:<id>."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🌓 Open/Close posts", callback_data="sch:list")
    b.button(text="✍️ New post", callback_data="post:new")
    b.button(text="🗓 My schedule", callback_data="sch:list")
    b.button(text="📊 Insights", callback_data="ins:home")
    b.button(text="⚙️ Settings", callback_data="set:home")
    b.button(text="💳 Billing", callback_data="bill:home")
    b.button(text="🆘 Help", callback_data="help:home")
    b.adjust(2, 2, 2, 1)
    return b.as_markup()


def onboarding_intro() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✨ Let's set it up", callback_data="ob:start")
    b.button(text="❓ How it works", callback_data="help:home")
    b.adjust(1, 1)
    return b.as_markup()


def connect_button(authorize_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Open X to connect", url=authorize_url)],
            [InlineKeyboardButton(text="🔁 I finished - check now", callback_data="ob:check")],
        ]
    )


def days_picker(selected: set[int]) -> InlineKeyboardMarkup:
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    b = InlineKeyboardBuilder()
    for i, n in enumerate(names):
        mark = "✅" if i in selected else "⬜"
        b.button(text=f"{n} {mark}", callback_data=f"sch:day:{i}")
    b.button(text="✅ These days", callback_data="sch:days_done")
    b.adjust(3, 3, 1, 1)
    return b.as_markup()


def time_picker(slot: str, options: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for hhmm in options:
        b.button(text=hhmm, callback_data=f"sch:time:{slot}:{hhmm}")
    b.adjust(3)
    return b.as_markup()


def confirm(action: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Confirm", callback_data=f"{action}:yes")
    b.button(text="◀️ Back", callback_data="nav:menu")
    b.adjust(2)
    return b.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Menu", callback_data="nav:menu")]]
    )


def upgrade_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬆️ Upgrade", callback_data="bill:upgrade")
    b.button(text="🏠 Menu", callback_data="nav:menu")
    b.adjust(2)
    return b.as_markup()
