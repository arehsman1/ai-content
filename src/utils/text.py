"""
Text processing helpers, including early support for the Human Writing System.
"""

from __future__ import annotations

import re
from typing import List

from src.config.constants import FORBIDDEN_AI_PHRASES, FORBIDDEN_CHARACTERS


def remove_em_dashes(text: str) -> str:
    """Replace em dashes and en dashes with commas or periods as appropriate."""
    # Simple replacement strategy – more sophisticated logic can be added later
    text = text.replace("—", ", ")
    text = text.replace("–", "-")
    # Clean up any double spaces, awkward punctuation, or spaces around commas
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",\s+", ", ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def contains_forbidden_phrase(text: str) -> List[str]:
    """
    Return a list of forbidden AI phrases found in the text (case-insensitive).
    """
    lower = text.lower()
    found = []
    for phrase in FORBIDDEN_AI_PHRASES:
        if phrase.lower() in lower:
            found.append(phrase)
    return found


def contains_forbidden_characters(text: str) -> List[str]:
    """Return a list of forbidden characters present in the text."""
    return [ch for ch in FORBIDDEN_CHARACTERS if ch in text]


def apply_human_writing_cleanup(text: str) -> str:
    """
    Apply the most basic Human Writing System rules that can be done
    with pure string operations (no LLM required).

    Later phases will expand this with full LLM-based rewriting.
    """
    cleaned = remove_em_dashes(text)
    # Future: more rules can be added here
    return cleaned.strip()


def estimate_reading_time(text: str, words_per_minute: int = 200) -> int:
    """Rough estimate of reading time in minutes."""
    words = len(text.split())
    return max(1, round(words / words_per_minute))
