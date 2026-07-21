"""
Hybrid filtering pipeline:

  Google News articles
       ↓
  Stage 1: Python Fast Filter
       ↓
  Stage 2: AI Smart Filter (batched)
       ↓
  High-quality opportunities only
"""

from __future__ import annotations

import time
from typing import Awaitable, Callable, List, Optional

from loguru import logger

from src.ai.filter_engine import AIFilterEngine, FilterResult
from src.ai.python_filter import python_fast_filter
from src.bot.store import Opportunity, store
from src.config.constants import ContentStatus
from src.config.settings import AppSettings

ProgressCallback = Callable[..., Awaitable[None]]


async def hybrid_filter(
    opportunities: List[Opportunity],
    settings: AppSettings,
    filter_engine: AIFilterEngine,
    *,
    min_confidence: float = 0.55,
    progress: Optional[ProgressCallback] = None,
) -> List[Opportunity]:
    """
    Run Stage 1 (Python) then Stage 2 (AI batch).

    progress callbacks:
      stage="python", received=..., passed=..., removed=..., percent=...
      stage="ai", total=..., analyzed=..., passed=..., rejected=...,
                  current_title=..., eta_text=..., percent=...
    """
    if not opportunities:
        return []

    # ---------- Stage 1: Python Fast Filter ----------
    if progress:
        await progress(
            stage="python",
            received=len(opportunities),
            passed=0,
            removed=0,
            percent=10,
        )

    py = python_fast_filter(opportunities, settings)

    if progress:
        await progress(
            stage="python",
            received=py.received,
            passed=len(py.passed),
            removed=py.removed,
            percent=100,
        )

    logger.info(
        "Python Filter: Received: {} | Passed: {} | Removed: {}",
        py.received,
        len(py.passed),
        py.removed,
    )

    if not py.passed:
        return []

    # ---------- Stage 2: AI Smart Filter (batched) ----------
    if not filter_engine.is_ready:
        logger.info(
            "AI filter not ready – returning {} Python-passed articles unfiltered",
            len(py.passed),
        )
        for opp in py.passed:
            opp.score = 0.5
        return py.passed

    batch_size = getattr(settings, "ai_filter_batch_size", 10)
    candidates = py.passed
    total = len(candidates)
    passed: List[Opportunity] = []
    rejected_count = 0
    analyzed = 0
    start = time.monotonic()

    for batch_start in range(0, total, batch_size):
        batch = candidates[batch_start : batch_start + batch_size]
        current_title = batch[0].title if batch else ""

        if progress:
            elapsed = time.monotonic() - start
            eta = _estimate_eta(elapsed, analyzed, total)
            await progress(
                stage="ai",
                total=total,
                analyzed=analyzed,
                passed=len(passed),
                rejected=rejected_count,
                current_title=current_title,
                eta_text=eta,
                percent=int(analyzed / total * 100) if total else 100,
            )

        results = await filter_engine.evaluate_batch(batch)

        for opp in batch:
            result: FilterResult = results.get(
                opp.id,
                FilterResult(
                    relevant=False,
                    confidence=0.0,
                    reason="AI filtering failed",
                ),
            )
            analyzed += 1

            logger.info(
                "AI filter | opp_id={} | {} | confidence={:.2f} | reason={}",
                opp.id,
                "PASS" if result.relevant else "REJECT",
                result.confidence,
                result.reason,
            )

            opp.score = result.confidence
            opp.raw_data["ai_filter"] = {
                "relevant": result.relevant,
                "confidence": result.confidence,
                "reason": result.reason,
            }

            if result.relevant and result.confidence >= min_confidence:
                passed.append(opp)
            else:
                rejected_count += 1
                store.update_status(opp.id, ContentStatus.SKIPPED)

        if progress:
            elapsed = time.monotonic() - start
            eta = _estimate_eta(elapsed, analyzed, total)
            title = batch[-1].title if batch else ""
            await progress(
                stage="ai",
                total=total,
                analyzed=analyzed,
                passed=len(passed),
                rejected=rejected_count,
                current_title=title,
                eta_text=eta,
                percent=min(100, int(analyzed / total * 100)) if total else 100,
            )

    logger.info(
        "AI Filter summary | input={} | passed={} | rejected={}",
        total,
        len(passed),
        rejected_count,
    )
    return passed


# Backwards-compatible name used by older call sites
async def filter_opportunities(
    opportunities: List[Opportunity],
    filter_engine: AIFilterEngine,
    min_confidence: float = 0.55,
    progress: Optional[ProgressCallback] = None,
    settings: Optional[AppSettings] = None,
) -> List[Opportunity]:
    """
    Compatibility wrapper.

    Prefer hybrid_filter() for new code. If settings is provided,
    runs the full hybrid pipeline; otherwise falls back to AI-only
    (legacy behaviour for callers that only have the engine).
    """
    if settings is not None:
        return await hybrid_filter(
            opportunities,
            settings,
            filter_engine,
            min_confidence=min_confidence,
            progress=progress,
        )

    # Legacy AI-only path (still fail-closed via engine)
    if not opportunities:
        return []
    if not filter_engine.is_ready:
        for opp in opportunities:
            opp.score = 0.5
        return opportunities

    passed: List[Opportunity] = []
    rejected = 0
    total = len(opportunities)
    for idx, opp in enumerate(opportunities):
        if progress:
            await progress(
                stage="ai",
                total=total,
                analyzed=idx,
                passed=len(passed),
                rejected=rejected,
                current_title=opp.title,
                eta_text="",
                percent=int(idx / total * 100) if total else 0,
            )
        result = await filter_engine.evaluate(opp)
        opp.score = result.confidence
        opp.raw_data["ai_filter"] = {
            "relevant": result.relevant,
            "confidence": result.confidence,
            "reason": result.reason,
        }
        if result.relevant and result.confidence >= min_confidence:
            passed.append(opp)
        else:
            rejected += 1
            store.update_status(opp.id, ContentStatus.SKIPPED)
    return passed


def _estimate_eta(elapsed: float, done: int, total: int) -> str:
    if done <= 0 or total <= done:
        return "almost done" if done >= total else "calculating…"
    rate = elapsed / done
    remaining = (total - done) * rate
    if remaining < 60:
        secs = max(1, int(remaining))
        return f"{secs} second{'s' if secs != 1 else ''}"
    mins = max(1, int(round(remaining / 60)))
    return f"{mins} minute{'s' if mins != 1 else ''}"
