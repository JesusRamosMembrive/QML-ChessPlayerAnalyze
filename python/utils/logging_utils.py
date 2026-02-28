"""
Logging utilities for centralized logger configuration.

Provides consistent logger creation across the application.
"""

import logging


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Get a configured logger instance.

    This centralizes logger creation to ensure consistency across the application
    and makes it easier to add global logging configuration in the future
    (e.g., custom formatters, handlers, log levels).

    Args:
        name: Logger name, typically __name__ from the calling module.
              If None, returns the root logger.

    Returns:
        Configured logging.Logger instance

    Example:
        >>> from src.utils import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    return logging.getLogger(name)


def configure_logging(
    level: int = logging.INFO,
    format_string: str | None = None,
) -> None:
    """
    Configure global logging settings.

    Args:
        level: Logging level (e.g., logging.DEBUG, logging.INFO)
        format_string: Custom format string for log messages.
                      If None, uses default format.

    Example:
        >>> configure_logging(level=logging.DEBUG)
        >>> configure_logging(
        ...     level=logging.INFO,
        ...     format_string="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ... )
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=level,
        format=format_string,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
