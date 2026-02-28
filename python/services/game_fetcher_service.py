"""
Game Fetcher — Chess.com API functions.

Standalone functions for fetching games. No database dependencies.
"""

import re
from datetime import UTC, datetime

import requests

# Regex to extract clock times from PGN comments
_CLK_RGX = re.compile(r"\[%clk\s+([\d:.]+)]")

# User-Agent for Chess.com API
_USER_AGENT = "ChessPlayerAnalyzerV2/0.1 (+https://github.com/your-username/chess-analyzer)"


def _parse_clock_time(time_str: str) -> int:
    """
    Convert clock time string (H:MM:SS or M:SS) to seconds.

    Examples:
        "0:05:30" -> 330
        "1:30" -> 90
    """
    parts = list(map(float, time_str.split(":")))
    parts = [0] * (3 - len(parts)) + parts

    if len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        hours, minutes, seconds = 0, *parts

    return int(hours * 3600 + minutes * 60 + seconds)


def fetch_games(username: str, months: int = 12) -> list[dict]:
    """
    Download games from Chess.com for a given player.

    Args:
        username: Chess.com username
        months: Number of recent months to fetch (default: 12)

    Returns:
        List of dicts with keys:
            - pgn: Full PGN text
            - move_times: List of seconds per move (extracted from clocks)
            - clock_times: Remaining time on clock after each move
            - white: White player username
            - black: Black player username
            - white_elo: White player rating (if available)
            - black_elo: Black player rating (if available)
            - end_time: ISO timestamp of game end

    Raises:
        requests.HTTPError: If API request fails
    """
    session = requests.Session()
    session.headers["User-Agent"] = _USER_AGENT

    # Get list of available archives
    archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
    print(f"Fetching archives from Chess.com for {username}...")

    try:
        response = session.get(archives_url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching archives: {e}")
        raise

    archives = response.json()["archives"][-months:]  # Most recent N months
    print(f"Found {len(archives)} monthly archives")

    games: list[dict] = []

    for idx, archive_url in enumerate(archives, 1):
        print(f"Processing archive {idx}/{len(archives)}: {archive_url}")

        try:
            data = session.get(archive_url, timeout=10).json()
            print(f"  Found {len(data.get('games', []))} games in this archive")

            for game in data["games"]:
                pgn = game["pgn"]

                # Extract clock times from PGN comments
                clocks = _CLK_RGX.findall(pgn)

                # Calculate time spent per move (clock difference)
                move_times = []
                clock_times = []  # Remaining time on clock after each move

                if clocks:
                    # Store remaining clock times (for pressure detection)
                    clock_times = [_parse_clock_time(clk) for clk in clocks]

                    # Calculate move times (time spent per move)
                    for i in range(1, len(clocks)):
                        time_before = _parse_clock_time(clocks[i - 1])
                        time_after = _parse_clock_time(clocks[i])
                        time_spent = time_before - time_after
                        move_times.append(time_spent)

                games.append(
                    {
                        "pgn": pgn,
                        "move_times": move_times,
                        "clock_times": clock_times,
                        "white": game["white"]["username"],
                        "black": game["black"]["username"],
                        "white_elo": game["white"].get("rating"),
                        "black_elo": game["black"].get("rating"),
                        "end_time": datetime.fromtimestamp(game["end_time"], UTC).isoformat(),
                    }
                )

        except Exception as e:
            print(f"  Warning: Error processing archive {archive_url}: {e}")
            continue

    # Sort games by end_time to ensure chronological order (oldest to newest)
    games.sort(key=lambda g: g["end_time"])

    print(f"\nSuccessfully downloaded {len(games)} games for {username}")
    return games
