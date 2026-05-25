"""Centralized logging configuration module."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from typing import Optional, Final

# Constants for rotating file handler configuration
MAX_LOG_BYTES: Final[int] = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT: Final[int] = 5

# Define the default format string
LOG_FORMAT: Final[str] = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def setup_logging(
    log_file: Optional[str] = None,
    level: int = logging.INFO
) -> None:
    """
    Configures the root logger with a console handler and an optional rotating file handler.

    This function is idempotent; it clears existing handlers from the root logger before
    configuring new ones to prevent duplicate log entries.

    Args:
        log_file: Optional filesystem path for log output. If provided, enables file logging.
        level: The logging level to set (e.g., logging.INFO).
    """
    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    if root_logger.hasHandlers():
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()

    formatter: logging.Formatter = logging.Formatter(LOG_FORMAT)

    # Setup console logging
    console_handler: logging.StreamHandler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Setup optional file logging
    if log_file:
        try:
            file_handler: RotatingFileHandler = RotatingFileHandler(
                log_file,
                maxBytes=MAX_LOG_BYTES,
                backupCount=BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except (OSError, IOError) as exc:
            # Fallback to console if file logging fails
            root_logger.error("Failed to initialize file logging to '%s': %s", log_file, exc)
        except Exception as exc:
            root_logger.error("Unexpected error during logging configuration: %s", exc)

def get_logger(name: str) -> logging.Logger:
    """
    Retrieves a logger instance for a given module.

    Args:
        name: The name of the logger, typically __name__.

    Returns:
        A configured logging.Logger instance.
    """
    return logging.getLogger(name)