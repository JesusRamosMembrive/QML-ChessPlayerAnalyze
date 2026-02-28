"""
Validation utilities for chess game analysis.

Provides reusable validators for common data validation patterns across services.
Implements DRY principle by centralizing validation logic.
"""

from typing import Any


class ValidationError(Exception):
    """Custom exception for validation failures."""

    def __init__(self, message: str, error_code: str | None = None, metadata: dict | None = None):
        """
        Initialize validation error.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code (e.g., "MISSING_TIME_DATA")
            metadata: Additional context about the validation failure
        """
        self.message = message
        self.error_code = error_code
        self.metadata = metadata or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert validation error to dictionary format.

        Returns:
            Dictionary with success=False, error, error_code, and metadata
        """
        result = {
            "success": False,
            "error": self.message,
        }
        if self.error_code:
            result["error_code"] = self.error_code
        if self.metadata:
            result.update(self.metadata)
        return result


class GameDataValidator:
    """Validator for chess game data structures."""

    @staticmethod
    def validate_move_times(
        move_times: list | None,
        required: bool = True,
        min_length: int = 1,
        error_code: str = "MISSING_TIME_DATA",
    ) -> None:
        """
        Validate move_times list exists and meets requirements.

        Args:
            move_times: List of move times (in seconds)
            required: Whether move_times is required (default: True)
            min_length: Minimum required length (default: 1)
            error_code: Error code for validation failure

        Raises:
            ValidationError: If validation fails
        """
        if not move_times:
            if required:
                raise ValidationError(
                    "Time data required for complete analysis",
                    error_code=error_code,
                )
            return

        if len(move_times) < min_length:
            raise ValidationError(
                f"Move times must have at least {min_length} entries, got {len(move_times)}",
                error_code="INSUFFICIENT_TIME_DATA",
            )

    @staticmethod
    def validate_move_evals(
        move_evals: list | None,
        required: bool = True,
        min_length: int = 1,
        error_code: str = "NO_MOVE_EVALUATIONS",
    ) -> None:
        """
        Validate move evaluations list exists and meets requirements.

        Args:
            move_evals: List of move evaluation dictionaries
            required: Whether move_evals is required (default: True)
            min_length: Minimum required length (default: 1)
            error_code: Error code for validation failure

        Raises:
            ValidationError: If validation fails
        """
        if not move_evals:
            if required:
                raise ValidationError(
                    "No move evaluations available",
                    error_code=error_code,
                )
            return

        if len(move_evals) < min_length:
            raise ValidationError(
                f"Move evaluations must have at least {min_length} entries, got {len(move_evals)}",
                error_code="INSUFFICIENT_MOVE_EVALS",
            )

    @staticmethod
    def validate_pgn(pgn: str | None, required: bool = True) -> None:
        """
        Validate PGN string exists and is non-empty.

        Args:
            pgn: PGN string
            required: Whether PGN is required (default: True)

        Raises:
            ValidationError: If validation fails
        """
        if not pgn:
            if required:
                raise ValidationError(
                    "PGN data is required",
                    error_code="MISSING_PGN",
                )
            return

        if not isinstance(pgn, str):
            raise ValidationError(
                f"PGN must be a string, got {type(pgn).__name__}",
                error_code="INVALID_PGN_TYPE",
            )

        if len(pgn.strip()) == 0:
            raise ValidationError(
                "PGN cannot be empty",
                error_code="EMPTY_PGN",
            )

    @staticmethod
    def validate_game_data(
        game_data: dict,
        require_pgn: bool = True,
        require_move_times: bool = True,
        min_move_count: int | None = None,
    ) -> None:
        """
        Validate complete game data structure.

        Args:
            game_data: Dictionary with game data
            require_pgn: Whether PGN is required (default: True)
            require_move_times: Whether move_times is required (default: True)
            min_move_count: Minimum number of moves required (default: None)

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(game_data, dict):
            raise ValidationError(
                f"Game data must be a dictionary, got {type(game_data).__name__}",
                error_code="INVALID_GAME_DATA_TYPE",
            )

        # Validate PGN
        pgn = game_data.get("pgn")
        GameDataValidator.validate_pgn(pgn, required=require_pgn)

        # Validate move_times
        move_times = game_data.get("move_times")
        GameDataValidator.validate_move_times(move_times, required=require_move_times)

        # Validate minimum move count if specified
        if min_move_count is not None and pgn:
            # Simple heuristic: count move number annotations (e.g., "1.", "2.")
            import re

            move_pattern = re.compile(r"\d+\.")
            move_count = len(move_pattern.findall(pgn))

            if move_count < min_move_count:
                raise ValidationError(
                    f"Game must have at least {min_move_count} moves, got {move_count}",
                    error_code="INSUFFICIENT_MOVES",
                )


