"""
Application configuration loaded from environment variables.

Uses pydantic-settings for type-safe validation and clear error messages
when required values are missing.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config.constants import DEFAULT_DATA_DIR, DEFAULT_LOG_DIR, PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env", override=False)


class TelegramSettings(BaseSettings):
    """Telegram bot configuration."""

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_", extra="ignore")

    bot_token: str = Field(..., description="Telegram Bot API token")
    allowed_user_ids: str = Field(
        ...,
        description="Comma-separated list of allowed Telegram user IDs",
    )

    @property
    def allowed_ids(self) -> List[int]:
        if not self.allowed_user_ids.strip():
            return []
        return [int(uid.strip()) for uid in self.allowed_user_ids.split(",") if uid.strip()]


class AISettings(BaseSettings):
    """AI provider configuration (OpenAI-compatible)."""

    model_config = SettingsConfigDict(env_prefix="AI_", extra="ignore")

    api_key: str = Field(..., description="AI provider API key")
    base_url: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for the AI provider (OpenAI, xAI, Azure, etc.)",
    )
    model_filter: str = Field(
        default="gpt-4o-mini",
        description="Model used for niche relevance filtering",
    )
    model_writer: str = Field(
        default="gpt-4o",
        description="Model used for post generation",
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=64, le=8192)


class NewsSettings(BaseSettings):
    """Google News scanner configuration."""

    model_config = SettingsConfigDict(env_prefix="NEWS_", extra="ignore")

    language: str = Field(default="en", description="News language code")
    country: str = Field(default="US", description="News country code")
    # How many days of articles to consider (default 3 = 72 hours)
    search_window_days: int = Field(default=3, ge=1, le=14)


class AppSettings(BaseSettings):
    """Top-level application settings."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = Field(default="development", description="Environment name")
    app_name: str = Field(
        default="AI Content Discovery Assistant",
        description="Human-readable application name",
    )
    log_level: str = Field(default="INFO", description="Logging level")
    log_dir: str = Field(default=DEFAULT_LOG_DIR, description="Directory for log files")
    data_dir: str = Field(default=DEFAULT_DATA_DIR, description="Directory for database and cache")
    database_url: str = Field(
        default="sqlite+aiosqlite:///data/app.db",
        description="SQLAlchemy database URL",
    )

    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    ai: AISettings = Field(default_factory=AISettings)
    news: NewsSettings = Field(default_factory=NewsSettings)

    niche_keywords: str = Field(
        default="AI,AI tools,AI agents,AI automation,AI software,ChatGPT,OpenAI,Claude AI,Gemini AI,Grok,generative AI,LLM,prompt engineering,AI productivity,AI workflow,automation tools,marketing automation,digital marketing,content creation,content automation,creator tools,SEO,lead generation,SaaS,n8n,Zapier,Make",
        description="Comma-separated niche keywords",
    )
    max_results_per_scan: int = Field(default=20, ge=1, le=100)

    # Automatic scan times (24h clock, comma-separated HH:MM)
    # Default: 00:00, 06:00, 12:00, 18:00  →  4 times per day
    auto_scan_times: str = Field(
        default="00:00,06:00,12:00,18:00",
        description="Comma-separated HH:MM times for automatic Google News scans",
    )

    enable_news_scanner: bool = Field(default=True)
    enable_ai_filter: bool = Field(default=True)
    # Stage-1 Python fast filter: min score (0-100) to send to AI
    python_filter_threshold: int = Field(default=50, ge=0, le=100)
    # AI batch size for stage-2 filtering
    ai_filter_batch_size: int = Field(default=10, ge=1, le=25)

    # How long (hours) to remember a sent opportunity for duplicate prevention
    dedup_window_hours: int = Field(default=24, ge=1, le=168)

    @property
    def niche_list(self) -> List[str]:
        return [kw.strip() for kw in self.niche_keywords.split(",") if kw.strip()]

    @property
    def scan_times_list(self) -> List[str]:
        """Return cleaned list of HH:MM strings."""
        return [t.strip() for t in self.auto_scan_times.split(",") if t.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def log_path(self) -> Path:
        path = Path(self.log_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def data_path(self) -> Path:
        path = Path(self.data_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper

    @model_validator(mode="after")
    def ensure_directories_exist(self) -> "AppSettings":
        self.log_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)
        return self


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
