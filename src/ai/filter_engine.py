"""
AI relevance filter – Stage 2 Smart Filter.

Supports single and batch evaluation.
Fail-closed: invalid or failed AI responses REJECT the article.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from loguru import logger
from openai import AsyncOpenAI, OpenAIError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.bot.store import Opportunity
from src.config.settings import AppSettings


@dataclass
class FilterResult:
    relevant: bool
    confidence: float
    reason: str
    raw_response: Optional[str] = None


class AIFilterEngine:
    """Classifies whether an opportunity is worth notifying the user about."""

    SYSTEM_PROMPT = """You are a strict content relevance classifier for an AI tools creator on X.

Decide if each article is a valuable X content opportunity for an audience interested in:
AI tools, AI agents, AI automation, digital marketing, creators, SaaS, and online business.

APPROVE only when the article:
- Provides useful, practical information
- Has discussion potential on X
- Can become a valuable X post
- Clearly matches the niche above

REJECT:
- Generic AI opinions or thought pieces
- AI politics, regulation, policy, governance
- AI safety / alignment debates
- Academic papers with no practical product angle
- Unrelated technology or hardware news
- Anything with no practical value for builders, marketers, or creators

Key question:
"Is this a valuable X content opportunity for an audience interested in AI tools, automation, digital marketing, creators, and online business?"

If no → reject.

Respond with valid JSON only. No markdown.

Single-article format:
{
  "relevant": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "One concise sentence"
}

Batch format (when multiple articles are provided):
{
  "results": [
    {"id": "article_id", "relevant": true, "confidence": 0.9, "reason": "..."},
    {"id": "article_id", "relevant": false, "confidence": 0.2, "reason": "..."}
  ]
}
"""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._client: Optional[AsyncOpenAI] = None

        if settings.enable_ai_filter and settings.ai.api_key:
            self._client = AsyncOpenAI(
                api_key=settings.ai.api_key,
                base_url=settings.ai.base_url,
            )
            logger.info(
                "AI Filter Engine initialized | model={} | base_url={}",
                settings.ai.model_filter,
                settings.ai.base_url,
            )
        else:
            logger.warning(
                "AI Filter Engine disabled or missing API key – "
                "articles will pass without AI filtering"
            )

    @property
    def is_ready(self) -> bool:
        return self._client is not None and self.settings.enable_ai_filter

    async def evaluate(self, opportunity: Opportunity) -> FilterResult:
        """Evaluate a single opportunity. Fail-closed on errors."""
        if not self.is_ready:
            return FilterResult(
                relevant=True,
                confidence=0.5,
                reason="AI filter disabled – passing through",
            )
        try:
            return await self._call_single(opportunity)
        except Exception as exc:
            logger.exception("AI filter failed for opp_id={}: {}", opportunity.id, exc)
            return FilterResult(
                relevant=False,
                confidence=0.0,
                reason="AI filtering failed",
            )

    async def evaluate_batch(
        self,
        opportunities: List[Opportunity],
    ) -> Dict[str, FilterResult]:
        """
        Evaluate multiple opportunities in one API call.

        Returns a map of opp_id → FilterResult.
        Any missing or invalid entry is treated as REJECT.
        """
        if not opportunities:
            return {}

        if not self.is_ready:
            return {
                o.id: FilterResult(
                    relevant=True,
                    confidence=0.5,
                    reason="AI filter disabled – passing through",
                )
                for o in opportunities
            }

        try:
            return await self._call_batch(opportunities)
        except Exception as exc:
            logger.exception("AI batch filter failed: {}", exc)
            return {
                o.id: FilterResult(
                    relevant=False,
                    confidence=0.0,
                    reason="AI filtering failed",
                )
                for o in opportunities
            }

    # ------------------------------------------------------------------
    # Internal API calls
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type(OpenAIError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _call_single(self, opportunity: Opportunity) -> FilterResult:
        user_prompt = (
            f"Niche: {', '.join(self.settings.niche_list)}\n\n"
            f"ID: {opportunity.id}\n"
            f"Title: {opportunity.title}\n"
            f"Summary: {opportunity.summary}\n"
            f"URL: {opportunity.url}\n\n"
            "Is this a valuable X content opportunity? JSON only."
        )
        response = await self._client.chat.completions.create(
            model=self.settings.ai.model_filter,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        return self._parse_single(raw)

    @retry(
        retry=retry_if_exception_type(OpenAIError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _call_batch(
        self, opportunities: List[Opportunity]
    ) -> Dict[str, FilterResult]:
        lines = []
        for o in opportunities:
            lines.append(
                f"- id: {o.id}\n"
                f"  title: {o.title}\n"
                f"  summary: {(o.summary or '')[:280]}"
            )
        user_prompt = (
            f"Niche: {', '.join(self.settings.niche_list)}\n\n"
            f"Classify each article. Return JSON with a results array.\n\n"
            + "\n".join(lines)
        )
        response = await self._client.chat.completions.create(
            model=self.settings.ai.model_filter,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=min(2048, 180 * len(opportunities) + 200),
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        return self._parse_batch(raw, opportunities)

    def _parse_single(self, raw: str) -> FilterResult:
        data = self._safe_json(raw)
        if not data or "relevant" not in data:
            logger.warning("Invalid AI response – REJECT: {!r}", raw[:200])
            return FilterResult(
                relevant=False,
                confidence=0.0,
                reason="AI filtering failed",
                raw_response=raw,
            )
        return self._result_from_dict(data, raw)

    def _parse_batch(
        self,
        raw: str,
        opportunities: List[Opportunity],
    ) -> Dict[str, FilterResult]:
        data = self._safe_json(raw)
        out: Dict[str, FilterResult] = {}
        known_ids = {o.id for o in opportunities}

        # Default all to reject; overwrite with valid results
        for o in opportunities:
            out[o.id] = FilterResult(
                relevant=False,
                confidence=0.0,
                reason="AI filtering failed",
                raw_response=raw,
            )

        if not data:
            logger.warning("Invalid AI batch response – all REJECT: {!r}", raw[:200])
            return out

        results = data.get("results")
        if not isinstance(results, list):
            # Maybe single-object style by mistake
            if "relevant" in data and len(opportunities) == 1:
                out[opportunities[0].id] = self._result_from_dict(data, raw)
            else:
                logger.warning("Batch response missing results array – all REJECT")
            return out

        for item in results:
            if not isinstance(item, dict):
                continue
            oid = str(item.get("id", "")).strip()
            if oid not in known_ids:
                continue
            if "relevant" not in item:
                continue
            out[oid] = self._result_from_dict(item, raw)

        return out

    def _result_from_dict(self, data: dict, raw: str) -> FilterResult:
        relevant = bool(data.get("relevant"))
        try:
            confidence = float(data.get("confidence", 0.0))
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = 0.0
            relevant = False
        reason = str(data.get("reason", "")).strip() or "No reason provided"
        return FilterResult(
            relevant=relevant,
            confidence=confidence,
            reason=reason,
            raw_response=raw,
        )

    def _safe_json(self, raw: str) -> Optional[dict]:
        raw = (raw or "").strip()
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
