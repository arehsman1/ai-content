"""
Stage 1 – Python Fast Filter.

Scores articles against NICHE_KEYWORDS and drops low-scoring items
before any AI calls are made.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Sequence, Tuple

from loguru import logger

from src.bot.store import Opportunity
from src.config.constants import ContentStatus
from src.config.settings import AppSettings
from src.bot.store import store


@dataclass
class PythonFilterResult:
    passed: List[Opportunity] = field(default_factory=list)
    received: int = 0
    removed: int = 0


def score_opportunity(
    opp: Opportunity,
    keywords: Sequence[str],
    *,
    now: datetime | None = None,
) -> int:
    """
    Score 0–100 based on keyword presence and freshness.

    Title match:            +50
    Description match:      +30
    Multiple keyword hits:  +20
    Published within 24h:   +10
    """
    now = now or datetime.now(timezone.utc)
    title = (opp.title or "").lower()
    summary = (opp.summary or "").lower()
    score = 0

    matched: set[str] = set()
    title_hit = False
    desc_hit = False

    for kw in keywords:
        kw_l = kw.lower().strip()
        if not kw_l:
            continue
        if " " in kw_l:
            in_title = kw_l in title
            in_desc = kw_l in summary
        else:
            # word-boundary for single tokens
            in_title = bool(re.search(rf"\b{re.escape(kw_l)}\b", title))
            in_desc = bool(re.search(rf"\b{re.escape(kw_l)}\b", summary))

        if in_title:
            title_hit = True
            matched.add(kw_l)
        if in_desc:
            desc_hit = True
            matched.add(kw_l)

    if title_hit:
        score += 50
    if desc_hit:
        score += 30
    if len(matched) >= 2:
        score += 20

    # Freshness from raw_data.published if available
    pub = (opp.raw_data or {}).get("published")
    if pub:
        try:
            dt = datetime.fromisoformat(str(pub).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if now - dt <= timedelta(hours=24):
                score += 10
        except Exception:
            pass

    return min(100, score)


def python_fast_filter(
    opportunities: List[Opportunity],
    settings: AppSettings,
) -> PythonFilterResult:
    """
    Filter opportunities by keyword score.

    Drops empty titles, and anything below python_filter_threshold.
    """
    keywords = settings.niche_list
    threshold = getattr(settings, "python_filter_threshold", 50)
    now = datetime.now(timezone.utc)

    received = len(opportunities)
    passed: List[Opportunity] = []

    for opp in opportunities:
        # Empty / garbage
        if not (opp.title or "").strip() or len((opp.title or "").strip()) < 15:
            store.update_status(opp.id, ContentStatus.SKIPPED)
            continue

        score = score_opportunity(opp, keywords, now=now)
        opp.raw_data["python_filter_score"] = score

        if score >= threshold:
            passed.append(opp)
        else:
            store.update_status(opp.id, ContentStatus.SKIPPED)

    removed = received - len(passed)
    logger.info(
        "Python Filter | Received: {} | Passed: {} | Removed: {}",
        received,
        len(passed),
        removed,
    )
    return PythonFilterResult(
        passed=passed,
        received=received,
        removed=removed,
    )
