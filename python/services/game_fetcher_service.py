"""
Game Fetcher Service.

Handles fetching games from Chess.com API, validation, and database persistence.
"""

import re
from datetime import UTC, datetime

import requests
from sqlmodel import Session

from database import Game, categorize_time_control
from repositories import AnalysisRepository, GameRepository
from utils import GameDataValidator, count_moves, extract_pgn_metadata

# Regex to extract clock times from PGN comments
_CLK_RGX = re.compile(r"\[%clk\s+([\d:.]+)]")

# User-Agent for Chess.com API
_USER_AGENT = "ChessPlayerAnalyzerV2/0.1 (+https://github.com/your-username/chess-analyzer)"


# ==================== Chess.com API Functions ====================


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
        print(f"❌ Error fetching archives: {e}")
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
                        "clock_times": clock_times,  # NEW: Remaining clock times
                        "white": game["white"]["username"],
                        "black": game["black"]["username"],
                        "white_elo": game["white"].get("rating"),
                        "black_elo": game["black"].get("rating"),
                        "end_time": datetime.fromtimestamp(game["end_time"], UTC).isoformat(),
                    }
                )

        except Exception as e:
            print(f"  ⚠️  Error processing archive {archive_url}: {e}")
            continue

    # Sort games by end_time to ensure chronological order (oldest to newest)
    # This ensures that when we take the last N games, we get the most recent ones
    games.sort(key=lambda g: g["end_time"])

    print(f"\n✅ Successfully downloaded {len(games)} games for {username}")
    return games


# ==================== GameFetcherService ====================


