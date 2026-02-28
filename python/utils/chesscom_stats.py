"""
Chess.com player statistics fetcher.

Retrieves player ratings and statistics from Chess.com Public API.
"""

import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


def fetch_player_stats(username: str, timeout: int = 10) -> dict | None:
    """
    Fetch player statistics from Chess.com API.

    Args:
        username: Chess.com username
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Dictionary with player stats, or None if fetch fails

    API Endpoint: https://api.chess.com/pub/player/{username}/stats

    Response Structure:
        {
            "chess_rapid": {
                "last": {"rating": 1070, "date": 1762662010, "rd": 42},
                "best": {"rating": 1588, "date": 1737914882, "game": "..."},
                "record": {"win": 66, "loss": 81, "draw": 3}
            },
            "chess_bullet": {...},
            "chess_blitz": {...},
            "chess_daily": {...},
            "fide": 0
        }
    """
    url = f"https://api.chess.com/pub/player/{username}/stats"

    # Chess.com requires User-Agent header
    headers = {
        "User-Agent": "ChessPlayerAnalyzerV2/2.0 (Python/requests; +https://github.com/your-repo)"
    }

    try:
        logger.info(f"Fetching Chess.com stats for username: {username}")
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        data = response.json()
        logger.info(f"Successfully fetched stats for {username}")
        return data

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching stats for {username} (timeout={timeout}s)")
        return None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning(f"Player not found: {username}")
        else:
            logger.error(f"HTTP error fetching stats for {username}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching stats for {username}: {e}")
        return None
    except ValueError as e:
        logger.error(f"JSON decode error for {username}: {e}")
        return None


def parse_player_ratings(stats_data: dict) -> dict:
    """
    Parse Chess.com stats data into structured ratings format.

    Args:
        stats_data: Raw data from Chess.com /stats API

    Returns:
        Dictionary with structured ratings:
        {
            "rapid": {"rating": 1070, "best_rating": 1588, "win": 66, "loss": 81, "draw": 3},
            "blitz": {...},
            "bullet": {...},
            "daily": {...},
            "fide": 0,
            "fetched_at": "2025-11-21T10:00:00Z"
        }
    """
    result = {"fetched_at": datetime.utcnow().isoformat() + "Z"}

    # Map Chess.com API keys to our schema keys
    time_control_mapping = {
        "chess_rapid": "rapid",
        "chess_blitz": "blitz",
        "chess_bullet": "bullet",
        "chess_daily": "daily",
    }

    for api_key, schema_key in time_control_mapping.items():
        if api_key in stats_data:
            time_control_data = stats_data[api_key]

            rating_info = {}

            # Current rating
            if "last" in time_control_data:
                rating_info["rating"] = time_control_data["last"].get("rating")

            # Best rating
            if "best" in time_control_data:
                rating_info["best_rating"] = time_control_data["best"].get("rating")

            # Record
            if "record" in time_control_data:
                record = time_control_data["record"]
                rating_info["win"] = record.get("win")
                rating_info["loss"] = record.get("loss")
                rating_info["draw"] = record.get("draw")

            # Only add if we have at least the current rating
            if rating_info.get("rating") is not None:
                result[schema_key] = rating_info

    # FIDE rating
    if "fide" in stats_data and stats_data["fide"]:
        result["fide"] = stats_data["fide"]

    return result


def get_player_ratings(username: str) -> dict | None:
    """
    Fetch and parse player ratings from Chess.com.

    Convenience function that combines fetch + parse.

    Args:
        username: Chess.com username

    Returns:
        Structured ratings dict, or None if fetch fails

    Example:
        >>> ratings = get_player_ratings("Blaine-Carroll")
        >>> print(ratings["rapid"]["rating"])
        1070
        >>> print(ratings["bullet"]["best_rating"])
        1545
    """
    stats = fetch_player_stats(username)
    if not stats:
        return None

    return parse_player_ratings(stats)
