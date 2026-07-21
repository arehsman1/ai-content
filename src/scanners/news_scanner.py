"""
Google News scanner with 3-day window and stage-1 progress reporting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Awaitable, Callable, List, Optional, Set
from urllib.parse import quote_plus, urlparse

import feedparser
from loguru import logger

from src.bot.store import Opportunity, store
from src.config.constants import SourceType
from src.config.settings import AppSettings
from src.scanners.base import BaseScanner
from src.utils.helpers import clean_text, generate_content_hash, is_valid_url, truncate

ProgressCallback = Callable[..., Awaitable[None]]


@dataclass
class ScanResult:
    """Result of a Google News scan including stats for progress stages."""

    opportunities: List[Opportunity] = field(default_factory=list)
    raw_articles: int = 0
    duplicates_removed: int = 0
    unique_articles: int = 0


class NewsScanner(BaseScanner):
    """Google News RSS scanner."""

    name = "google_news"

    RSS_SEARCH_URL = (
        "https://news.google.com/rss/search"
        "?q={query}&hl={lang}-{country}&gl={country}&ceid={country}:{lang}"
    )

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._seen_hashes: Set[str] = set()

    @property
    def is_ready(self) -> bool:
        return self.settings.enable_news_scanner

    async def health_check(self) -> bool:
        try:
            url = self._build_feed_url("technology")
            feed = feedparser.parse(url)
            return bool(feed and feed.entries)
        except Exception as exc:
            logger.warning("News scanner health check failed: {}", exc)
            return False

    async def scan(
        self,
        progress: Optional[ProgressCallback] = None,
    ) -> ScanResult:
        """
        Run a full Google News scan for every niche keyword.

        progress is called as:
            await progress(keywords_done=..., articles_found=..., task=...)
        """
        if not self.is_ready:
            logger.warning("News scanner is disabled – skipping")
            return ScanResult()

        keywords = self.settings.niche_list
        logger.info(
            "Starting Google News scan | niche={} | window={}d",
            keywords,
            self.settings.news.search_window_days,
        )

        opportunities: List[Opportunity] = []
        total_found = 0
        total_dupes = 0
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=self.settings.news.search_window_days
        )

        for idx, keyword in enumerate(keywords):
            if progress:
                await progress(
                    keywords_done=idx,
                    articles_found=total_found,
                    task=f"Searching: {keyword}",
                )
            try:
                found, raw_count, dupes = await self._fetch_for_keyword(
                    keyword, cutoff=cutoff
                )
                opportunities.extend(found)
                total_found += raw_count
                total_dupes += dupes
            except Exception as exc:
                logger.exception("News fetch failed for keyword {!r}: {}", keyword, exc)

            if progress:
                await progress(
                    keywords_done=idx + 1,
                    articles_found=total_found,
                    task=f"Searching: {keyword}",
                )

        unique = len(opportunities)
        logger.info(
            "Google News scan finished | raw={} | unique={} | dupes={}",
            total_found,
            unique,
            total_dupes,
        )
        return ScanResult(
            opportunities=opportunities,
            raw_articles=total_found,
            duplicates_removed=total_dupes,
            unique_articles=unique,
        )

    def _build_feed_url(self, query: str) -> str:
        lang = self.settings.news.language or "en"
        country = self.settings.news.country or "US"
        days = self.settings.news.search_window_days
        q = f"{query} when:{days}d"
        encoded = quote_plus(q)
        return self.RSS_SEARCH_URL.format(
            query=encoded,
            lang=lang,
            country=country,
        )

    async def _fetch_for_keyword(
        self,
        keyword: str,
        cutoff: datetime,
    ) -> tuple[List[Opportunity], int, int]:
        url = self._build_feed_url(keyword)
        logger.debug("Fetching Google News RSS | keyword={!r}", keyword)

        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            logger.warning("Network error fetching feed for {!r}: {}", keyword, exc)
            return [], 0, 0

        if getattr(feed, "bozo", False) and not feed.entries:
            logger.warning(
                "Failed to parse feed for {!r}: {}",
                keyword,
                getattr(feed, "bozo_exception", "unknown"),
            )
            return [], 0, 0

        results: List[Opportunity] = []
        raw_count = 0
        dupes = 0
        max_items = self.settings.max_results_per_scan

        for entry in feed.entries[:max_items]:
            raw_count += 1
            opp = self._entry_to_opportunity(entry, source_query=keyword, cutoff=cutoff)
            if opp is None:
                dupes += 1
                continue
            results.append(opp)

        return results, raw_count, dupes

    def _entry_to_opportunity(
        self,
        entry: feedparser.FeedParserDict,
        source_query: str,
        cutoff: datetime,
    ) -> Optional[Opportunity]:
        title = clean_text(entry.get("title", ""))
        summary = clean_text(entry.get("summary", entry.get("description", "")))
        link = entry.get("link", "").strip()

        if not title or len(title) < 15:
            return None
        if not is_valid_url(link):
            return None

        published = None
        if entry.get("published"):
            try:
                published = parsedate_to_datetime(entry.published)
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
            except Exception:
                published = None

        if published and published < cutoff:
            return None

        combined = f"{title} {summary}"
        if not self._matches_niche(combined):
            return None

        content_hash = generate_content_hash(link, title)

        if content_hash in self._seen_hashes:
            return None
        if store.was_recently_notified(
            content_hash, window_hours=self.settings.dedup_window_hours
        ):
            return None
        self._seen_hashes.add(content_hash)

        for existing in store.all():
            if existing.url == link or existing.raw_data.get("content_hash") == content_hash:
                return None

        source_name = "Google News"
        if entry.get("source") and entry.source.get("title"):
            source_name = entry.source.title
        else:
            parsed = urlparse(link)
            if parsed.netloc and "news.google" not in parsed.netloc:
                source_name = parsed.netloc.replace("www.", "")

        reason = (
            f"Matched niche keyword “{source_query}”. "
            f"Published by {source_name}."
            + (f" Date: {published.strftime('%Y-%m-%d')}" if published else "")
        )

        suggested_angle = (
            f"Cover “{truncate(title, 80)}” from the angle of what it means "
            "for practitioners. Focus on implications, not just the headline. "
            "End with a question that invites informed discussion."
        )

        opp = store.add(
            source=SourceType.GOOGLE_NEWS,
            title=truncate(title, 140),
            summary=truncate(summary or title, 400),
            url=link,
            reason=reason,
            suggested_angle=suggested_angle,
            matched_keyword=source_query,
            score=0.0,
            raw_data={
                "content_hash": content_hash,
                "source_name": source_name,
                "query": source_query,
                "published": published.isoformat() if published else None,
            },
        )
        return opp

    def _matches_niche(self, text: str) -> bool:
        text_lower = text.lower()
        for kw in self.settings.niche_list:
            if " " in kw:
                if kw.lower() in text_lower:
                    return True
            else:
                if re.search(rf"\b{re.escape(kw.lower())}\b", text_lower):
                    return True
        return False
