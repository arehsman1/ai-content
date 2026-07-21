"""
Application entry point (V1.2).

Starts Telegram bot + automatic Google News scheduler (4× daily by default).
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from src.bot import create_bot
from src.config.constants import APP_VERSION
from src.config.settings import get_settings
from src.notifications import TelegramNotifier
from src.scheduler import SchedulerManager
from src.utils.logging import setup_logging


async def run_app() -> None:
    """Create bot, notifier, scheduler and run until interrupted."""
    settings = get_settings()
    bot, dp = create_bot(settings)

    notifier = TelegramNotifier(bot, settings)

    scheduler_mgr = SchedulerManager(settings, notifier=notifier)
    scheduler_mgr.set_bot(bot)
    scheduler_mgr.setup()
    scheduler_mgr.start()

    dp["scheduler_mgr"] = scheduler_mgr
    dp["notifier"] = notifier

    logger.info("Starting Telegram polling…")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler_mgr.shutdown()
        await bot.session.close()
        logger.info("Bot session closed")


def main() -> int:
    try:
        settings = get_settings()
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        print(
            "\nMake sure you have copied .env.example to .env and filled in the required values.",
            file=sys.stderr,
        )
        return 1

    setup_logging(settings)

    logger.info("Starting {} v{}", settings.app_name, APP_VERSION)
    logger.info("Environment     : {}", settings.app_env)
    logger.info("Log level       : {}", settings.log_level)
    logger.info("News scanner    : {}", "enabled" if settings.enable_news_scanner else "disabled")
    logger.info("AI filter       : {}", "enabled" if settings.enable_ai_filter else "disabled")
    logger.info("Auto scan times : {} UTC", settings.scan_times_list)
    logger.info("Search window   : {} days", settings.news.search_window_days)
    logger.info("Allowed users   : {}", settings.telegram.allowed_ids)

    try:
        asyncio.run(run_app())
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception:
        logger.exception("Fatal error while running the application")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
