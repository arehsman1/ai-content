"""
Immutable project-wide constants.
"""

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent

DEFAULT_LOG_DIR: str = "logs"
DEFAULT_DATA_DIR: str = "data"

APP_VERSION: str = "1.3.0"
APP_DESCRIPTION: str = (
    "AI Content Discovery Assistant – finds content opportunities "
    "and guides you through creating native X posts."
)

TELEGRAM_MAX_MESSAGE_LENGTH: int = 4096
TELEGRAM_CALLBACK_DATA_MAX_LENGTH: int = 64


class ContentStatus:
    PENDING = "pending"       # 🆕 New
    WRITING = "writing"       # ✍ Writing
    COMPLETED = "completed"   # ✅ Post Ready
    SKIPPED = "skipped"       # ⏭ Skipped
    POSTED = "posted"         # 📌 Posted
    # legacy aliases
    APPROVED = "writing"
    REWRITTEN = "writing"
    GENERATED = "completed"


STATUS_LABELS = {
    ContentStatus.PENDING: "🆕 New Opportunity",
    ContentStatus.WRITING: "✍ Writing...",
    ContentStatus.COMPLETED: "✅ Post Ready",
    ContentStatus.SKIPPED: "⏭ Skipped",
    ContentStatus.POSTED: "📌 Posted",
}


class SourceType:
    X = "x"
    GOOGLE_NEWS = "google_news"


class AccountType:
    FREE = "free"
    PREMIUM = "premium"


class WritingAngle:
    HOT_TAKE = "hot_take"
    EDUCATIONAL = "educational"
    STORYTELLING = "storytelling"
    DATA_DRIVEN = "data_driven"
    PROFESSIONAL = "professional"
    QUICK_TIP = "quick_tip"


ANGLE_LABELS = {
    WritingAngle.HOT_TAKE: "🔥 Hot Take",
    WritingAngle.EDUCATIONAL: "📚 Educational",
    WritingAngle.STORYTELLING: "📖 Storytelling",
    WritingAngle.DATA_DRIVEN: "📊 Data Driven",
    WritingAngle.PROFESSIONAL: "💼 Professional",
    WritingAngle.QUICK_TIP: "⚡ Quick Tip",
}


class Tone:
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    BOLD = "bold"
    CURIOUS = "curious"
    OPINIONATED = "opinionated"
    INSPIRATIONAL = "inspirational"


TONE_LABELS = {
    Tone.PROFESSIONAL: "Professional",
    Tone.CASUAL: "Casual",
    Tone.BOLD: "Bold",
    Tone.CURIOUS: "Curious",
    Tone.OPINIONATED: "Opinionated",
    Tone.INSPIRATIONAL: "Inspirational",
}


class ImageStyle:
    REALISTIC = "realistic"
    ILLUSTRATION = "illustration"
    RENDER_3D = "3d_render"
    NEWS_GRAPHIC = "news_graphic"
    FUTURISTIC = "futuristic"
    MINIMALIST = "minimalist"


IMAGE_STYLE_LABELS = {
    ImageStyle.REALISTIC: "📸 Realistic",
    ImageStyle.ILLUSTRATION: "🎨 Illustration",
    ImageStyle.RENDER_3D: "💻 3D Render",
    ImageStyle.NEWS_GRAPHIC: "📰 News Graphic",
    ImageStyle.FUTURISTIC: "🚀 Futuristic",
    ImageStyle.MINIMALIST: "✨ Minimalist",
}


FORBIDDEN_AI_PHRASES: tuple[str, ...] = (
    "marks a pivotal moment",
    "stands as a testament",
    "underscores the importance",
    "game changer",
    "revolutionary breakthrough",
    "next generation",
    "cutting edge",
    "tapestry",
    "landscape",
    "realm",
    "delve",
    "boast",
    "testament",
    "underscore",
    "foster",
    "leverage",
    "seamless",
    "robust",
    "revolutionary",
    "in conclusion",
    "experts say",
)

FORBIDDEN_CHARACTERS: tuple[str, ...] = (
    "—",
    "–",
)

LOG_ROTATION: str = "10 MB"
LOG_RETENTION: str = "30 days"
LOG_FORMAT: str = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

PREFS_FILENAME: str = "user_preferences.json"
PREFS_MIN_GENERATIONS_FOR_SUGGESTIONS: int = 10
