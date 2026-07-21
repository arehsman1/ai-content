"""
Live progress message for the hybrid filter pipeline.

Stages:
  0 – Collecting articles (Google News)
  1 – Python Filtering
  2 – AI Filtering
  3 – Preparing Opportunities
  Complete / Failed
"""

from __future__ import annotations

from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from loguru import logger


def _bar(percent: int, width: int = 10) -> str:
    pct = max(0, min(100, int(percent)))
    filled = max(0, min(width, round(pct / 100 * width)))
    return "█" * filled + "░" * (width - filled)


class ScanProgress:
    """Single Telegram message updated through the hybrid scan pipeline."""

    def __init__(self, bot: Bot, chat_id: int) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.message_id: Optional[int] = None

        self.phase: str = "collect"  # collect | python | ai | prepare | done
        self.percent: int = 0

        # Collection
        self.keywords_total: int = 0
        self.keywords_done: int = 0
        self.articles_found: int = 0
        self.current_task: str = "Starting…"

        # Python filter
        self.py_received: int = 0
        self.py_passed: int = 0
        self.py_removed: int = 0

        # AI filter
        self.ai_total: int = 0
        self.ai_analyzed: int = 0
        self.ai_passed: int = 0
        self.ai_rejected: int = 0
        self.current_title: str = ""
        self.eta_text: str = ""

        # Prepare / complete
        self.approved: int = 0
        self.unique_articles: int = 0

        self.finished: bool = False
        self.failed: bool = False
        self.error_reason: str = ""
        self.next_scan: str = ""

    async def start(self, keywords_total: int) -> None:
        self.keywords_total = keywords_total
        self.phase = "collect"
        self.percent = 0
        self.current_task = "Searching Google News…"
        try:
            msg = await self.bot.send_message(
                self.chat_id, self._render(), parse_mode="HTML"
            )
            self.message_id = msg.message_id
        except TelegramAPIError as exc:
            logger.warning("Could not send progress message: {}", exc)

    async def stage1_update(
        self,
        *,
        keywords_done: int,
        articles_found: int,
        task: Optional[str] = None,
    ) -> None:
        """Collection progress (before Python filter)."""
        self.phase = "collect"
        self.keywords_done = keywords_done
        self.articles_found = articles_found
        if task is not None:
            self.current_task = task
        if self.keywords_total > 0:
            self.percent = min(100, int(keywords_done / self.keywords_total * 100))
        await self._edit()

    async def stage_python(
        self,
        *,
        received: int,
        passed: int,
        removed: int,
        percent: int = 100,
    ) -> None:
        self.phase = "python"
        self.py_received = received
        self.py_passed = passed
        self.py_removed = removed
        self.percent = max(0, min(100, percent))
        await self._edit()

    async def stage_ai(
        self,
        *,
        total: int,
        analyzed: int,
        passed: int,
        rejected: int,
        current_title: str = "",
        eta_text: str = "",
        percent: int = 0,
    ) -> None:
        self.phase = "ai"
        self.ai_total = total
        self.ai_analyzed = analyzed
        self.ai_passed = passed
        self.ai_rejected = rejected
        self.current_title = current_title
        self.eta_text = eta_text
        self.percent = max(0, min(100, percent))
        await self._edit()

    async def stage_prepare(self, *, approved: int, percent: int = 100) -> None:
        self.phase = "prepare"
        self.approved = approved
        self.percent = max(0, min(100, percent))
        await self._edit()

    async def complete(
        self,
        *,
        articles_found: int,
        unique_articles: int,
        relevant: int,
        next_scan: str = "",
    ) -> None:
        self.finished = True
        self.phase = "done"
        self.articles_found = articles_found
        self.unique_articles = unique_articles
        self.approved = relevant
        self.next_scan = next_scan
        await self._edit()

    async def fail(self, reason: str, next_scan: str = "") -> None:
        self.failed = True
        self.error_reason = reason
        self.next_scan = next_scan
        await self._edit()

    # Back-compat aliases used by older call sites
    async def stage2_update(self, **kwargs) -> None:
        # Map old "duplicates" stage → python display if needed
        await self.stage_python(
            received=kwargs.get("raw_articles", kwargs.get("received", 0)),
            passed=kwargs.get("unique_articles", kwargs.get("passed", 0)),
            removed=kwargs.get("duplicates_removed", kwargs.get("removed", 0)),
            percent=kwargs.get("percent", 100),
        )

    async def stage3_update(self, **kwargs) -> None:
        await self.stage_ai(
            total=kwargs.get("total", 0),
            analyzed=kwargs.get("analyzed", 0),
            passed=kwargs.get("passed", 0),
            rejected=kwargs.get("rejected", 0),
            current_title=kwargs.get("current_title", ""),
            eta_text=kwargs.get("eta_text", ""),
            percent=kwargs.get("percent", 0),
        )

    async def stage4_update(self, **kwargs) -> None:
        await self.stage_prepare(
            approved=kwargs.get("approved", 0),
            percent=kwargs.get("percent", 100),
        )

    def _render(self) -> str:
        if self.failed:
            return (
                f"❌ <b>Google News Scan Failed</b>\n\n"
                f"<b>Reason:</b>\n{self.error_reason}\n\n"
                f"<b>Next Scheduled Scan:</b>\n{self.next_scan or '—'}\n\n"
                f"The automatic scheduler is still running."
            )

        if self.finished:
            return (
                f"✅ <b>Google News Scan Completed</b>\n\n"
                f"<b>Articles Found:</b>\n{self.articles_found}\n\n"
                f"<b>Unique Articles:</b>\n{self.unique_articles}\n\n"
                f"<b>Relevant Opportunities:</b>\n{self.approved}\n\n"
                f"Ready for review."
            )

        bar = _bar(self.percent)

        if self.phase == "collect":
            return (
                f"🔎 <b>Google News Scan Started</b>\n\n"
                f"<b>Collecting Articles</b>\n\n"
                f"{bar} {self.percent}%\n\n"
                f"<b>Current Task:</b>\n{self.current_task}\n\n"
                f"<b>Keywords Checked:</b>\n"
                f"{self.keywords_done}/{self.keywords_total}\n\n"
                f"<b>Articles Found:</b>\n{self.articles_found}"
            )

        if self.phase == "python":
            return (
                f"🔎 <b>Google News Scan Started</b>\n\n"
                f"<b>Stage 1/4:</b>\nPython Filtering\n\n"
                f"{bar} {self.percent}%\n\n"
                f"<b>Received:</b>\n{self.py_received}\n\n"
                f"<b>Passed:</b>\n{self.py_passed}\n\n"
                f"<b>Removed:</b>\n{self.py_removed}"
            )

        if self.phase == "ai":
            title = self.current_title or "—"
            if len(title) > 80:
                title = title[:77] + "…"
            eta = self.eta_text or "—"
            return (
                f"🔎 <b>Google News Scan Started</b>\n\n"
                f"<b>Stage 2/4:</b>\nAI Filtering\n\n"
                f"{bar} {self.percent}%\n\n"
                f"<b>Currently analyzing:</b>\n\"{title}\"\n\n"
                f"<b>Analyzed:</b>\n{self.ai_analyzed}/{self.ai_total}\n\n"
                f"<b>Passed:</b>\n{self.ai_passed}\n\n"
                f"<b>Rejected:</b>\n{self.ai_rejected}\n\n"
                f"<b>Estimated Time Remaining:</b>\n{eta}"
            )

        # prepare
        return (
            f"🔎 <b>Google News Scan Started</b>\n\n"
            f"<b>Stage 3/4:</b>\nPreparing Opportunities\n\n"
            f"{bar} {self.percent}%\n\n"
            f"<b>Approved Opportunities:</b>\n{self.approved}"
        )

    async def _edit(self) -> None:
        if not self.message_id:
            return
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_id,
                text=self._render(),
                parse_mode="HTML",
            )
        except TelegramAPIError as exc:
            if "not modified" not in str(exc).lower():
                logger.debug("Progress edit failed: {}", exc)
