"""
Analysis Service.

Orchestrates the complete game analysis pipeline: fetch → analyze → aggregate.
"""

import json
import threading
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Optional

from sqlmodel import Session

from analysis import (
    analyze_game,
    analyze_psychological_momentum,
    calculate_acpl,
    calculate_blunders,
    calculate_enhanced_phase_analysis,
    calculate_phase_metrics,
    calculate_precision_bursts,
    calculate_time_complexity_correlation,
    calculate_time_pressure_metrics,
    calculate_topn_match_rates,
)
from analysis.human_impossibility import calculate_human_impossibility_metrics
from analysis.toggle_detection import calculate_toggle_detection_metrics
from database import GameAnalysis
from repositories import AnalysisRepository
from services.aggregation_service import AggregationService
from services.game_fetcher_service import GameFetcherService
from utils import (
    ValidationError,
    extract_pgn_metadata,
    get_logger,
    require_move_evals,
    require_move_times,
)

logger = get_logger(__name__)


class AnalysisService:
    """
    Main orchestration service for game analysis.

    Responsibilities:
    - Coordinate game fetching (via GameFetcherService)
    - Orchestrate parallel analysis of games
    - Save analysis results to database
    - Trigger aggregate recalculation (via AggregationService)
    """

    def __init__(
        self,
        session: Session,
        stockfish_path: str = "stockfish",
        depth: int = 12,
    ):
        """
        Initialize analysis service.

        Args:
            session: SQLModel database session
            stockfish_path: Path to Stockfish executable
            depth: Stockfish analysis depth
        """
        self.session = session
        self.stockfish_path = stockfish_path
        self.depth = depth

        # Initialize repositories
        self.analysis_repo = AnalysisRepository(session)

        # Initialize dependent services
        self.game_fetcher = GameFetcherService(session)
        self.aggregator = AggregationService(session)

    def analyze_player(
        self,
        username: str,
        game_count: int = 200,
        workers: int = 4,
        months: int = 6,
        progress_callback: Callable[[dict], None] | None = None,
        cancellation_event: threading.Event | None = None,
        analysis_config: dict | None = None,
        enable_window_filter: bool = False,
        window_range: tuple[int, int] | None = None,
        window_id: int = 0,
    ) -> dict[str, Any]:
        """
        Complete analysis pipeline for a player.

        Steps:
        1. Fetch games from Chess.com
        2. Filter games needing analysis
        3. Parallel analysis with Stockfish (cancellable)
        4. Save results to database
        5. Recalculate aggregates

        Args:
            username: Chess.com username
            game_count: Number of recent games to analyze
            workers: Number of parallel workers
            months: Months of history to search
            progress_callback: Optional callback(progress_data) called after each game
            cancellation_event: Optional Event to check for cancellation
            analysis_config: Optional analysis configuration dict
            enable_window_filter: Enable window detection mode (backend decides game count)
            window_range: Optional (start_idx, end_idx) to analyze only specific game range
            window_id: Window ID for storage (0 = full analysis, 1+ = window analysis)

        Returns:
            Statistics dict with counts and metrics
        """
        # Step 1: Fetch and save games
        if window_range:
            # Window mode: Fetch all games but filter by range
            from repositories import GameRepository

            game_repo = GameRepository(self.session)
            all_games = game_repo.get_by_username(username)

            # Sort by date to get consistent indexing
            all_games = sorted(all_games, key=lambda g: g.date, reverse=True)

            # Filter by window range
            start_idx, end_idx = window_range
            games_in_window = all_games[start_idx : end_idx + 1]

            logger.info(
                f"Window mode: analyzing {len(games_in_window)} games (indices {start_idx}-{end_idx}) for {username}"
            )

            # Convert Game objects to the format expected by _analyze_batch
            games_to_analyze = [
                {
                    "game_data": {
                        "pgn": game.pgn,
                        "move_times": game.move_times,
                        "date": game.date.isoformat() if game.date else None,
                        "url": game.url,
                        "white_username": game.white_username,
                        "black_username": game.black_username,
                        "white_elo": game.white_elo,
                        "black_elo": game.black_elo,
                        "result": game.result,
                        "time_control_category": game.time_control_category,
                    },
                    "game_id": game.id,
                }
                for game in games_in_window
            ]
            fetch_stats = {"total_fetched": len(games_in_window), "already_saved": 0, "newly_saved": 0}
            window_analysis = None
        else:
            # Normal mode: Fetch and filter
            games_to_analyze, fetch_stats, window_analysis = self.game_fetcher.fetch_and_save_games(
                username, game_count, months, enable_window_filter=enable_window_filter
            )

        # Step 2: Parallel analysis
        if not games_to_analyze:
            # No games need analysis (all cached)
            return {
                **fetch_stats,
                "new_analyses": 0,
                "failed_analyses": 0,
                "aggregates_updated": False,
            }

        results = self._analyze_batch(
            games_to_analyze,
            username,
            workers,
            progress_callback,
            cancellation_event,
            analysis_config,
        )

        # Step 3: Save analysis results (skip if dry-run)
        is_dry_run = analysis_config and analysis_config.get("dry_run", False)
        if not is_dry_run:
            analysis_stats = self._save_analysis_results(results, username)
        else:
            # Dry-run: don't save, just report stats from results
            analysis_stats = {
                "new_analyses": sum(1 for r in results if r.get("success")),
                "failed_analyses": sum(1 for r in results if not r.get("success")),
            }

        # Step 4: Recalculate aggregates
        # Check if there are any analyses in DB (since we now save immediately)
        aggregates_updated = False
        try:
            actual_count = self.analysis_repo.count_by_username(username)

            if actual_count > 0:
                self.aggregator.recalculate_aggregates(
                    username, window_analysis=window_analysis, window_id=window_id, window_range=window_range
                )
                aggregates_updated = True
                logger.info(f"Aggregates updated for {username} ({actual_count} analyses, window_id={window_id})")
        except Exception as e:
            # Log but don't fail the whole operation
            logger.error(f"Warning: Could not update aggregates for {username}: {e}")

        # Combine statistics
        return {
            **fetch_stats,
            **analysis_stats,
            "aggregates_updated": aggregates_updated,
        }

    def analyze_single_game(self, game_data: dict, username: str) -> dict[str, Any]:
        """
        Analyze a single game.

        Args:
            game_data: Dict with "pgn" and optional "move_times"
            username: Player username

        Returns:
            Analysis results dict
        """
        try:
            pgn = game_data["pgn"]

            # CRITICAL: Validate move_times are present using validator
            # Time data is required for complete analysis (defense in depth)
            try:
                move_times = require_move_times(game_data)
            except ValidationError as e:
                return {**e.to_dict(), "metadata": extract_pgn_metadata(pgn)}

            # Extract clock_times (remaining time on clock) if available
            clock_times = game_data.get("clock_times")  # NEW: for pressure detection

            # Extract metadata
            metadata = extract_pgn_metadata(pgn)
            is_white = metadata["white_username"] == username
            player_elo = metadata["white_elo"] if is_white else metadata["black_elo"]

            # Analyze with Stockfish
            move_evals = analyze_game(pgn, stockfish_path=self.stockfish_path, depth=self.depth)

            # Validate move evaluations using validator
            try:
                move_evals = require_move_evals(move_evals)
            except ValidationError as e:
                return {**e.to_dict(), "metadata": metadata}

            # CRITICAL: Filter to only the player's moves
            # White plays on even indices (0, 2, 4, ...), Black on odd indices (1, 3, 5, ...)
            player_move_evals = [
                move_evals[i] for i in range(0 if is_white else 1, len(move_evals), 2)
            ]

            # Calculate all metrics using ONLY player's moves
            acpl = calculate_acpl(player_move_evals)
            topn_rates = calculate_topn_match_rates(player_move_evals)
            blunder_stats = calculate_blunders(player_move_evals)
            phase_breakdown = calculate_phase_metrics(pgn, player_move_evals)

            # Advanced metrics (also use player's moves only)
            precision_bursts = calculate_precision_bursts(player_move_evals)
            enhanced_phase = calculate_enhanced_phase_analysis(pgn, player_move_evals)

            # Time analysis (still needs ALL move_evals for context)
            time_analysis = calculate_time_pressure_metrics(move_times, move_evals, is_white)

            # Extract player's move times for time-complexity correlation
            player_times = []

            for i, time in enumerate(move_times):
                if i < len(move_evals) and ((is_white and time > 0) or (not is_white and time < 0)):
                    player_times.append(abs(time))

            # Extract player's clock times (remaining time on clock after each move)
            player_clock_times = []
            if clock_times:
                for i, clock in enumerate(clock_times):
                    # White moves: even indices (0, 2, 4, ...), Black moves: odd indices (1, 3, 5, ...)
                    if (is_white and i % 2 == 0) or (not is_white and i % 2 == 1):
                        player_clock_times.append(clock)

            # Time-complexity correlation (uses player_move_evals from above)
            time_complexity = calculate_time_complexity_correlation(player_move_evals, player_times)

            # Psychological momentum (use player's moves only)
            psychological_momentum = None
            if player_move_evals:
                move_eval_losses = [
                    m.get("cp_loss", 0) for m in player_move_evals if isinstance(m, dict)
                ]

                # Determine time control for pressure threshold
                time_control = metadata.get("time_control", "blitz")  # Default to blitz

                # DEBUG: Log what we're passing
                logger.info(
                    f"🔍 Calling psychological analysis: "
                    f"move_evals={len(move_eval_losses)}, "
                    f"player_times={len(player_times) if player_times else 0}, "
                    f"player_clock_times={len(player_clock_times) if player_clock_times else 0}, "
                    f"time_control={time_control}"
                )
                if player_clock_times:
                    logger.info(f"   player_clock_times (first 10): {player_clock_times[:10]}")

                # CRITICAL: Align clock_times length with move_eval_losses
                # The last move of the game may not have a clock time (clock stops when game ends)
                # Truncate player_clock_times to match move_eval_losses length
                aligned_player_clock_times = player_clock_times[: len(move_eval_losses)]

                psychological_momentum = analyze_psychological_momentum(
                    move_evals=move_eval_losses,
                    move_times=player_times,
                    clock_times=aligned_player_clock_times if aligned_player_clock_times else None,  # NEW
                    time_control=time_control,  # NEW
                )

            # Difficulty metrics (human impossibility + toggle detection)
            difficulty_metrics = None
            if player_move_evals:
                impossibility = calculate_human_impossibility_metrics(player_move_evals)
                toggle = calculate_toggle_detection_metrics(player_move_evals, player_times or None)
                difficulty_metrics = {**impossibility, **toggle}

            return {
                "success": True,
                "metadata": metadata,
                "player_elo": player_elo,
                "is_white": is_white,
                "acpl": acpl,
                "topn_rates": topn_rates,  # {"top1": float, "top2": float, "top3": float, "top5": float}
                "blunder_stats": blunder_stats,
                "move_evals": move_evals,
                "phase_breakdown": phase_breakdown,
                "time_analysis": time_analysis,
                "precision_bursts": precision_bursts,
                "time_complexity": time_complexity,
                "enhanced_phase": enhanced_phase,
                "psychological_momentum": psychological_momentum,
                "difficulty_metrics": difficulty_metrics,
                "depth": self.depth,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _analyze_batch(
        self,
        games_to_analyze: list[dict],
        username: str,
        workers: int,
        progress_callback: Callable[[dict], None] | None = None,
        cancellation_event: threading.Event | None = None,
        analysis_config: dict | None = None,
    ) -> list[dict]:
        """
        Analyze multiple games in parallel.

        Args:
            games_to_analyze: List of dicts with {game_data: dict, game_id: int}
            username: Player username
            workers: Number of parallel workers
            progress_callback: Optional callback to report progress
            cancellation_event: Optional event to check for cancellation
            analysis_config: Optional analysis configuration dict

        Returns:
            List of analysis results
        """
        results = []
        games_completed = 0

        # Prepare arguments for parallel processing
        tasks = [
            (
                item["game_data"],
                item["game_id"],
                username,
                self.stockfish_path,
                self.depth,
                None,
                analysis_config,
            )
            for item in games_to_analyze
        ]

        # Run in parallel
        with ProcessPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(_analyze_single_game_worker, *task): task for task in tasks
            }

            # Collect results as they complete
            for future in as_completed(future_to_task):
                # Check for cancellation
                if cancellation_event and cancellation_event.is_set():
                    print(f"Cancellation detected, stopping analysis for {username}")
                    break

                try:
                    result = future.result()
                    results.append(result)
                    games_completed += 1

                    # Check if dry-run mode is enabled
                    is_dry_run = analysis_config and analysis_config.get("dry_run", False)

                    if is_dry_run:
                        # Dry-run: print to console instead of saving
                        self._print_result_summary(result, username)
                    else:
                        # Normal mode: save to database
                        self._save_single_result(result, username)

                    # Report progress with actual saved count
                    if progress_callback:
                        # Count actual saved analyses in DB using repository
                        total_saved = self.analysis_repo.count_by_username(username)

                        progress_callback(
                            {
                                "username": username,
                                "games_analyzed": total_saved,
                                "games_requested": len(games_to_analyze),
                                "progress": (total_saved / len(games_to_analyze)) * 100,
                            }
                        )

                except Exception as e:
                    # Handle worker failure
                    task = future_to_task[future]
                    results.append(
                        {
                            "success": False,
                            "error": f"Worker failed: {str(e)}",
                            "game_id": task[1],
                        }
                    )

        return results

    def _save_single_result(self, result: dict, username: str) -> int:
        """
        Save a single analysis result to database immediately.

        Args:
            result: Analysis result dict
            username: Player username

        Returns:
            1 if saved successfully, 0 otherwise
        """
        if not result.get("success"):
            return 0

        try:
            game_id = result["game_id"]

            # Skip if analysis already exists
            if self.analysis_repo.exists_for_game(game_id):
                return 0

            # Extract top-N rates
            topn = result.get("topn_rates", {})

            # Create analysis object
            analysis = GameAnalysis(
                game_id=game_id,
                username=username,
                acpl=result["acpl"],
                top1_match_rate=topn.get("top1"),
                top2_match_rate=topn.get("top2"),
                top3_match_rate=topn.get("top3"),
                top4_match_rate=topn.get("top4"),
                top5_match_rate=topn.get("top5"),
                move_count=len(result["move_evals"]),
                blunder_count=result["blunder_stats"]["blunder_count"],
                blunder_rate=result["blunder_stats"]["blunder_rate"],
                move_evals=json.dumps(result["move_evals"]),
                phase_breakdown=json.dumps(result["phase_breakdown"]),
                time_analysis=json.dumps(result["time_analysis"]),
                precision_bursts=json.dumps(result["precision_bursts"]),
                time_complexity=json.dumps(result["time_complexity"]),
                enhanced_phase=json.dumps(result["enhanced_phase"]),
                psychological_momentum=(
                    json.dumps(result["psychological_momentum"])
                    if result["psychological_momentum"]
                    else None
                ),
                difficulty_metrics=(
                    json.dumps(result["difficulty_metrics"])
                    if result.get("difficulty_metrics")
                    else None
                ),
                stockfish_depth=result["depth"],
            )

            self.analysis_repo.create(analysis)
            return 1

        except Exception as e:
            logger.error(f"Failed to save single analysis for game {result.get('game_id')}: {e}")
            return 0

    def _print_result_summary(self, result: dict, username: str):
        """
        Print analysis result to console in dry-run mode.

        Args:
            result: Analysis result dict
            username: Player username
        """
        if not result.get("success"):
            print(f"   ❌ Game {result.get('game_id')}: {result.get('error')}")
            return

        game_id = result["game_id"]
        metadata = result.get("metadata", {})

        # Format game header
        event = metadata.get("event", "Unknown")
        date = metadata.get("date", "Unknown")
        white = metadata.get("white", "?")
        black = metadata.get("black", "?")
        white_elo = metadata.get("white_elo", "?")
        black_elo = metadata.get("black_elo", "?")

        print(f"\n   📊 Game #{game_id} - {event} ({date})")
        print(f"      White: {white} ({white_elo}) vs Black: {black} ({black_elo})")

        # Basic metrics
        if result.get("acpl") is not None:
            print(f"      ✅ ACPL: {result['acpl']:.2f}")

        # Top-N match rates
        topn = result.get("topn_rates")
        if topn:
            if topn.get("top1") is not None:
                print(f"      ✅ Top-1 Match: {topn['top1']*100:.1f}%")
            if topn.get("top2") is not None:
                print(f"      ✅ Top-2 Match: {topn['top2']*100:.1f}%")
            if topn.get("top3") is not None:
                print(f"      ✅ Top-3 Match: {topn['top3']*100:.1f}%")

        # Blunders
        blunder_stats = result.get("blunder_stats")
        if blunder_stats:
            blunder_count = blunder_stats.get("blunder_count", 0)
            blunder_rate = blunder_stats.get("blunder_rate", 0)
            print(f"      ✅ Blunders: {blunder_count} ({blunder_rate*100:.1f}%)")

        # Additional metrics if enabled
        if result.get("time_analysis") and result["time_analysis"] != "null":
            print("      ⏱️  Time Analysis: Included")

        if result.get("psychological_momentum"):
            print("      🧠 Psychology: Included")

        if result.get("precision_bursts"):
            print("      🎯 Precision Bursts: Included")

    def _save_analysis_results(self, results: list[dict], username: str) -> dict[str, int]:
        """
        Save analysis results to database.

        Args:
            results: List of analysis result dicts
            username: Player username (normalized)

        Returns:
            Statistics dict with counts
        """
        stats = {
            "new_analyses": 0,
            "failed_analyses": 0,
        }

        for result in results:
            if not result.get("success"):
                stats["failed_analyses"] += 1
                continue

            # Save to database
            try:
                game_id = result["game_id"]

                # Skip if analysis already exists
                if self.analysis_repo.exists_for_game(game_id):
                    continue

                # FIXED: Use normalized username parameter, not PGN header username
                # The username from PGN headers can have different capitalization

                # Extract top-N rates
                topn = result.get("topn_rates", {})

                analysis = GameAnalysis(
                    game_id=game_id,
                    username=username,
                    acpl=result["acpl"],
                    top1_match_rate=topn.get("top1"),
                    top2_match_rate=topn.get("top2"),
                    top3_match_rate=topn.get("top3"),
                    top4_match_rate=topn.get("top4"),
                    top5_match_rate=topn.get("top5"),
                    move_count=len(result["move_evals"]),
                    blunder_count=result["blunder_stats"]["blunder_count"],
                    blunder_rate=result["blunder_stats"]["blunder_rate"],
                    move_evals=json.dumps(result["move_evals"]),
                    phase_breakdown=json.dumps(result["phase_breakdown"]),
                    # Time data is now guaranteed to be present
                    time_analysis=json.dumps(result["time_analysis"]),
                    precision_bursts=json.dumps(result["precision_bursts"]),
                    time_complexity=json.dumps(result["time_complexity"]),
                    enhanced_phase=json.dumps(result["enhanced_phase"]),
                    # Psychological momentum can still be None (depends on data quality)
                    psychological_momentum=(
                        json.dumps(result["psychological_momentum"])
                        if result["psychological_momentum"]
                        else None
                    ),
                    difficulty_metrics=(
                        json.dumps(result["difficulty_metrics"])
                        if result.get("difficulty_metrics")
                        else None
                    ),
                    stockfish_depth=result["depth"],
                )

                self.analysis_repo.create(analysis)
                stats["new_analyses"] += 1

            except Exception as e:
                print(f"Failed to save analysis: {e}")
                stats["failed_analyses"] += 1

        return stats


