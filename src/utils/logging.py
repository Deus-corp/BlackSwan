"""Centralized logging configuration helpers."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final, Optional

MAX_LOG_BYTES: Final[int] = 10 * 1024 * 1024
BACKUP_COUNT: Final[int] = 5
LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    log_file: Optional[str | Path] = None,
    level: int | str = logging.INFO,
    *,
    reset: bool = True,
    max_bytes: int = MAX_LOG_BYTES,
    backup_count: int = BACKUP_COUNT,
) -> None:
    """Configure root logger with console and optional rotating file handler."""
    root_logger = logging.getLogger()
    resolved_level = _resolve_level(level)
    root_logger.setLevel(resolved_level)

    if reset:
        _clear_handlers(root_logger)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    if not _has_handler(root_logger, logging.StreamHandler):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(resolved_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if log_file:
        try:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)

            if not _has_file_handler(root_logger, path):
                file_handler = RotatingFileHandler(
                    path,
                    maxBytes=max(1, int(max_bytes)),
                    backupCount=max(0, int(backup_count)),
                    encoding="utf-8",
                )
                file_handler.setLevel(resolved_level)
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)

        except Exception as exc:
            root_logger.error("Failed to initialize file logging to %r: %s", str(log_file), exc)

    _configure_noisy_loggers()


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(str(name or __name__))


def _resolve_level(level: int | str) -> int:
    if isinstance(level, int):
        return level

    env_level = os.getenv("LOG_LEVEL", "")
    raw_level = str(level or env_level or "INFO").strip().upper()

    if raw_level.isdigit():
        return int(raw_level)

    return int(getattr(logging, raw_level, logging.INFO))


def _clear_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass


def _has_handler(logger: logging.Logger, handler_type: type[logging.Handler]) -> bool:
    return any(isinstance(handler, handler_type) for handler in logger.handlers)


def _has_file_handler(logger: logging.Logger, path: Path) -> bool:
    target = str(path.resolve())
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            try:
                if str(Path(handler.baseFilename).resolve()) == target:
                    return True
            except Exception:
                continue
    return False


def _configure_noisy_loggers() -> None:
    for name in (
        "urllib3",
        "web3",
        "asyncio",
        "aiohttp.access",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)