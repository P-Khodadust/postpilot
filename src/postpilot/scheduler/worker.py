"""The post-sending core: claim due rows (exactly-once via SKIP LOCKED), send, record."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.core.errors import XApiError
from postpilot.core.logging import get_logger
from postpilot.models import ConnectedXAccount, PostHistory, PostQueue
from postpilot.scheduler.token_refresh import valid_access_token
from postpilot.x_api.client import HttpXClient, XClient

log = get_logger("worker")
BASE_BACKOFF_SECONDS = 30


async def claim_due(session: AsyncSession, *, worker_id: str, batch: int = 20) -> list[PostQueue]:
    """Atomically lease up to `batch` due rows. FOR UPDATE SKIP LOCKED = exactly-once across replicas."""
    rows = await session.execute(
        text(
            """
            UPDATE post_queue q
               SET status = 'leased', leased_by = :wid, leased_at = now(),
                   lease_expires_at = now() + interval '2 minutes',
                   attempts = attempts + 1, updated_at = now()
             WHERE q.id IN (
                 SELECT id FROM post_queue
                  WHERE status IN ('pending','failed')
                    AND scheduled_for <= now()
                    AND (next_attempt_at IS NULL OR next_attempt_at <= now())
                  ORDER BY scheduled_for
                  FOR UPDATE SKIP LOCKED
                  LIMIT :batch
             )
             RETURNING q.id
            """
        ),
        {"wid": worker_id, "batch": batch},
    )
    ids = [r[0] for r in rows]
    if not ids:
        return []
    return list(
        (await session.execute(select(PostQueue).where(PostQueue.id.in_(ids)))).scalars().all()
    )


async def process_one(session: AsyncSession, row: PostQueue, xclient: XClient) -> None:
    from postpilot.metering.service import record_event
    from postpilot.notifications.service import enqueue_notification

    acct = (
        await session.execute(
            select(ConnectedXAccount).where(ConnectedXAccount.id == row.x_account_id)
        )
    ).scalar_one_or_none()
    if acct is None:
        row.status = "dead"
        row.last_error = "connected account missing"
        return

    row.status = "sending"
    await session.flush()
    try:
        token = await valid_access_token(session, acct)
        posted = await xclient.create_tweet(token, row.body)
    except XApiError as e:
        await _handle_failure(session, row, acct, e, enqueue_notification)
        await record_event(session, account_id=row.account_id, event_type="post_failed")
        return
    except Exception as e:  # noqa: BLE001 - unexpected: retry path
        await _handle_failure(
            session, row, acct,
            XApiError(str(e), retryable=True), enqueue_notification,
        )
        return

    row.status = "succeeded"
    row.last_error = None
    session.add(
        PostHistory(
            account_id=row.account_id, queue_id=row.id, x_account_id=row.x_account_id,
            body=row.body, status="succeeded", x_tweet_id=posted.id,
            attempt_number=row.attempts, posted_at=dt.datetime.now(dt.timezone.utc),
        )
    )
    await record_event(session, account_id=row.account_id, event_type="post_sent")
    await enqueue_notification(
        session, account_id=row.account_id, tg_user_id=_owner_tg(acct),
        kind="post_posted", title="Posted to X",
        body=f'✅ Posted to @{acct.x_handle or "your account"}\n"{row.body[:200]}"',
    )


async def _handle_failure(session, row: PostQueue, acct, err: XApiError, notify) -> None:
    if err.duplicate:
        # Rotation should prevent this; treat as terminal-skip, not an error storm.
        row.status = "skipped"
        row.last_error = "duplicate content"
        session.add(PostHistory(
            account_id=row.account_id, queue_id=row.id, x_account_id=row.x_account_id,
            body=row.body, status="failed", error_code="duplicate",
            error_detail="duplicate content", attempt_number=row.attempts,
        ))
        return
    if err.reauth_required:
        acct.status = "reauth_required"
        row.status = "failed"
        row.next_attempt_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
        row.last_error = "reauth required"
        await notify(
            session, account_id=row.account_id, tg_user_id=_owner_tg(acct),
            kind="reauth_required", title="Reconnect needed",
            body="⚠️ I lost the connection to your X account. Tap to reconnect.",
        )
        return

    terminal = (not err.retryable) or row.attempts >= row.max_attempts
    session.add(PostHistory(
        account_id=row.account_id, queue_id=row.id, x_account_id=row.x_account_id,
        body=row.body, status="failed",
        error_code=str(err.status or err.code), error_detail=err.message[:500],
        attempt_number=row.attempts,
    ))
    if terminal:
        row.status = "dead"
        row.last_error = err.message[:500]
        await notify(
            session, account_id=row.account_id, tg_user_id=_owner_tg(acct),
            kind="post_failed", title="A post didn't go out",
            body=f"⚠️ A scheduled post couldn't be sent. {err.user_message}",
        )
    else:
        row.status = "failed"
        row.last_error = err.message[:500]
        row.next_attempt_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
            seconds=BASE_BACKOFF_SECONDS * (2 ** (row.attempts - 1))
        )


def _owner_tg(acct: ConnectedXAccount) -> int:
    # Best-effort: notifications are addressed to the account's connecting member.
    # The notifications worker resolves the chat id from the membership/tg_user.
    return 0


async def run_tick(session: AsyncSession, *, worker_id: str, xclient: XClient | None = None) -> int:
    """One full tick: reclaim, materialize (leader), claim, send. Returns rows processed."""
    from postpilot.core.redis import with_lock
    from postpilot.scheduler.materializer import materialize
    from postpilot.scheduler.reclaim import reclaim_expired_leases

    xclient = xclient or HttpXClient()
    await reclaim_expired_leases(session)
    if await with_lock("materializer", ttl_seconds=30):
        await materialize(session)
    rows = await claim_due(session, worker_id=worker_id)
    for row in rows:
        await process_one(session, row, xclient)
    return len(rows)
