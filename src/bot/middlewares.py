"""
Bot middlewares.

Currently implements a simple allow-list based on TELEGRAM_ALLOWED_USER_IDS.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from loguru import logger

from src.config.settings import AppSettings


class AuthMiddleware(BaseMiddleware):
    """
    Reject any update that does not come from an allowed user ID.

    Allowed IDs are read from settings.telegram.allowed_ids.
    """

    def __init__(self, settings: AppSettings) -> None:
        self.allowed_ids = set(settings.telegram.allowed_ids)
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = None

        if isinstance(event, Message) and event.from_user:
            user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user = event.from_user

        if user is None:
            logger.warning("Received update without from_user – ignoring")
            return None

        if user.id not in self.allowed_ids:
            logger.warning(
                "Unauthorized access attempt | user_id={} | username={}",
                user.id,
                user.username,
            )
            # Silently ignore (do not even reply) to avoid leaking that the bot exists
            return None

        # Inject settings into handler data for convenience
        data["settings"] = self.settings
        return await handler(event, data)
