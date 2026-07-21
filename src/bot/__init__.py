"""
Telegram bot package.

Public API:
    create_bot() – build Bot + Dispatcher with routers, middlewares, and FSM storage
"""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

from src.bot.handlers import router as main_router
from src.bot.middlewares import AuthMiddleware
from src.config.settings import AppSettings


def create_bot(settings: AppSettings) -> tuple[Bot, Dispatcher]:
    """
    Construct a fully configured Bot and Dispatcher with FSM support.
    """
    bot = Bot(
        token=settings.telegram.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.message.middleware(AuthMiddleware(settings))
    dp.callback_query.middleware(AuthMiddleware(settings))

    dp.include_router(main_router)

    logger.info(
        "Telegram bot created | allowed_users={}",
        settings.telegram.allowed_ids,
    )
    return bot, dp
