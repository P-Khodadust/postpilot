"""Nightly aggregation into platform_daily_metrics (cheap dashboard reads)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def rollup_day(session: AsyncSession, day: dt.date | None = None) -> None:
    day = day or (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1))
    await session.execute(
        text(
            """
            INSERT INTO platform_daily_metrics
              (day, posts_sent, posts_failed, new_accounts, active_subs, trials)
            SELECT
              :day,
              COALESCE((SELECT count(*) FROM usage_events
                        WHERE event_type='post_sent' AND occurred_at::date=:day), 0),
              COALESCE((SELECT count(*) FROM usage_events
                        WHERE event_type='post_failed' AND occurred_at::date=:day), 0),
              COALESCE((SELECT count(*) FROM accounts WHERE created_at::date=:day), 0),
              COALESCE((SELECT count(*) FROM subscriptions WHERE status='active'), 0),
              COALESCE((SELECT count(*) FROM subscriptions WHERE status='trialing'), 0)
            ON CONFLICT (day) DO UPDATE SET
              posts_sent = EXCLUDED.posts_sent,
              posts_failed = EXCLUDED.posts_failed,
              new_accounts = EXCLUDED.new_accounts,
              active_subs = EXCLUDED.active_subs,
              trials = EXCLUDED.trials
            """
        ),
        {"day": day},
    )