class GameFetcherService:
    """
    Service for fetching, validating, and persisting chess games.

    Responsibilities:
    - Fetch games from Chess.com API
    - Validate games (move count, data quality)
    - Save games to database with duplicate checking
    - Track statistics (new/cached games)
    """

    MIN_MOVES_THRESHOLD = 10  # Skip ultra-short games (aborts, fraud, etc.)

    def __init__(self, session: Session):
        """
        Initialize the game fetcher service with repositories.

        Args:
            session: SQLModel database session
        """
        self.session = session
        self.game_repo = GameRepository(session)
        self.analysis_repo = AnalysisRepository(session)

    def fetch_and_save_games(
        self,
        username: str,
        game_count: int,
        months: int = 6,
        enable_window_filter: bool = True,
    ) -> tuple[list[dict], dict[str, int], dict]:
        """
        Fetch games from Chess.com and save to database.

        Phase 1C Window Filtering:
        If enable_window_filter=True (default), uses lightweight window detection
        to pre-screen games and only analyze suspicious windows. This dramatically
        reduces Stockfish analysis time for legitimate players.

        Args:
            username: Chess.com username
            game_count: Number of recent games to fetch
            months: How many months back to search (default 6)
            enable_window_filter: Enable temporal window pre-screening (default: True)

        Returns:
            Tuple of (games_to_analyze, statistics, window_analysis)
            - games_to_analyze: List of dicts with {"game_data": dict, "game_id": int}
            - statistics: Dict with counts (new_games, cached_games, filtered, etc.)
            - window_analysis: Dict with window detection results (for storage)
        """
        # Fetch from Chess.com API
        all_games = fetch_games(username, months=months)

        if not all_games:
            return [], {"error": "No games found", "total_games": 0}

        # Limit to requested number (most recent)
        games_to_fetch = all_games[-game_count:]

        # Process and save games
        games_to_analyze = []
        stats = {
            "total_fetched": len(all_games),
            "requested_count": len(games_to_fetch),
            "new_games": 0,
            "cached_games": 0,
            "filtered_short_games": 0,
            "cached_analyses": 0,
            "needs_analysis": 0,
        }

        for game_data in games_to_fetch:
            # Validate game
            if not self._is_valid_game(game_data):
                stats["filtered_short_games"] += 1
                continue

            # Save to database
            game_record, game_created = self._save_game(game_data, username)

            if game_created:
                stats["new_games"] += 1
            else:
                stats["cached_games"] += 1

            # Check if analysis exists
            if self.analysis_repo.exists_for_game(game_record.id):
                stats["cached_analyses"] += 1
            else:
                # Needs analysis
                games_to_analyze.append({"game_data": game_data, "game_id": game_record.id})

        stats["needs_analysis"] = len(games_to_analyze)

        # Phase 1C: Window filtering (lightweight pre-screening)
        window_analysis = {}
        if enable_window_filter and games_to_analyze:
            suspicious_windows, window_analysis = self.detect_suspicious_windows(username)

            if suspicious_windows:
                # Filter games to only suspicious windows
                original_count = len(games_to_analyze)
                games_to_analyze = self.filter_games_by_windows(games_to_analyze, suspicious_windows)

                # Update stats
                games_filtered = original_count - len(games_to_analyze)
                stats["window_filtered"] = games_filtered
                stats["needs_analysis"] = len(games_to_analyze)
                stats["suspicious_windows"] = len(suspicious_windows)

                # Add filtered/analyzed counts to window_analysis
                window_analysis["games_filtered"] = games_filtered
                window_analysis["games_analyzed"] = len(games_to_analyze)
            else:
                # No suspicious windows detected - player looks clean
                stats["window_filtered"] = 0
                stats["suspicious_windows"] = 0
                window_analysis["games_filtered"] = 0
                window_analysis["games_analyzed"] = len(games_to_analyze)

        return games_to_analyze, stats, window_analysis

    def _is_valid_game(self, game_data: dict) -> bool:
        """
        Validate game meets quality criteria.

        Args:
            game_data: Game data from Chess.com API

        Returns:
            True if game is valid, False otherwise
        """
        # Use validator for comprehensive game data validation
        try:
            GameDataValidator.validate_game_data(
                game_data,
                require_pgn=True,
                require_move_times=True,  # CRITICAL for time-based analysis
                min_move_count=self.MIN_MOVES_THRESHOLD,  # Filter ultra-short games
            )
            return True
        except Exception:
            # Return False on any validation failure
            return False

    def _count_moves(self, pgn: str) -> int:
        """
        Count number of moves in a PGN string.

        Args:
            pgn: PGN string

        Returns:
            Number of moves in the game
        """
        # Use utility function for consistent PGN parsing
        return count_moves(pgn)

    def _save_game(self, game_data: dict, username: str) -> tuple[Game, bool]:
        """
        Save game to database with duplicate checking.

        Args:
            game_data: Game data from Chess.com API
            username: Player username

        Returns:
            Tuple of (Game object, was_created: bool)
        """
        pgn = game_data["pgn"]
        metadata = extract_pgn_metadata(pgn)

        # Check for duplicate
        existing = self.game_repo.find_duplicate(
            url=metadata.get("url"),
            username=username,
            date=metadata["date"],
            white=metadata["white_username"],
            black=metadata["black_username"],
        )

        if existing:
            return existing, False

        # Create new game
        game = Game(
            username=username,
            url=metadata.get("url"),
            pgn=pgn,
            date=metadata["date"],
            white_username=metadata["white_username"],
            black_username=metadata["black_username"],
            white_elo=metadata["white_elo"],
            black_elo=metadata["black_elo"],
            time_control_seconds=metadata["time_control_seconds"],
            time_control_category=categorize_time_control(metadata["time_control_seconds"]),
            eco_code=metadata["eco_code"],
            opening_name=metadata["opening_name"],
            result=metadata["result"],
            move_times=game_data.get("move_times"),
            clock_times=game_data.get("clock_times"),  # NEW: Store remaining clock times
        )

        return self.game_repo.create(game), True

    def get_games_for_analysis(self, username: str, limit: int | None = None) -> list[Game]:
        """
        Get games from database that need analysis.

        Args:
            username: Chess.com username
            limit: Optional limit on number of games

        Returns:
            List of Game objects that don't have analyses yet
        """
        # Get all games for user
        games = self.game_repo.get_by_username(username)

        # Filter to games without analysis
        games_needing_analysis = []
        for game in games:
            if not self.analysis_repo.exists_for_game(game.id):
                games_needing_analysis.append(game)

        # Apply limit if specified
        if limit:
            games_needing_analysis = games_needing_analysis[:limit]

        return games_needing_analysis

    # ============================================================
    # PHASE 1C: TEMPORAL WINDOW DETECTION (Lightweight Pre-Screening)
    # ============================================================

    def detect_suspicious_windows(
        self, username: str, window_size: int = 20
    ) -> tuple[list[tuple[int, int]], dict]:
        """
        Phase 1: Lightweight window detection (NO Stockfish analysis).

        Analyzes ALL games using only Game table data (ELO, result, date) to detect
        suspicious temporal patterns. Returns list of suspicious game index ranges.

        This is the pre-screening phase that dramatically reduces the number of games
        needing expensive Stockfish analysis.

        Args:
            username: Chess.com username
            window_size: Number of consecutive games per window (default: 20)

        Returns:
            Tuple of (suspicious_windows, window_analysis_dict)
            - suspicious_windows: List of (start_index, end_index) tuples
            - window_analysis_dict: Complete analysis results for storage
        """
        from analysis.temporal_windows import (
            calculate_elo_slope,
            detect_performance_bursts,
            detect_win_streaks,
        )

        # Get games with minimal data loading (lightweight query)
        games = self.game_repo.get_for_window_analysis(username)

        if not games:
            return [], {}

        # Convert to format expected by temporal_windows functions
        game_dicts = []
        for game in games:
            # Determine player's ELO and result
            is_white = game.white_username.lower() == username.lower()
            player_elo = game.white_elo if is_white else game.black_elo

            # Parse result from player's perspective
            if game.result == "1-0":
                result = "win" if is_white else "loss"
            elif game.result == "0-1":
                result = "loss" if is_white else "win"
            else:
                result = "draw"

            game_dicts.append(
                {
                    "date": game.date,
                    "elo": player_elo,
                    "result": result,
                    "url": game.url,
                    "game_id": game.id,  # For filtering later
                }
            )

        # Run lightweight window detection algorithms
        elo_result = calculate_elo_slope(game_dicts, window_size=window_size, slope_threshold=10.0)

        win_result = detect_win_streaks(
            game_dicts, window_size=window_size, winrate_threshold=0.85, min_games=10
        )

        burst_result = detect_performance_bursts(
            game_dicts,
            window_size=window_size,
            elo_slope_threshold=8.0,
            winrate_threshold=0.80,
            acpl_threshold=15.0,
            min_signals=2,
        )

        # Merge suspicious windows from all detection methods
        suspicious_indices = set()

        for window in elo_result.suspicious_windows:
            for idx in range(window.start_index, window.end_index + 1):
                suspicious_indices.add(idx)

        for window in win_result.suspicious_windows:
            for idx in range(window.start_index, window.end_index + 1):
                suspicious_indices.add(idx)

        for window in burst_result.suspicious_windows:
            for idx in range(window.start_index, window.end_index + 1):
                suspicious_indices.add(idx)

        # Convert indices to continuous ranges
        suspicious_windows = self._indices_to_ranges(sorted(suspicious_indices))

        # Build analysis results dictionary for storage
        window_analysis = {
            "elo_slope": {
                "max_slope": (
                    elo_result.max_slope_window.elo_slope if elo_result.max_slope_window else 0.0
                ),
                "max_slope_window": (
                    [elo_result.max_slope_window.start_index, elo_result.max_slope_window.end_index]
                    if elo_result.max_slope_window
                    else None
                ),
                "suspicious_windows": [
                    [w.start_index, w.end_index] for w in elo_result.suspicious_windows
                ],
                "total_windows_scanned": len(game_dicts) // window_size,
            },
            "win_streaks": {
                "max_win_rate": (
                    win_result.max_winrate_window.win_rate if win_result.max_winrate_window else 0.0
                ),
                "max_win_rate_window": (
                    [win_result.max_winrate_window.start_index, win_result.max_winrate_window.end_index]
                    if win_result.max_winrate_window
                    else None
                ),
                "suspicious_windows": [
                    [w.start_index, w.end_index] for w in win_result.suspicious_windows
                ],
            },
            "performance_bursts": {
                "max_signals": (
                    len(burst_result.strongest_burst.suspicion_reasons)
                    if burst_result.strongest_burst
                    else 0
                ),
                "strongest_burst_window": (
                    [burst_result.strongest_burst.start_index, burst_result.strongest_burst.end_index]
                    if burst_result.strongest_burst
                    else None
                ),
                "suspicious_windows": [
                    [w.start_index, w.end_index] for w in burst_result.suspicious_windows
                ],
            },
        }

        return suspicious_windows, window_analysis

    def _indices_to_ranges(self, sorted_indices: list[int]) -> list[tuple[int, int]]:
        """
        Convert sorted list of indices to continuous ranges.

        Example: [0, 1, 2, 5, 6, 10] → [(0, 2), (5, 6), (10, 10)]

        Args:
            sorted_indices: Sorted list of game indices

        Returns:
            List of (start, end) tuples representing continuous ranges
        """
        if not sorted_indices:
            return []

        ranges = []
        start = sorted_indices[0]
        prev = start

        for idx in sorted_indices[1:]:
            if idx != prev + 1:
                # Gap detected, close current range
                ranges.append((start, prev))
                start = idx
            prev = idx

        # Close final range
        ranges.append((start, prev))

        return ranges

    def filter_games_by_windows(
        self, games_to_analyze: list[dict], suspicious_windows: list[tuple[int, int]]
    ) -> list[dict]:
        """
        Filter games to only those in suspicious windows.

        Args:
            games_to_analyze: List of game dicts with 'game_id' field
            suspicious_windows: List of (start_index, end_index) tuples

        Returns:
            Filtered list containing only games in suspicious windows
        """
        if not suspicious_windows:
            # No suspicious windows, analyze all games (default behavior)
            return games_to_analyze

        # Get game IDs from suspicious windows
        # games_to_analyze is ordered by date, so we can use indices directly
        suspicious_game_ids = set()

        for start_idx, end_idx in suspicious_windows:
            for idx in range(start_idx, end_idx + 1):
                if idx < len(games_to_analyze):
                    suspicious_game_ids.add(games_to_analyze[idx].get("game_id"))

        # Filter to only suspicious games
        filtered_games = [
            game for game in games_to_analyze if game.get("game_id") in suspicious_game_ids
        ]

        return filtered_games
