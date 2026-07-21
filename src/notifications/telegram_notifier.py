"""
Telegram notification system – sends single lifecycle opportunity cards.
"""

from __future__ import annotations

from typing import List, Sequence

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from loguru import logger

from src.bot.keyboards import opportunity_keyboard
from src.bot.store import Opportunity, store
from src.config.settings import AppSettings


class TelegramNotifier:
    def __init__(self, bot: Bot, settings: AppSettings) -> None:
        self.bot = bot
        self.settings = settings
        self.allowed_ids: List[int] = settings.telegram.allowed_ids

    async def notify(self, opportunity: Opportunity) -> bool:
        if not self.allowed_ids:
            logger.warning("No allowed Telegram user IDs configured – cannot notify")
            return False

        text = opportunity.render_new()
        keyboard = opportunity_keyboard(opportunity.id)
        success = False

        for user_id in self.allowed_ids:
            try:
                msg = await self.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                store.bind_message(opportunity.id, user_id, msg.message_id)
                logger.info(
                    "Notification sent | opp_id={} | user_id={}",
                    opportunity.id,
                    user_id,
                )
                success = True
            except TelegramAPIError as exc:
                logger.error(
                    "Failed to send notification | opp_id={} | user_id={} | error={}",
                    opportunity.id,
                    user_id,
                    exc,
                )
        return success

    async def notify_many(self, opportunities: Sequence[Opportunity]) -> int:
        if not opportunities:
            return 0
        sent = 0
        for opp in opportunities:
            if await self.notify(opp):
                sent += 1
        return sent
