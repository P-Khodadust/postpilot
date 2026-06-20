"""Scheduler/worker process: lease+send due posts, dispatch notifications, periodic rollups.

Horizontally scalable: exactly-once delivery comes from Postgres row leasing (SKIP LOCKED),
not from this loop, so running N replicas is safe.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid

from postpilot.core.config import get_settings
from postpilot.core.db import session_scope
from postpilot.core.logging import configure_logging, get_logger
from postpilot.notifications.service import dispatch_pending
from postpilot.scheduler.worker import run_tick

log = get_logger("worker")


async def _loop() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    log.info("worker.start", worker_id=worker_id, tick=settings.scheduler_tick_seconds)

    from postpilot.bot.main import build_bot

    bot = build_bot()
    try:
        while True:
            try:
                async with session_scope() as session:
                    processed = await run_tick(session, worker_id=worker_id)
                async with session_scope() as session:
                    sent = await dispatch_pending(session, bot)
                if processed or sent:
                    log.info("worker.tick", processed=processed, notifications=sent)
            except Exception as e:  # noqa: BLE001 - never let one tick kill the loop
                log.error("worker.tick_error", error=str(e))
            await asyncio.sleep(settings.scheduler_tick_seconds)
    finally:
        with contextlib.suppress(Exception):
            await bot.session.close()


def main() -> None:
    asyncio.run(_loop())


if __name__ == "__main__":
    main()