class UsernameValidator:
    """Validator for Chess.com usernames."""

    @staticmethod
    def validate_username(username: str | None, required: bool = True) -> None:
        """
        Validate username format and requirements.

        Args:
            username: Chess.com username
            required: Whether username is required (default: True)

        Raises:
            ValidationError: If validation fails
        """
        if not username:
            if required:
                raise ValidationError(
                    "Username is required",
                    error_code="MISSING_USERNAME",
                )
            return

        if not isinstance(username, str):
            raise ValidationError(
                f"Username must be a string, got {type(username).__name__}",
                error_code="INVALID_USERNAME_TYPE",
            )

        # Normalize and check length
        username = username.strip()
        if len(username) == 0:
            raise ValidationError(
                "Username cannot be empty",
                error_code="EMPTY_USERNAME",
            )

        if len(username) < 3:
            raise ValidationError(
                f"Username must be at least 3 characters, got {len(username)}",
                error_code="USERNAME_TOO_SHORT",
            )

        if len(username) > 50:
            raise ValidationError(
                f"Username must be at most 50 characters, got {len(username)}",
                error_code="USERNAME_TOO_LONG",
            )


class AnalysisResultValidator:
    """Validator for analysis result structures."""

    @staticmethod
    def validate_result_dict(
        result: dict | None,
        required_keys: list[str] | None = None,
    ) -> None:
        """
        Validate analysis result dictionary structure.

        Args:
            result: Analysis result dictionary
            required_keys: List of required keys (default: ["success"])

        Raises:
            ValidationError: If validation fails
        """
        if not result:
            raise ValidationError(
                "Analysis result is required",
                error_code="MISSING_RESULT",
            )

        if not isinstance(result, dict):
            raise ValidationError(
                f"Analysis result must be a dictionary, got {type(result).__name__}",
                error_code="INVALID_RESULT_TYPE",
            )

        # Default required keys
        if required_keys is None:
            required_keys = ["success"]

        # Check required keys
        missing_keys = [key for key in required_keys if key not in result]
        if missing_keys:
            raise ValidationError(
                f"Analysis result missing required keys: {', '.join(missing_keys)}",
                error_code="MISSING_RESULT_KEYS",
                metadata={"missing_keys": missing_keys},
            )

    @staticmethod
    def is_success(result: dict) -> bool:
        """
        Check if analysis result indicates success.

        Args:
            result: Analysis result dictionary

        Returns:
            True if result["success"] is True, False otherwise
        """
        if not isinstance(result, dict):
            return False
        return result.get("success", False) is True


# Convenience functions for common patterns


def require_move_times(game_data: dict) -> list:
    """
    Extract and validate move_times from game_data.

    Args:
        game_data: Game data dictionary

    Returns:
        List of move times

    Raises:
        ValidationError: If move_times is missing or invalid
    """
    move_times = game_data.get("move_times")
    GameDataValidator.validate_move_times(move_times, required=True)
    return move_times


def require_pgn(game_data: dict) -> str:
    """
    Extract and validate PGN from game_data.

    Args:
        game_data: Game data dictionary

    Returns:
        PGN string

    Raises:
        ValidationError: If PGN is missing or invalid
    """
    pgn = game_data.get("pgn")
    GameDataValidator.validate_pgn(pgn, required=True)
    return pgn


def require_move_evals(move_evals: list | None) -> list:
    """
    Validate move evaluations list.

    Args:
        move_evals: List of move evaluation dictionaries

    Returns:
        The same list if valid

    Raises:
        ValidationError: If move_evals is missing or invalid
    """
    GameDataValidator.validate_move_evals(move_evals, required=True)
    return move_evals
