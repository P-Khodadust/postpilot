"""Usage metering: cheap append-only events + monthly quota counters."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.models import UsageCounter, UsageEvent


def current_period_start(now: dt.datetime | None = None) -> dt.date:
    now = now or dt.datetime.now(dt.timezone.utc)
    return dt.date(now.year, now.month, 1)


async def record_event(
    session: AsyncSession,
    *,
    account_id: uuid.UUID | None,
    event_type: str,
    quantity: int = 1,
    payload: dict | None = None,
) -> None:
    """Append a raw analytics event. Never on the critical path of a user reply."""
    session.add(
        UsageEvent(
            account_id=account_id, event_type=event_type, quantity=quantity, payload=payload
        )
    )


async def increment_quota(
    session: AsyncSession, *, account_id: uuid.UUID, limit_key: str, amount: int = 1
) -> None:
    """Atomic UPSERT increment of the current month's counter for a quota key."""
    await session.execute(
        text(
            """
            INSERT INTO usage_counters (account_id, period_start, limit_key, used, updated_at)
            VALUES (:acc, :period, :key, :amt, now())
            ON CONFLICT (account_id, period_start, limit_key)
            DO UPDATE SET used = usage_counters.used + EXCLUDED.used, updated_at = now()
            """
        ),
        {"acc": str(account_id), "period": current_period_start(), "key": limit_key, "amt": amount},
    )


async def current_period_usage(
    session: AsyncSession, *, account_id: uuid.UUID, limit_key: str
) -> int:
    row = (
        await session.execute(
            select(UsageCounter.used).where(
                UsageCounter.account_id == account_id,
                UsageCounter.period_start == current_period_start(),
                UsageCounter.limit_key == limit_key,
            )
        )
    ).scalar_one_or_none()
    return int(row or 0)
