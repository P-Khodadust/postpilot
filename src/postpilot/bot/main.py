"""Bot runtime. Exposes build_bot()/build_dispatcher() (reused by the web webhook route)."""

from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage

from postpilot.bot.handlers import get_router
from postpilot.bot.middlewares.tenant import TenantMiddleware
from postpilot.core.config import get_settings
from postpilot.core.logging import configure_logging, get_logger

log = get_logger("bot")


def build_bot() -> Bot:
    settings = get_settings()
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )


def build_dispatcher() -> Dispatcher:
    settings = get_settings()
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)
    tenant = TenantMiddleware()
    dp.message.middleware(tenant)
    dp.callback_query.middleware(tenant)
    dp.include_router(get_router())
    return dp


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    bot = build_bot()
    dp = build_dispatcher()
    if settings.telegram_use_webhook:
        url = f"{settings.public_base_url}/telegram/webhook"
        await bot.set_webhook(url, secret_token=settings.telegram_webhook_secret,
                              drop_pending_updates=False)
        log.info("bot.webhook_set", url=url)
        # The web service receives & dispatches updates; idle here.
        while True:
            await asyncio.sleep(3600)
    else:
        await bot.delete_webhook(drop_pending_updates=False)
        log.info("bot.polling_start")
        await dp.start_polling(bot)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
