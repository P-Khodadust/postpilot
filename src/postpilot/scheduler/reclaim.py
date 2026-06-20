"""Reclaim expired leases so a crashed worker's in-flight posts get retried."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def reclaim_expired_leases(session: AsyncSession) -> int:
    """Reset rows whose lease expired back to 'failed' (will be re-picked with backoff)."""
    result = await session.execute(
        text(
            """
            UPDATE post_queue
               SET status = 'failed',
                   leased_by = NULL,
                   next_attempt_at = now()
             WHERE status IN ('leased','sending')
               AND lease_expires_at < now()
            """
        )
    )
    return result.rowcount or 0
