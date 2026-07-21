"""
Lightweight local preference learning (JSON file, no database).

Tracks account type, angle, tone, image style, and thread acceptance
so the assistant can offer smart defaults after enough history.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from src.config.constants import (
    PREFS_FILENAME,
    PREFS_MIN_GENERATIONS_FOR_SUGGESTIONS,
    PROJECT_ROOT,
)
from src.config.settings import AppSettings


def _prefs_path(settings: AppSettings) -> Path:
    return settings.data_path / PREFS_FILENAME


def load_preferences(settings: AppSettings) -> Dict[str, Any]:
    path = _prefs_path(settings)
    if not path.exists():
        return _empty_prefs()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {**_empty_prefs(), **data}
    except Exception as exc:
        logger.warning("Could not load preferences: {}", exc)
        return _empty_prefs()


def save_preferences(settings: AppSettings, data: Dict[str, Any]) -> None:
    path = _prefs_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _empty_prefs() -> Dict[str, Any]:
    return {
        "preferred_account_type": None,
        "preferred_writing_angle": None,
        "preferred_tone": None,
        "preferred_image_style": None,
        "angle_counts": {},
        "tone_counts": {},
        "account_counts": {},
        "image_style_counts": {},
        "thread_accepted": 0,
        "thread_rejected": 0,
        "total_posts_generated": 0,
        "last_updated": None,
    }


def record_generation(
    settings: AppSettings,
    *,
    account_type: str,
    angle: str,
    tone: str,
    image_style: Optional[str] = None,
    thread_accepted: Optional[bool] = None,
) -> None:
    """Update preference stats after a completed generation."""
    prefs = load_preferences(settings)
    prefs["total_posts_generated"] = prefs.get("total_posts_generated", 0) + 1

    # Counts
    for key, value in (
        ("account_counts", account_type),
        ("angle_counts", angle),
        ("tone_counts", tone),
    ):
        counts = prefs.setdefault(key, {})
        counts[value] = counts.get(value, 0) + 1

    if image_style:
        counts = prefs.setdefault("image_style_counts", {})
        counts[image_style] = counts.get(image_style, 0) + 1

    if thread_accepted is True:
        prefs["thread_accepted"] = prefs.get("thread_accepted", 0) + 1
    elif thread_accepted is False:
        prefs["thread_rejected"] = prefs.get("thread_rejected", 0) + 1

    # Preferred = most frequent
    prefs["preferred_account_type"] = _most_common(prefs.get("account_counts", {}))
    prefs["preferred_writing_angle"] = _most_common(prefs.get("angle_counts", {}))
    prefs["preferred_tone"] = _most_common(prefs.get("tone_counts", {}))
    prefs["preferred_image_style"] = _most_common(prefs.get("image_style_counts", {}))

    save_preferences(settings, prefs)
    logger.debug("Preferences updated | total={}", prefs["total_posts_generated"])


def _most_common(counts: Dict[str, int]) -> Optional[str]:
    if not counts:
        return None
    return max(counts, key=counts.get)


def can_suggest(settings: AppSettings) -> bool:
    prefs = load_preferences(settings)
    return prefs.get("total_posts_generated", 0) >= PREFS_MIN_GENERATIONS_FOR_SUGGESTIONS


def get_suggestions(settings: AppSettings) -> Optional[Dict[str, str]]:
    if not can_suggest(settings):
        return None
    prefs = load_preferences(settings)
    if not all(
        [
            prefs.get("preferred_account_type"),
            prefs.get("preferred_writing_angle"),
            prefs.get("preferred_tone"),
        ]
    ):
        return None
    return {
        "account_type": prefs["preferred_account_type"],
        "angle": prefs["preferred_writing_angle"],
        "tone": prefs["preferred_tone"],
        "image_style": prefs.get("preferred_image_style") or "realistic",
    }


def thread_acceptance_rate(settings: AppSettings) -> float:
    prefs = load_preferences(settings)
    accepted = prefs.get("thread_accepted", 0)
    rejected = prefs.get("thread_rejected", 0)
    total = accepted + rejected
    if total == 0:
        return 0.5  # neutral
    return accepted / total


def reset_preferences(settings: AppSettings) -> None:
    path = _prefs_path(settings)
    if path.exists():
        path.unlink()
    logger.info("User preferences reset")
