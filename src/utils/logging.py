"""
Centralized logging configuration using loguru.

Provides a single setup function that configures console + rotating file handlers.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from src.config.constants import LOG_FORMAT, LOG_RETENTION, LOG_ROTATION
from src.config.settings import AppSettings


def setup_logging(settings: AppSettings) -> None:
    """
    Configure loguru with console and rotating file output.

    Args:
        settings: Application settings containing log_level and log_path.
    """
    # Remove default handler
    logger.remove()

    # Console handler (colored, human-friendly)
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=LOG_FORMAT,
        colorize=True,
        backtrace=True,
        diagnose=not settings.is_production,  # hide internal frames in production
    )

    # Rotating file handler
    log_file: Path = settings.log_path / "app.log"
    logger.add(
        str(log_file),
        level=settings.log_level,
        format=LOG_FORMAT,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression="zip",
        enqueue=True,  # thread/process safe
        backtrace=True,
        diagnose=not settings.is_production,
    )

    # Separate error log for quicker troubleshooting
    error_log_file: Path = settings.log_path / "error.log"
    logger.add(
        str(error_log_file),
        level="ERROR",
        format=LOG_FORMAT,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

    logger.info(
        "Logging initialized | level={} | env={} | log_dir={}",
        settings.log_level,
        settings.app_env,
        settings.log_path,
    )


def get_logger(name: str | None = None):
    """
    Convenience wrapper that returns a loguru logger bound to a module name.

    Usage:
        from src.utils.logging import get_logger
        log = get_logger(__name__)
        log.info("Hello")
    """
    if name:
        return logger.bind(name=name)
    return logger
