"""
AI Writing Engine v2.0 – Authority-Based X Content.

Position: AI Automation Consultant / Digital Marketing Strategist.
Goal: trust, authority, followers, inbound clients — not news reporting.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from loguru import logger
from openai import AsyncOpenAI, OpenAIError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.bot.store import Opportunity
from src.config.constants import (
    ANGLE_LABELS,
    FORBIDDEN_AI_PHRASES,
    FORBIDDEN_CHARACTERS,
    IMAGE_STYLE_LABELS,
    TONE_LABELS,
    AccountType,
    ImageStyle,
    Tone,
    WritingAngle,
)
from src.config.settings import AppSettings
from src.utils.text import apply_human_writing_cleanup


@dataclass
class WritingResult:
    posts: List[str] = field(default_factory=list)
    image_prompt: Optional[str] = None
    hashtags: List[str] = field(default_factory=list)
    is_thread: bool = False
    account_type: str = AccountType.FREE
    angle: str = WritingAngle.EDUCATIONAL
    tone: str = Tone.PROFESSIONAL
    image_style: str = ImageStyle.REALISTIC
    char_counts: List[int] = field(default_factory=list)
    raw_response: Optional[str] = None

    def as_telegram_message(self) -> str:
        if not self.posts:
            return "⚠️ Writing engine returned no content."

        parts: List[str] = []

        # 1. Final X Post
        if self.is_thread or len(self.posts) > 1:
            parts.append(f"<b>🧵 Thread ({len(self.posts)} posts)</b>\n")
            for i, post in enumerate(self.posts, 1):
                cc = self.char_counts[i - 1] if i - 1 < len(self.char_counts) else len(post)
                parts.append(f"<b>{i}/</b> ({cc} chars)\n{post}\n")
        else:
            parts.append("<b>📝 X Post</b>\n")
            parts.append(self.posts[0])
            cc = self.char_counts[0] if self.char_counts else len(self.posts[0])
            # 2. Character count
            if self.account_type == AccountType.FREE:
                parts.append(f"\n\n<b>Characters:</b>\n{cc} / 280")
            else:
                parts.append(f"\n\n<b>Characters:</b>\n{cc:,}")

        # 3. Image prompt
        if self.image_prompt:
            parts.append(
                f"\n\n<b>🖼 Image Prompt</b>\n<code>{self.image_prompt}</code>"
            )

        # 4. Generation summary
        angle_label = ANGLE_LABELS.get(self.angle, self.angle)
        tone_label = TONE_LABELS.get(self.tone, self.tone)
        style_label = IMAGE_STYLE_LABELS.get(self.image_style, self.image_style)
        fmt = "Thread" if (self.is_thread or len(self.posts) > 1) else "Single Post"
        acct = "Free" if self.account_type == AccountType.FREE else "Premium"

        parts.append(
            f"\n\n<b>Generation Summary</b>\n"
            f"Account Type: {acct}\n"
            f"Writing Angle: {angle_label}\n"
            f"Tone: {tone_label}\n"
            f"Format: {fmt}\n"
            f"Image Style: {style_label}"
        )

        parts.append(
            "\n\n<i>Copy the text above and post it yourself. "
            "Nothing is published automatically.</i>"
        )
        return "\n".join(parts)


class AIWritingEngine:
    """Generates native X posts that follow Human Writing + V1.1.3 rules."""

    SYSTEM_PROMPT = """You are an AI Automation Consultant, Digital Marketing Strategist, and Business Growth Advisor who posts on X.

You are NOT a journalist, news site, AI assistant, blogger, or press-release writer.

Your job is to build trust, authority, followers, and inbound clients.
Every post should make readers think:
"This person really understands AI automation and digital marketing."
Eventually: "I'd trust this person to help automate or grow my business."

==================================================
TARGET AUDIENCE
Business owners, entrepreneurs, coaches, agencies, freelancers,
digital marketers, content creators, affiliate marketers, small businesses.
Many are beginners. Avoid unnecessary jargon. Assume they want to grow faster with AI.

