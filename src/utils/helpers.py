"""
General-purpose pure utility functions used across the project.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional
from urllib.parse import urlparse


def utc_now() -> datetime:
    """Return current UTC datetime with timezone info."""
    return datetime.now(timezone.utc)


def generate_content_hash(*parts: str) -> str:
    """
    Create a stable SHA-256 hash from one or more string parts.

    Used for duplicate detection (tweet ID + text, URL, etc.).
    """
    combined = "|".join(p.strip().lower() for p in parts if p)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def clean_text(text: str) -> str:
    """
    Basic text normalization:
    - collapse multiple whitespace
    - strip leading/trailing whitespace
    - remove zero-width characters
    """
    if not text:
        return ""
    # Remove zero-width spaces and similar
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate(text: str, max_length: int = 280, suffix: str = "…") -> str:
    """Truncate text to max_length, adding suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)].rstrip() + suffix


def is_valid_url(url: str) -> bool:
    """Return True if the string looks like a valid HTTP/HTTPS URL."""
    try:
        result = urlparse(url)
        return all([result.scheme in {"http", "https"}, result.netloc])
    except Exception:
        return False


def chunk_list(items: List[Any], size: int) -> Iterable[List[Any]]:
    """Yield successive chunks of the given size."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


def safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dictionaries."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
        if current is default:
            return default
    return current


def format_duration(seconds: float) -> str:
    """Human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"
