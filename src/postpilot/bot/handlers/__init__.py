"""Router aggregation."""

from __future__ import annotations

from aiogram import Router


def get_router() -> Router:
    from postpilot.bot.handlers import (
        billing,
        connect,
        core,
        insights,
        onboarding,
        posts,
        schedules,
    )

    root = Router()
    root.include_router(onboarding.router)
    root.include_router(connect.router)
    root.include_router(schedules.router)
    root.include_router(posts.router)
    root.include_router(insights.router)
    root.include_router(billing.router)
    root.include_router(core.router)  # core last (catch-all menu/help)
    return root
