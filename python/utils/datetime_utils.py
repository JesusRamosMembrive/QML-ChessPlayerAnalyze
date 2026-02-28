"""
Datetime utilities for consistent timezone handling.

Provides centralized datetime operations with UTC timezone awareness
to prevent timezone-related bugs and ensure consistency across the application.
"""

from datetime import datetime, timedelta, timezone

# Python 3.11+ has UTC, but for compatibility use timezone.utc
UTC = timezone.utc


def now_utc() -> datetime:
    """
    Get current UTC time with timezone awareness.

    This is the preferred method for getting the current time in the application
    to ensure consistency and timezone awareness.

    Returns:
        Timezone-aware datetime object in UTC

    Example:
        >>> from src.utils import now_utc
        >>> current_time = now_utc()
        >>> print(current_time.tzinfo)
        UTC
    """
    return datetime.now(UTC)


def now_naive() -> datetime:
    """
    Get current time without timezone information.

    Use this only when interfacing with legacy systems or databases
    that don't support timezone-aware datetimes. Prefer now_utc() when possible.

    Returns:
        Naive datetime object (no timezone info)

    Example:
        >>> from src.utils import now_naive
        >>> current_time = now_naive()
        >>> print(current_time.tzinfo)
        None

    Warning:
        This returns a naive datetime. Prefer now_utc() for new code.
    """
    return datetime.now()


def format_timestamp(dt: datetime, include_microseconds: bool = False) -> str:
    """
    Format datetime to ISO 8601 string.

    Args:
        dt: Datetime object to format
        include_microseconds: Whether to include microseconds in output

    Returns:
        ISO 8601 formatted string

    Example:
        >>> from src.utils import now_utc, format_timestamp
        >>> dt = now_utc()
        >>> format_timestamp(dt)
        '2025-11-18T08:30:00+00:00'
        >>> format_timestamp(dt, include_microseconds=True)
        '2025-11-18T08:30:00.123456+00:00'
    """
    if include_microseconds:
        return dt.isoformat()
    return dt.replace(microsecond=0).isoformat()


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse ISO 8601 timestamp string to datetime.

    Args:
        timestamp_str: ISO 8601 formatted timestamp string

    Returns:
        Datetime object parsed from string

    Raises:
        ValueError: If timestamp string is not valid ISO 8601 format

    Example:
        >>> from src.utils import parse_timestamp
        >>> dt = parse_timestamp('2025-11-18T08:30:00+00:00')
        >>> print(dt.year, dt.month, dt.day)
        2025 11 18
    """
    return datetime.fromisoformat(timestamp_str)


def datetime_ago(*, days: int = 0, hours: int = 0, minutes: int = 0) -> datetime:
    """
    Get UTC datetime N days/hours/minutes ago.

    Args:
        days: Number of days ago
        hours: Number of hours ago
        minutes: Number of minutes ago

    Returns:
        Timezone-aware datetime in UTC

    Example:
        >>> from src.utils import datetime_ago
        >>> yesterday = datetime_ago(days=1)
        >>> two_hours_ago = datetime_ago(hours=2)
        >>> thirty_minutes_ago = datetime_ago(minutes=30)
    """
    delta = timedelta(days=days, hours=hours, minutes=minutes)
    return now_utc() - delta


def is_older_than(dt: datetime, *, days: int = 0, hours: int = 0, minutes: int = 0) -> bool:
    """
    Check if datetime is older than specified duration.

    Args:
        dt: Datetime to check
        days: Number of days threshold
        hours: Number of hours threshold
        minutes: Number of minutes threshold

    Returns:
        True if datetime is older than threshold, False otherwise

    Example:
        >>> from src.utils import now_utc, is_older_than
        >>> old_time = datetime_ago(days=7)
        >>> is_older_than(old_time, days=1)
        True
        >>> is_older_than(old_time, days=30)
        False
    """
    threshold = datetime_ago(days=days, hours=hours, minutes=minutes)
    return dt < threshold
