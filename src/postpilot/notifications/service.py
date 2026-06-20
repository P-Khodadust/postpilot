"""Outbound notifications: enqueue from anywhere, dispatch to Telegram from the worker."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.core.logging import get_logger
from postpilot.models import Membership, Notification

log = get_logger("notifications")


async def _resolve_owner_tg(session: AsyncSession, account_id: uuid.UUID) -> int | None:
    return (
        await session.execute(
            select(Membership.tg_user_id)
            .where(Membership.account_id == account_id, Membership.role == "owner")
            .limit(1)
        )
    ).scalar_one_or_none()


async def enqueue_notification(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    tg_user_id: int,
    kind: str,
    title: str,
    body: str,
) -> None:
    if not tg_user_id:
        resolved = await _resolve_owner_tg(session, account_id)
        if not resolved:
            log.warning("notify.no_recipient", account_id=str(account_id), kind=kind)
            return
        tg_user_id = resolved
    session.add(
        Notification(
            account_id=account_id, tg_user_id=tg_user_id, kind=kind, title=title, body=body
        )
    )


async def dispatch_pending(session: AsyncSession, bot, *, batch: int = 50) -> int:
    """Send pending notifications via the aiogram bot. Returns number sent."""
    pending = (
        (await session.execute(
            select(Notification).where(Notification.status == "pending").limit(batch)
        ))
        .scalars()
        .all()
    )
    sent = 0
    for n in pending:
        try:
            await bot.send_message(n.tg_user_id, n.body)
            await session.execute(
                update(Notification).where(Notification.id == n.id).values(status="sent")
            )
            sent += 1
        except Exception as e:  # noqa: BLE001
            n.attempts += 1
            n.status = "failed" if n.attempts >= 3 else "pending"
            log.warning("notify.send_failed", id=str(n.id), error=str(e))
    return sent