==================================================
THE ARTICLE IS CONTEXT, NOT THE CONTENT
Do not rewrite or report the article.
Find the most valuable insight, then explain:
- Why it matters
- Who should care
- What businesses can learn
- What marketers or creators can do
- What opportunity this creates

==================================================
STRUCTURE (natural flow, not labeled headings)
1. Strong hook — stop the scroll. No greetings, no "Today…", no "OpenAI announced…". Lead with the idea.
2. Brief context — mention the news naturally, keep it short.
3. Insight — the core. Teach, challenge assumptions, connect ideas, show expertise.
4. Practical takeaway — answer "So what?" Give something useful.

==================================================
ACCOUNT TYPE
Free: max 280 characters per post, target 180–260. Never exceed 280.
Premium: longer only when it improves the message. No filler. Short paragraphs.

Threads: only when the topic genuinely needs more room (2–5 posts). Each post must add value.

==================================================
STYLE
- Sound like a successful X creator sharing a sharp observation.
- Not LinkedIn, not a blog, not a newspaper.
- Mobile-first: 1–2 line paragraphs, white space, easy scroll.
- First two lines are the strongest.
- Mix short and medium sentences. Have opinions. React. Show curiosity.
- Preserve all names, numbers, companies, products, dates, quotes.

==================================================
BUSINESS POSITIONING
When it fits naturally, connect to:
AI automation, marketing automation, sales funnels, lead generation,
digital marketing, content creation, SEO, ads, affiliate marketing,
workflow automation, productivity, business growth.
Never force a connection that does not exist.

==================================================
NEVER
- Em dashes (—) or en dashes (–)
- AI clichés: game changer, revolutionary, pivotal moment, stands as a testament,
  underscores, delve, leverage, seamless, robust, landscape, realm, next generation,
  cutting edge, industry observers, experts say, some believe, it could potentially,
  while details remain limited
- Openings: Great question, Absolutely, Certainly, Of course
- Closings: In conclusion, To summarize, Let me know, Comment YES, Follow for more

==================================================
VALUE DENSITY
Every sentence must teach, explain, persuade, challenge, inspire, or create curiosity.
Remove anything that adds no value.

==================================================
IMAGE PROMPT
After the post, write one professional image prompt:
- No text inside the image
- High quality, modern, relevant, attention-grabbing
- Subject, scene, style, lighting, mood, composition, X-friendly aspect ratio (1:1 or 16:9)
- Match the requested image style

==================================================
OUTPUT — valid JSON only, no markdown:
{
  "posts": ["post 1", "optional post 2"],
  "image_prompt": "detailed visual prompt",
  "hashtags": []
}

