"""
JSON field parsing utilities with consistent error handling.

This module provides centralized JSON parsing to eliminate code duplication
and ensure consistent error handling across the codebase.
"""

import json
from typing import Any

from utils.logging_utils import get_logger

logger = get_logger(__name__)


class JSONFieldParser:
    """
    Centralized JSON field parsing with robust error handling.

    Handles common patterns:
    - Simple JSON strings
    - Already-parsed dictionaries
    - Double-encoded JSON (string -> string -> dict)
    - None/empty values
    - Parsing errors with graceful degradation
    """

    @staticmethod
    def parse_field(
        obj: Any,
        field_name: str,
        default: Any = None,
        handle_double_encoding: bool = False,
        log_errors: bool = False,
    ) -> Any:
        """
        Parse a JSON field from an object with consistent error handling.

        Args:
            obj: Object containing the field (e.g., database model instance)
            field_name: Name of the field to parse
            default: Value to return if parsing fails or field is None
            handle_double_encoding: If True, handle double-encoded JSON (string -> string -> dict)
            log_errors: If True, log parsing errors at WARNING level

        Returns:
            Parsed value (usually dict or list), or default if parsing fails

        Examples:
            >>> parser = JSONFieldParser()
            >>> # Simple usage
            >>> data = parser.parse_field(analysis, 'phase_breakdown', default={})

            >>> # With double encoding handling
            >>> data = parser.parse_field(
            ...     analysis,
            ...     'time_complexity',
            ...     default={},
            ...     handle_double_encoding=True
            ... )

            >>> # Direct string parsing
            >>> data = parser.parse_json_string('{"key": "value"}', default={})
        """
        try:
            # Get field value
            if hasattr(obj, field_name):
                value = getattr(obj, field_name)
            elif isinstance(obj, dict):
                value = obj.get(field_name)
            else:
                return default

            # Return default if None or empty
            if not value:
                return default

            # If already a dict/list, return as-is
            if isinstance(value, (dict, list)):
                return value

            # Parse JSON string
            if isinstance(value, str):
                parsed = json.loads(value)

                # Handle double encoding if requested
                if handle_double_encoding and isinstance(parsed, str):
                    parsed = json.loads(parsed)

                return parsed

            # Unknown type
            if log_errors:
                logger.warning(f"Field '{field_name}' has unexpected type: {type(value).__name__}")
            return default

        except (json.JSONDecodeError, TypeError, KeyError, AttributeError) as e:
            if log_errors:
                logger.warning(f"Failed to parse field '{field_name}': {e}")
            return default

    @staticmethod
    def parse_json_string(
        json_string: str | None,
        default: Any = None,
        handle_double_encoding: bool = False,
        log_errors: bool = False,
    ) -> Any:
        """
        Parse a JSON string directly (without object field access).

        Args:
            json_string: JSON string to parse
            default: Value to return if parsing fails
            handle_double_encoding: If True, handle double-encoded JSON
            log_errors: If True, log parsing errors

        Returns:
            Parsed value or default

        Examples:
            >>> parser = JSONFieldParser()
            >>> data = parser.parse_json_string('{"key": "value"}')
            {'key': 'value'}

            >>> data = parser.parse_json_string(None, default={})
            {}
        """
        if not json_string:
            return default

        # Already parsed
        if isinstance(json_string, (dict, list)):
            return json_string

        try:
            parsed = json.loads(json_string)

            # Handle double encoding
            if handle_double_encoding and isinstance(parsed, str):
                parsed = json.loads(parsed)

            return parsed

        except (json.JSONDecodeError, TypeError) as e:
            if log_errors:
                logger.warning(f"Failed to parse JSON string: {e}")
            return default

    @staticmethod
    def safe_get_nested(data: dict, *keys: str, default: Any = None) -> Any:
        """
        Safely get nested dictionary values.

        Args:
            data: Dictionary to navigate
            *keys: Sequence of keys to traverse
            default: Value to return if any key is missing

        Returns:
            Nested value or default

        Examples:
            >>> parser = JSONFieldParser()
            >>> data = {"opening": {"acpl": 15.2}}
            >>> parser.safe_get_nested(data, "opening", "acpl")
            15.2

            >>> parser.safe_get_nested(data, "middlegame", "acpl", default=None)
            None
        """
        try:
            result = data
            for key in keys:
                result = result[key]
            return result
        except (KeyError, TypeError, AttributeError):
            return default
