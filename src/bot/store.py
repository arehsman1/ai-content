"""
In-memory store for opportunities – lifecycle-aware task cards.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from src.config.constants import STATUS_LABELS, ContentStatus


@dataclass
class Opportunity:
    id: str
    source: str
    title: str
    summary: str
    url: str
    reason: str
    suggested_angle: str
    status: str = ContentStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_data: dict = field(default_factory=dict)
    matched_keyword: str = ""
    score: float = 0.0

    # Telegram message binding (single-card lifecycle)
    chat_id: Optional[int] = None
    message_id: Optional[int] = None

    # Writing workflow context
    writing_step: str = ""
    account_type: str = ""
    angle: str = ""
    tone: str = ""
    as_thread: bool = False
    image_style: str = ""

    # Generated content
    generated_posts: List[str] = field(default_factory=list)
    image_prompt: str = ""
    char_counts: List[int] = field(default_factory=list)
    posted_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Card renderers – always one message, status at top
    # ------------------------------------------------------------------

    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    def to_message_text(self) -> str:
        """Default card for PENDING / New state."""
        return self.render_new()

    def render_new(self) -> str:
        source_label = {
            "x": "X (Twitter)",
            "google_news": "Google News",
        }.get(self.source, self.source)
        score_str = f"{self.score:.0%}" if self.score else "N/A"
        keyword_str = self.matched_keyword or "—"
        freshness = self._freshness_line()

        return (
            f"<b>Status:</b>\n{self.status_label()}\n\n"
            f"<b>Source:</b> {source_label}\n"
            f"<b>Topic:</b> {self.title}\n"
            f"{freshness}"
            f"<b>Summary</b>\n{self.summary}\n\n"
            f"<b>Why it matters</b>\n{self.reason}\n\n"
            f"<b>Matched keyword:</b> {keyword_str}\n"
            f"<b>Opportunity score:</b> {score_str}\n\n"
            f"<b>Suggested angle</b>\n{self.suggested_angle}\n\n"
            f"<i>ID: {self.id}</i>"
        )

    def render_writing(self, step: str = "", percent: int = 0, task: str = "") -> str:
        bar = _progress_bar(percent)
        step_line = step or self.writing_step or "Working…"
        task_line = task or ""
        extra = f"\n\n{bar} {percent}%" if percent else ""
        task_block = f"\n\n<b>Current Task:</b>\n{task_line}" if task_line else ""
        return (
            f"<b>Status:</b>\n{STATUS_LABELS[ContentStatus.WRITING]}\n\n"
            f"<b>Topic:</b> {self.title}\n\n"
            f"<b>Current Step:</b>\n{step_line}"
            f"{extra}{task_block}\n\n"
            f"<i>ID: {self.id}</i>"
        )

    def render_completed(self) -> str:
        posts = self.generated_posts or []
        if not posts:
            body = "<i>No post content.</i>"
            char_line = ""
        elif len(posts) == 1:
            body = posts[0]
            cc = self.char_counts[0] if self.char_counts else len(posts[0])
            if self.account_type == "free":
                char_line = f"\n\n<b>Characters:</b>\n{cc} / 280"
            else:
                char_line = f"\n\n<b>Characters:</b>\n{cc:,}"
        else:
            parts = []
            for i, p in enumerate(posts, 1):
                cc = self.char_counts[i - 1] if i - 1 < len(self.char_counts) else len(p)
                parts.append(f"<b>{i}/</b> ({cc} chars)\n{p}")
            body = "\n\n".join(parts)
            char_line = f"\n\n<b>Thread:</b> {len(posts)} posts"

        img = ""
        if self.image_prompt:
            img = f"\n\n<b>Image Prompt:</b>\n<code>{self.image_prompt}</code>"

        return (
            f"<b>Status:</b>\n{STATUS_LABELS[ContentStatus.COMPLETED]}\n\n"
            f"<b>Headline:</b>\n{self.title}\n\n"
            f"<b>Generated Post:</b>\n{body}"
            f"{char_line}{img}\n\n"
            f"<i>ID: {self.id}</i>"
        )

    def render_skipped(self) -> str:
        return (
            f"<b>Status:</b>\n{STATUS_LABELS[ContentStatus.SKIPPED]}\n\n"
            f"<b>Topic:</b> {self.title}\n\n"
            f"<i>ID: {self.id}</i>"
        )

    def render_posted(self) -> str:
        when = "—"
        if self.posted_at:
            when = self.posted_at.strftime("%Y-%m-%d\n%H:%M UTC")
        posts = self.generated_posts or []
        preview = posts[0][:200] + ("…" if posts and len(posts[0]) > 200 else "") if posts else ""
        return (
            f"<b>Status:</b>\n{STATUS_LABELS[ContentStatus.POSTED]}\n\n"
            f"<b>Topic:</b> {self.title}\n\n"
            f"<b>Posted:</b>\n{when}\n\n"
            f"{preview}\n\n"
            f"<i>ID: {self.id}</i>"
        )

    def _freshness_line(self) -> str:
        pub = (self.raw_data or {}).get("published")
        if not pub:
            return "\n"
        try:
            dt = datetime.fromisoformat(str(pub).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            hours = int((datetime.now(timezone.utc) - dt).total_seconds() // 3600)
            if hours < 1:
                s = "Published: just now"
            elif hours < 24:
                s = f"Published: {hours} hour{'s' if hours != 1 else ''} ago"
            else:
                days = hours // 24
                s = f"Published: {days} day{'s' if days != 1 else ''} ago"
            return f"\n<b>{s}</b>\n"
        except Exception:
            return "\n"


def _progress_bar(percent: int, width: int = 10) -> str:
    pct = max(0, min(100, int(percent)))
    filled = max(0, min(width, round(pct / 100 * width)))
    return "█" * filled + "░" * (width - filled)


class OpportunityStore:
    def __init__(self) -> None:
        self._items: Dict[str, Opportunity] = {}
        self._notified_hashes: Dict[str, datetime] = {}
        self.last_scan_at: Optional[datetime] = None
        self.last_scan_stats: dict = {}

    def add(
        self,
        source: str,
        title: str,
        summary: str,
        url: str,
        reason: str,
        suggested_angle: str,
        raw_data: Optional[dict] = None,
        matched_keyword: str = "",
        score: float = 0.0,
    ) -> Opportunity:
        opp_id = uuid.uuid4().hex[:12]
        opp = Opportunity(
            id=opp_id,
            source=source,
            title=title,
            summary=summary,
            url=url,
            reason=reason,
            suggested_angle=suggested_angle,
            raw_data=raw_data or {},
            matched_keyword=matched_keyword,
            score=score,
        )
        self._items[opp_id] = opp
        return opp

    def get(self, opp_id: str) -> Optional[Opportunity]:
        return self._items.get(opp_id)

    def update_status(self, opp_id: str, status: str) -> bool:
        opp = self._items.get(opp_id)
        if not opp:
            return False
        opp.status = status
        return True

    def bind_message(self, opp_id: str, chat_id: int, message_id: int) -> None:
        opp = self._items.get(opp_id)
        if opp:
            opp.chat_id = chat_id
            opp.message_id = message_id

    def list_by_status(self, status: str) -> List[Opportunity]:
        return [o for o in self._items.values() if o.status == status]

    def pending_count(self) -> int:
        return len(self.list_by_status(ContentStatus.PENDING))

    def all(self) -> List[Opportunity]:
        return list(self._items.values())

    def delete(self, opp_id: str) -> bool:
        return self._items.pop(opp_id, None) is not None

    def was_recently_notified(self, content_hash: str, window_hours: int = 24) -> bool:
        ts = self._notified_hashes.get(content_hash)
        if not ts:
            return False
        if datetime.now(timezone.utc) - ts > timedelta(hours=window_hours):
            del self._notified_hashes[content_hash]
            return False
        return True

    def mark_notified(self, content_hash: str) -> None:
        self._notified_hashes[content_hash] = datetime.now(timezone.utc)

    def cleanup_old_hashes(self, window_hours: int = 24) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        expired = [h for h, ts in self._notified_hashes.items() if ts < cutoff]
        for h in expired:
            del self._notified_hashes[h]
        return len(expired)


store = OpportunityStore()