Before returning, silently verify:
- Sounds like an experienced creator?
- Would someone stop scrolling?
- Would a business owner learn something?
- Increases trust / could attract clients?
- Human, no AI clichés, mobile-readable?
- Free account under 280 chars per post?
If any answer is no, rewrite before returning.
Only return the final polished JSON.
"""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._client: Optional[AsyncOpenAI] = None
        if settings.ai.api_key:
            self._client = AsyncOpenAI(
                api_key=settings.ai.api_key,
                base_url=settings.ai.base_url,
            )
            logger.info(
                "AI Writing Engine v2.0 | model={}",
                settings.ai.model_writer,
            )

    @property
    def is_ready(self) -> bool:
        return self._client is not None

    async def generate(
        self,
        opportunity: Opportunity,
        *,
        account_type: str = AccountType.FREE,
        angle: str = WritingAngle.EDUCATIONAL,
        tone: str = Tone.PROFESSIONAL,
        as_thread: bool = False,
        image_style: str = ImageStyle.REALISTIC,
    ) -> WritingResult:
        if not self.is_ready:
            raise RuntimeError(
                "AI Writing Engine is not configured. Set AI_API_KEY in .env"
            )

        result = await self._call_model(
            opportunity,
            account_type=account_type,
            angle=angle,
            tone=tone,
            as_thread=as_thread,
            image_style=image_style,
        )
        result = self._apply_human_writing_system(result, account_type=account_type)
        result = self._silent_quality_check(result, account_type=account_type)
        result.account_type = account_type
        result.angle = angle
        result.tone = tone
        result.image_style = image_style
        result.is_thread = as_thread or len(result.posts) > 1
        result.char_counts = [len(p) for p in result.posts]
        return result

    async def regenerate_image_prompt(
        self,
        opportunity: Opportunity,
        post_text: str,
        image_style: str = ImageStyle.REALISTIC,
    ) -> str:
        if not self.is_ready:
            return "A clean, modern visual related to the topic, no text overlay."

        style_label = IMAGE_STYLE_LABELS.get(image_style, image_style)
        prompt = (
            f"Write only an AI image generation prompt (no other text).\n"
            f"Style: {style_label}\n"
            f"Post:\n{post_text[:500]}\n\n"
            f"Topic: {opportunity.title}\n"
            "Include subject, scene, style, lighting, mood, composition, "
            "and aspect ratio suitable for X (1:1 or 16:9). "
            "No text inside the image. Do not repeat the post wording."
        )
        try:
            response = await self._client.chat.completions.create(
                model=self.settings.ai.model_writer,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You write concise, high-quality image generation prompts "
                            "for social media. No text overlays unless essential."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.9,
                max_tokens=300,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("Image prompt regen failed: {}", exc)
            return (
                "Clean modern visual that complements the post, high quality, "
                "social-media ready, no text overlay."
            )

    async def should_recommend_thread(
        self,
        opportunity: Opportunity,
        account_type: str,
    ) -> bool:
        """Recommend a thread only when the topic genuinely needs more room."""
        summary_len = len(opportunity.summary or "")
        reason_len = len(opportunity.reason or "")
        complexity = summary_len + reason_len
        text = f"{opportunity.title} {opportunity.summary}".lower()
        multi_signals = (
            "how to",
            "steps",
            "reasons",
            "ways",
            "guide",
            "breakdown",
            "explained",
            "vs ",
            "versus",
            "comparison",
        )
        if any(s in text for s in multi_signals) and complexity > 220:
            return True
        if account_type == AccountType.FREE and complexity > 400:
            return True
        if complexity > 600:
            return True
        return False

    async def rewrite_angle(self, opportunity: Opportunity) -> str:
        if not self.is_ready:
            return (
                "Focus on what this means for people who build or use AI tools "
                "every day, and end with a clear question."
            )
        prompt = (
            f"Niche: {', '.join(self.settings.niche_list)}\n"
            f"Title: {opportunity.title}\n"
            f"Summary: {opportunity.summary}\n"
            f"Current angle: {opportunity.suggested_angle}\n\n"
            "Write one new, distinct suggested angle (2–3 sentences) for an X post. "
            "Be concrete. No JSON. No em dashes."
        )
        try:
            response = await self._client.chat.completions.create(
                model=self.settings.ai.model_writer,
                messages=[
                    {
                        "role": "system",
                        "content": "You write short concrete content angles for X. No em dashes.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=200,
            )
            text = (response.choices[0].message.content or "").strip()
            return apply_human_writing_cleanup(text) or opportunity.suggested_angle
        except Exception as exc:
            logger.warning("Angle rewrite failed: {}", exc)
            return opportunity.suggested_angle

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type(OpenAIError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _call_model(
        self,
        opportunity: Opportunity,
        *,
        account_type: str,
        angle: str,
        tone: str,
        as_thread: bool,
        image_style: str,
    ) -> WritingResult:
        user_prompt = self._build_user_prompt(
            opportunity,
            account_type=account_type,
            angle=angle,
            tone=tone,
            as_thread=as_thread,
            image_style=image_style,
        )
        response = await self._client.chat.completions.create(
            model=self.settings.ai.model_writer,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.settings.ai.temperature,
            max_tokens=self.settings.ai.max_tokens,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        return self._parse_response(raw)

    def _build_user_prompt(
        self,
        opportunity: Opportunity,
        *,
        account_type: str,
        angle: str,
        tone: str,
        as_thread: bool,
        image_style: str,
    ) -> str:
        niche = ", ".join(self.settings.niche_list)
        fmt = "thread (2–5 posts)" if as_thread else "single post"
        if account_type == AccountType.FREE:
            limit = "FREE ACCOUNT: max 280 characters per post, prefer 180–260"
        else:
            limit = "PREMIUM ACCOUNT: longer form allowed only when it adds real value"
        return (
            f"Niche audience: {niche}\n\n"
            f"Source: {opportunity.source}\n"
            f"Topic: {opportunity.title}\n"
            f"Summary: {opportunity.summary}\n"
            f"Why it matters: {opportunity.reason}\n"
            f"Angle context: {opportunity.suggested_angle}\n"
            f"Matched keyword: {opportunity.matched_keyword}\n"
            f"URL: {opportunity.url}\n\n"
            f"{limit}\n"
            f"Writing angle: {angle}\n"
            f"Tone: {tone}\n"
            f"Format: {fmt}\n"
            f"Image style: {image_style}\n\n"
            "Write as an AI automation and digital marketing consultant. "
            "The article is context only — extract the insight, explain why it matters "
            "for business owners and marketers, and give a practical takeaway. "
            "Do not report the news. Build authority. Return JSON only."
        )

    def _parse_response(self, raw: str) -> WritingResult:
        raw = raw.strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return WritingResult(posts=[raw[:280]], raw_response=raw)
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return WritingResult(posts=[raw[:280]], raw_response=raw)

        posts = data.get("posts") or []
        if isinstance(posts, str):
            posts = [posts]
        posts = [str(p).strip() for p in posts if str(p).strip()]

        hashtags = data.get("hashtags") or []
        if isinstance(hashtags, str):
            hashtags = [hashtags]
        hashtags = [str(h).lstrip("#").strip() for h in hashtags if str(h).strip()]

        image_prompt = data.get("image_prompt")
        if image_prompt is not None:
            image_prompt = str(image_prompt).strip() or None

        return WritingResult(
            posts=posts,
            hashtags=hashtags,
            image_prompt=image_prompt,
            raw_response=raw,
        )

    def _apply_human_writing_system(
        self,
        result: WritingResult,
        *,
        account_type: str,
    ) -> WritingResult:
        cleaned: List[str] = []
        max_len = 280 if account_type == AccountType.FREE else 4000

        for post in result.posts:
            text = apply_human_writing_cleanup(post)
            for ch in FORBIDDEN_CHARACTERS:
                text = text.replace(ch, ", " if ch in ("—", "–") else "-")
            for phrase in FORBIDDEN_AI_PHRASES:
                if phrase.lower() in text.lower():
                    pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                    text = pattern.sub("", text)
            # Extra banned stems from V1.1.3
            for phrase in (
                "revolutionary",
                "in conclusion",
                "let me know what you think",
                "thanks for reading",
                "great question",
            ):
                pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                text = pattern.sub("", text)
            text = re.sub(r"\s{2,}", " ", text)
            text = re.sub(r"\s+,", ",", text)
            text = re.sub(r",\s*,", ",", text)
            text = text.strip(" ,.")
            if len(text) > max_len:
                # Soft trim at last space before limit
                cut = text[: max_len - 1]
                if " " in cut:
                    cut = cut.rsplit(" ", 1)[0]
                text = cut.rstrip(" ,.;:") + "…"
            cleaned.append(text)

        result.posts = cleaned
        if result.image_prompt:
            result.image_prompt = result.image_prompt.replace("—", ", ").replace("–", "-")
        return result

    def _silent_quality_check(
        self,
        result: WritingResult,
        *,
        account_type: str,
    ) -> WritingResult:
        """
        Final deterministic checks. Never shown to the user.
        Enforces free-account limits and strips leftover AI tells.
        """
        max_len = 280 if account_type == AccountType.FREE else 4000
        fixed: List[str] = []
        for post in result.posts:
            text = post
            # Collapse accidental multi-blank lines into single breaks
            text = re.sub(r"\n{3,}", "\n\n", text)
            if len(text) > max_len:
                cut = text[: max_len - 1]
                if " " in cut:
                    cut = cut.rsplit(" ", 1)[0]
                text = cut.rstrip(" ,.;:") + "…"
            fixed.append(text)
        result.posts = fixed
        result.char_counts = [len(p) for p in fixed]
        return result