def _analyze_single_game_worker(
    game_data: dict,
    game_id: int,
    username: str,
    stockfish_path: str,
    depth: int,
    trace_id: Optional[str] = None,
    analysis_config: Optional[dict] = None,
) -> dict:
    """
    Worker function for parallel game analysis.

    This function is defined at module level to work with multiprocessing.

    Args:
        game_data: Game data dict with "pgn" and "move_times"
        game_id: Database game ID
        username: Player username
        stockfish_path: Path to Stockfish
        depth: Analysis depth
        trace_id: Optional trace ID for distributed tracing
        analysis_config: Optional dict config for enabling/disabling features

    Returns:
        Analysis result dict (includes worker_trace if tracing enabled)
    """
    # Import config here to avoid circular imports
    from analysis.analysis_config import AnalysisConfig

    # Convert dict config to AnalysisConfig object (for multiprocessing serialization)
    if analysis_config is None:
        config = AnalysisConfig.all_enabled()
    else:
        config = AnalysisConfig(**analysis_config)

    try:
        pgn = game_data["pgn"]

        # CRITICAL: Validate move_times are present using validator (defense in depth)
        try:
            move_times = require_move_times(game_data)
        except ValidationError as e:
            return {**e.to_dict(), "game_id": game_id}

        # Extract metadata
        metadata = extract_pgn_metadata(pgn)
        # FIXED: Case-insensitive username comparison
        is_white = metadata["white_username"].lower() == username.lower()
        player_elo = metadata["white_elo"] if is_white else metadata["black_elo"]

        # Analyze with Stockfish (multipv=5 for accurate Top-N match rates)
        # Get player's moves with book moves skipped for accurate metrics
        player_color = "white" if is_white else "black"
        player_move_evals = analyze_game(
            pgn,
            stockfish_path=stockfish_path,
            depth=depth,
            multipv=5,
            player_color=player_color,
            skip_book_moves=True,
        )

        # Validate move evaluations using validator
        try:
            player_move_evals = require_move_evals(player_move_evals)
        except ValidationError as e:
            return {**e.to_dict(), "game_id": game_id}

        # Get ALL moves (both players, including book) for time analysis context
        all_move_evals = analyze_game(
            pgn,
            stockfish_path=stockfish_path,
            depth=depth,
            multipv=5,
            player_color=None,  # Get all moves
            skip_book_moves=False,  # Include book moves for time context
        )

        # Calculate metrics using ONLY player's moves (book moves excluded)
        # Basic metrics (always enabled)
        acpl = None
        blunder_stats = None
        if config.basic_metrics:
            acpl = calculate_acpl(player_move_evals)
            blunder_stats = calculate_blunders(player_move_evals)

        # Top-N match rates
        topn_rates = None
        if config.topn_match_rates:
            topn_rates = calculate_topn_match_rates(player_move_evals)

        # Phase analysis (part of basic metrics)
        phase_breakdown = None
        precision_bursts = None
        enhanced_phase = None
        if config.basic_metrics:
            phase_breakdown = calculate_phase_metrics(pgn, player_move_evals)
            precision_bursts = calculate_precision_bursts(player_move_evals)
            enhanced_phase = calculate_enhanced_phase_analysis(pgn, player_move_evals)

        # Time analysis (conditional)
        time_analysis = None
        time_complexity = None
        if config.time_pressure or config.time_complexity_correlation:
            # Time analysis needs ALL move_evals for proper move_times alignment
            if config.time_pressure:
                time_analysis = calculate_time_pressure_metrics(
                    move_times, all_move_evals, is_white
                )

            # Extract player's move times for time-complexity correlation
            if config.time_complexity_correlation:
                # CRITICAL: Use same filtering method as player_move_evals (index-based, not sign-based)
                # White plays on even indices (0, 2, 4, ...), Black on odd indices (1, 3, 5, ...)
                # IMPORTANT: Also skip first 10 moves to align with player_move_evals (which skips book moves)
                player_times = []
                move_counter = 0
                for i in range(0 if is_white else 1, len(move_times), 2):
                    if i < len(move_times):
                        move_counter += 1
                        # Skip first 10 player moves to match skip_book_moves=True
                        if move_counter > 10:
                            player_times.append(abs(move_times[i]))

                # CRITICAL: Align player_move_evals with player_times
                # The last move of the game often has no time recorded (clock stops)
                # If the player made the last move, we'll have 1 more eval than times
                # Truncate evals to match times length for time-based analysis
                aligned_player_evals = player_move_evals[: len(player_times)]

                # Time-complexity correlation (uses aligned evals and times)
                time_complexity = calculate_time_complexity_correlation(
                    aligned_player_evals, player_times
                )

        # Psychological momentum (conditional)
        psychological_momentum = None
        if config.psychological_momentum:
            # Need to extract player_times if not already done
            if not config.time_complexity_correlation:
                player_times = []
                move_counter = 0
                for i in range(0 if is_white else 1, len(move_times), 2):
                    if i < len(move_times):
                        move_counter += 1
                        if move_counter > 10:
                            player_times.append(abs(move_times[i]))

                aligned_player_evals = player_move_evals[: len(player_times)]

            if aligned_player_evals:
                move_eval_losses = [
                    m.get("cp_loss", 0) for m in aligned_player_evals if isinstance(m, dict)
                ]

                # Extract player's clock times (remaining time on clock after each move)
                player_clock_times = []
                clock_times = game_data.get("clock_times")  # NEW: for pressure detection

                if clock_times:
                    move_counter = 0
                    for i in range(0 if is_white else 1, len(clock_times), 2):
                        if i < len(clock_times):
                            move_counter += 1
                            # Skip first 10 player moves to match player_move_evals
                            if move_counter > 10:
                                player_clock_times.append(clock_times[i])

                # Determine time control for pressure threshold
                time_control = metadata.get("time_control", "blitz")  # Default to blitz

                # CRITICAL: Align clock_times length with move_eval_losses
                # The last move of the game may not have a clock time (clock stops when game ends)
                # Truncate player_clock_times to match move_eval_losses length
                aligned_player_clock_times = player_clock_times[: len(move_eval_losses)]

                psychological_momentum = analyze_psychological_momentum(
                    move_evals=move_eval_losses,
                    move_times=player_times,
                    clock_times=aligned_player_clock_times if aligned_player_clock_times else None,  # NEW
                    time_control=time_control,  # NEW
                )

        # Difficulty metrics (human impossibility + toggle detection)
        difficulty_metrics = None
        if config.basic_metrics and player_move_evals:
            from analysis.human_impossibility import calculate_human_impossibility_metrics
            from analysis.toggle_detection import calculate_toggle_detection_metrics

            impossibility = calculate_human_impossibility_metrics(player_move_evals)

            # For toggle detection, pass player_times if available
            # player_times is defined by time_complexity_correlation or psychological_momentum blocks
            toggle_times = None
            try:
                if player_times:
                    toggle_times = player_times
            except NameError:
                pass
            toggle = calculate_toggle_detection_metrics(player_move_evals, toggle_times)

            difficulty_metrics = {**impossibility, **toggle}

        result = {
            "success": True,
            "game_id": game_id,
            "metadata": metadata,
            "player_elo": player_elo,
            "is_white": is_white,
            "acpl": acpl,
            "topn_rates": topn_rates,  # {"top1": float, "top2": float, "top3": float, "top5": float}
            "blunder_stats": blunder_stats,
            "move_evals": player_move_evals,  # CRITICAL: Only player's moves, not all moves
            "phase_breakdown": phase_breakdown,
            "time_analysis": time_analysis,
            "precision_bursts": precision_bursts,
            "time_complexity": time_complexity,
            "enhanced_phase": enhanced_phase,
            "psychological_momentum": psychological_momentum,
            "difficulty_metrics": difficulty_metrics,
            "depth": depth,
        }

        return result

    except Exception as e:
        import traceback

        error_result = {
            "success": False,
            "error": str(e),
            "game_id": game_id,
            "traceback": traceback.format_exc(),
        }

        return error_result
