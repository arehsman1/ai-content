"""
Scheduled jobs for Google News – hybrid Python + AI filtering.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.ai.filter_engine import AIFilterEngine
from src.ai.pipeline import hybrid_filter
from src.bot.store import Opportunity, store
from src.config.settings import AppSettings
from src.notifications.telegram_notifier import TelegramNotifier
from src.scanners.news_scanner import NewsScanner
from src.utils.progress import ScanProgress


class SchedulerManager:
    def __init__(
        self,
        settings: AppSettings,
        notifier: Optional[TelegramNotifier] = None,
    ) -> None:
        self.settings = settings
        self.notifier = notifier
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.news_scanner: Optional[NewsScanner] = None
        self.filter_engine = AIFilterEngine(settings)
        self._bot = None
        self._scan_running = False

        if settings.enable_news_scanner:
            self.news_scanner = NewsScanner(settings)

    def set_notifier(self, notifier: TelegramNotifier) -> None:
        self.notifier = notifier
        logger.info("Telegram notifier attached to scheduler")

    def set_bot(self, bot) -> None:
        self._bot = bot

    def setup(self) -> None:
        if not (self.news_scanner and self.settings.enable_news_scanner):
            logger.warning("News scanner disabled – no automatic jobs registered")
            return

        for time_str in self.settings.scan_times_list:
            try:
                hour, minute = time_str.split(":")
                hour_i, minute_i = int(hour), int(minute)
            except ValueError:
                logger.error("Invalid scan time {!r} – expected HH:MM", time_str)
                continue

            job_id = f"news_scan_{hour_i:02d}{minute_i:02d}"
            self.scheduler.add_job(
                self._run_scheduled_scan,
                trigger=CronTrigger(hour=hour_i, minute=minute_i, timezone="UTC"),
                id=job_id,
                name=f"Google News Scan @ {time_str} UTC",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            logger.info("Scheduled Google News scan daily at {} UTC", time_str)

    async def _run_scheduled_scan(self) -> None:
        logger.info("=== Automatic scheduled scan starting ===")
        if not self.notifier or not self._bot:
            await self._execute_scan(chat_ids=[])
            return
        await self._execute_scan(chat_ids=self.settings.telegram.allowed_ids)

    async def run_manual_scan(self, chat_id: int) -> List[Opportunity]:
        logger.info("=== Manual scan requested by chat_id={} ===", chat_id)
        return await self._execute_scan(chat_ids=[chat_id])

    async def _execute_scan(self, chat_ids: List[int]) -> List[Opportunity]:
        if self._scan_running:
            logger.warning("Scan already in progress – skipping overlapping run")
            return []

        if not self.news_scanner:
            logger.warning("News scanner not available")
            return []

        self._scan_running = True
        progress_trackers: List[ScanProgress] = []

        try:
            if self._bot and chat_ids:
                for cid in chat_ids:
                    p = ScanProgress(self._bot, cid)
                    await p.start(keywords_total=len(self.settings.niche_list))
                    progress_trackers.append(p)

            async def on_collect(**kwargs):
                for p in progress_trackers:
                    await p.stage1_update(**kwargs)

            scan_result = await self.news_scanner.scan(progress=on_collect)

            async def on_filter(**kwargs):
                stage = kwargs.get("stage")
                for p in progress_trackers:
                    if stage == "python":
                        await p.stage_python(
                            received=kwargs.get("received", 0),
                            passed=kwargs.get("passed", 0),
                            removed=kwargs.get("removed", 0),
                            percent=kwargs.get("percent", 100),
                        )
                    elif stage == "ai":
                        await p.stage_ai(
                            total=kwargs.get("total", 0),
                            analyzed=kwargs.get("analyzed", 0),
                            passed=kwargs.get("passed", 0),
                            rejected=kwargs.get("rejected", 0),
                            current_title=kwargs.get("current_title", ""),
                            eta_text=kwargs.get("eta_text", ""),
                            percent=kwargs.get("percent", 0),
                        )

            passed = await hybrid_filter(
                scan_result.opportunities,
                self.settings,
                self.filter_engine,
                progress=on_filter,
            )

            for p in progress_trackers:
                await p.stage_prepare(approved=len(passed), percent=100)

            for opp in passed:
                h = opp.raw_data.get("content_hash")
                if h:
                    store.mark_notified(h)

            store.last_scan_at = datetime.now(timezone.utc)
            store.last_scan_stats = {
                "keywords": len(self.settings.niche_list),
                "found": scan_result.raw_articles,
                "unique": scan_result.unique_articles,
                "opportunities": len(passed),
            }

            next_scan = self.next_scan_time_str()
            for p in progress_trackers:
                await p.complete(
                    articles_found=scan_result.raw_articles,
                    unique_articles=scan_result.unique_articles,
                    relevant=len(passed),
                    next_scan=next_scan,
                )

            if passed and self.notifier:
                await self.notifier.notify_many(passed)
                logger.info("Delivered {} opportunities", len(passed))

            return passed

        except Exception as exc:
            logger.exception("Scan failed: {}", exc)
            next_scan = self.next_scan_time_str()
            for p in progress_trackers:
                await p.fail(reason=str(exc)[:200], next_scan=next_scan)
            return []
        finally:
            self._scan_running = False
            store.cleanup_old_hashes(self.settings.dedup_window_hours)

    def next_scan_time_str(self) -> str:
        jobs = self.scheduler.get_jobs()
        if not jobs:
            return "—"
        next_runs = [j.next_run_time for j in jobs if j.next_run_time]
        if not next_runs:
            return "—"
        return min(next_runs).strftime("%Y-%m-%d %H:%M UTC")

    def last_scan_time_str(self) -> str:
        if not store.last_scan_at:
            return "Never"
        return store.last_scan_at.strftime("%Y-%m-%d %H:%M UTC")

    def status_text(self) -> str:
        times = ", ".join(self.settings.scan_times_list) or "—"
        return (
            f"<b>📊 Scanner Status</b>\n\n"
            f"<b>Auto Scan:</b>\n"
            f"{'✅ Enabled' if self.settings.enable_news_scanner else '❌ Disabled'}\n\n"
            f"<b>Source:</b>\nGoogle News\n\n"
            f"<b>Frequency:</b>\n{len(self.settings.scan_times_list)} Times Per Day\n"
            f"({times} UTC)\n\n"
            f"<b>Last Scan:</b>\n{self.last_scan_time_str()}\n\n"
            f"<b>Next Scan:</b>\n{self.next_scan_time_str()}\n\n"
            f"<b>Search Window:</b>\nLast {self.settings.news.search_window_days} Days\n\n"
            f"<b>Scheduler:</b>\n"
            f"{'Running' if self.scheduler.running else 'Stopped'}"
        )

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started (cron jobs active)")

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler shut down")
