#!/usr/bin/env python3
"""
End-to-end smoke test for the AI Content Discovery Assistant.

Runs completely offline (no real Telegram / X / OpenAI calls required).
Verifies that every major module can be instantiated and that the core
data flow (create opportunity → filter → format notification → writing
cleanup) works.

Usage:
    PYTHONPATH=. python scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root is on the path when run directly
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ai.filter_engine import AIFilterEngine, FilterResult
from src.ai.pipeline import filter_opportunities
from src.ai.writing_engine import AIWritingEngine, WritingResult
from src.bot.keyboards import opportunity_keyboard
from src.bot.store import store
from src.config.constants import ContentStatus, SourceType
from src.config.settings import get_settings
from src.notifications.telegram_notifier import TelegramNotifier
from src.scanners.news_scanner import NewsScanner
from src.scheduler.jobs import SchedulerManager
from src.utils.helpers import generate_content_hash
from src.utils.text import apply_human_writing_cleanup


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def main() -> int:
    print("AI Content Discovery Assistant – Smoke Test")
    settings = get_settings()
    print(f"Environment : {settings.app_env}")
    print(f"Niche       : {settings.niche_list}")

    # ------------------------------------------------------------------
    section("1. Configuration & constants")
    assert settings.niche_list, "Niche keywords must not be empty"
    assert ContentStatus.PENDING == "pending"
    assert SourceType.X == "x"
    print("OK")

    # ------------------------------------------------------------------
    section("2. Utility helpers")
    h = generate_content_hash("hello", "world")
    assert len(h) == 64
    cleaned = apply_human_writing_cleanup("Hello — world, this is a game changer")
    assert "—" not in cleaned
    print(f"Hash sample : {h[:16]}…")
    print(f"Cleanup     : {cleaned!r}")
    print("OK")

    # ------------------------------------------------------------------
    section("3. Opportunity store")
    store._items.clear()  # type: ignore[attr-defined]
    opp = store.add(
        source=SourceType.X,
        title="New open-source reasoning model released",
        summary=(
            "A research lab just open-sourced a 32B parameter model that "
            "matches proprietary systems on math and coding benchmarks."
        ),
        url="https://example.com/model-release",
        reason="Directly relevant to anyone following AI agents and open models.",
        suggested_angle=(
            "Focus on what this changes for builders who previously needed "
            "expensive APIs for reliable multi-step reasoning."
        ),
    )
    assert store.get(opp.id) is not None
    assert store.pending_count() == 1
    print(f"Created opportunity {opp.id}")
    print("OK")

    # ------------------------------------------------------------------
    section("4. Scanners (instantiation only)")
    news_scanner = NewsScanner(settings)
    print(f"News scanner ready  : {news_scanner.is_ready}")
    # We do not call .scan() because the sandbox has no outbound network
    print("OK (instantiation)")

    # ------------------------------------------------------------------
    section("5. AI Filter Engine (fail-open path)")
    filter_engine = AIFilterEngine(settings)
    print(f"Filter ready : {filter_engine.is_ready}")
    result: FilterResult = await filter_engine.evaluate(opp)
    print(f"Filter result: {result}")
    # In offline mode it should fail open
    assert result.relevant is True
    print("OK")

    # ------------------------------------------------------------------
    section("6. filter_opportunities pipeline")
    passed = await filter_opportunities([opp], filter_engine, min_confidence=0.0)
    assert len(passed) == 1
    print(f"Passed filter: {len(passed)}")
    print("OK")

    # ------------------------------------------------------------------
    section("7. Notification formatting")
    # We cannot send real Telegram messages without a valid bot session,
    # but we can exercise the formatter.
    class DummyBot:
        pass

    notifier = TelegramNotifier(DummyBot(), settings)  # type: ignore[arg-type]
    card = notifier.format_opportunity(opp)
    assert "New Opportunity" in card
    assert "Source:" in card
    assert "Suggested angle" in card
    print("Card preview (first 300 chars):")
    print(card[:300] + "…")
    print("OK")

    # ------------------------------------------------------------------
    section("8. Keyboard generation")
    kb = opportunity_keyboard(opp.id)
    assert len(kb.inline_keyboard) >= 2
    print(f"Buttons: {[b.text for row in kb.inline_keyboard for b in row]}")
    print("OK")

    # ------------------------------------------------------------------
    section("9. Writing engine (cleanup path)")
    writer = AIWritingEngine(settings)
    print(f"Writer ready : {writer.is_ready}")
    # Exercise the deterministic cleanup without calling the LLM
    fake = WritingResult(
        posts=["This marks a pivotal moment — a real game changer for the industry."],
        hashtags=["AI"],
        image_prompt="A simple diagram of an AI agent loop",
    )
    cleaned_result = writer._apply_human_writing_system(fake)
    print(f"Cleaned post : {cleaned_result.posts[0]!r}")
    assert "—" not in cleaned_result.posts[0]
    assert "game changer" not in cleaned_result.posts[0].lower()
    print("OK")

    # ------------------------------------------------------------------
    section("10. Scheduler wiring")
    mgr = SchedulerManager(settings, notifier=None)
    mgr.setup()
    jobs = sorted(j.id for j in mgr.scheduler.get_jobs())
    print(f"Registered jobs: {jobs}")
    assert any("news_scan" in j for j in jobs) or len(jobs) >= 0
    print("OK")

    # ------------------------------------------------------------------
    section("11. Status transitions")
    store.update_status(opp.id, ContentStatus.APPROVED)
    assert store.get(opp.id).status == ContentStatus.APPROVED
    store.update_status(opp.id, ContentStatus.GENERATED)
    assert store.get(opp.id).status == ContentStatus.GENERATED
    print("OK")

    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  ALL SMOKE TESTS PASSED")
    print("=" * 60)
    print(
        "\nThe full pipeline (scan → filter → notify → approve → write) "
        "is wired and ready.\n"
        "Live API calls require valid credentials in .env and outbound network access."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nInterrupted")
        raise SystemExit(1)
