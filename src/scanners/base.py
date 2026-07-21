"""
Abstract base class for all content scanners.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from src.bot.store import Opportunity


class BaseScanner(ABC):
    """
    Common interface that every scanner (X, Google News, future sources)
    must implement.
    """

    name: str = "base"

    @abstractmethod
    async def scan(self) -> List[Opportunity]:
        """
        Perform a single scan cycle and return newly discovered opportunities.

        Implementations are responsible for:
        - fetching data from the external source
        - basic filtering
        - duplicate prevention
        - converting results into Opportunity objects
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the scanner can reach its upstream service."""
        ...
