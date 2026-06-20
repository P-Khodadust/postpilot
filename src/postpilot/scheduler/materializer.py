"""Expand active recurring schedules into concrete post_queue rows (idempotently)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.core.logging import get_logger
from postpilot.models import MessageVariant, PostQueue, RecurringSchedule
from postpilot.scheduler.rotation import decorate, next_variant, plan_day

log = get_logger("materializer")
LOOKAHEAD_DAYS = 2


async def materialize(session: AsyncSession, *, now_utc: dt.datetime | None = None) -> int:
    """Create queue rows for the next LOOKAHEAD_DAYS for every active schedule. Returns count inserted."""
    now_utc = now_utc or dt.datetime.now(dt.timezone.utc)
    inserted = 0
    schedules = (
        (await session.execute(select(RecurringSchedule).where(RecurringSchedule.is_active.is_(True))))
        .scalars()
        .all()
    )
    for sched in schedules:
        # load variant cursors for this schedule
        variants = {
            v.slot: v
            for v in (
                await session.execute(
                    select(MessageVariant).where(MessageVariant.schedule_id == sched.id)
                )
            )
            .scalars()
            .all()
        }
        for offset in range(LOOKAHEAD_DAYS + 1):
            day = (now_utc.date() + dt.timedelta(days=offset))
            for planned in plan_day(
                sched.config, tz_name=sched.timezone, on_day=day, schedule_id=str(sched.id)
            ):
                if planned.fire_at_utc < now_utc:
                    continue
                var = variants.get(planned.slot)
                if not var or not var.variants:
                    continue
                body, new_cursor = next_variant(var.variants, var.cursor)
                body = decorate(body, append_date=bool(sched.config.get("append_date")), on_day=day)
                stmt = (
                    pg_insert(PostQueue)
                    .values(
                        account_id=sched.account_id,
                        x_account_id=sched.x_account_id,
                        schedule_id=sched.id,
                        body=body[:4000],
                        scheduled_for=planned.fire_at_utc,
                        status="pending",
                        idempotency_key=planned.idempotency_key,
                    )
                    .on_conflict_do_nothing(constraint="ux_queue_idem")
                )
                res = await session.execute(stmt)
                if res.rowcount:
                    inserted += res.rowcount
                    var.cursor = new_cursor  # only advance when we actually scheduled a new post
        sched.last_materialized_for = (now_utc + dt.timedelta(days=LOOKAHEAD_DAYS)).date()
    if inserted:
        log.info("materialize.inserted", count=inserted)
    return inserted


async def enqueue_adhoc(
    session: AsyncSession,
    *,
    account_id,
    x_account_id,
    body: str,
    scheduled_for: dt.datetime,
    idempotency_key: str,
) -> None:
    """Insert a one-off post (also used for immediate 'post now')."""
    await session.execute(
        text(
            """
            INSERT INTO post_queue
              (id, account_id, x_account_id, body, scheduled_for, status, idempotency_key,
               attempts, max_attempts, created_at, updated_at)
            VALUES
              (gen_random_uuid(), :acc, :xacc, :body, :sched, 'pending', :idem, 0, 5, now(), now())
            ON CONFLICT (account_id, idempotency_key) DO NOTHING
            """
        ),
        {
            "acc": str(account_id),
            "xacc": str(x_account_id),
            "body": body[:4000],
            "sched": scheduled_for,
            "idem": idempotency_key,
        },
    )
