"""
Analysis Service.

Orchestrates the complete game analysis pipeline: fetch → analyze → aggregate → save JSON.
"""

import json
import threading
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Optional

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
from analysis.suspicion import calculate_suspicion_score
from analysis.toggle_detection import calculate_toggle_detection_metrics
from services.calculators import calculate_all
from services.game_fetcher_service import fetch_games
from storage import build_calculator_items, categorize_time_control, load_player, save_player
from utils import (
    GameDataValidator,
    ValidationError,
    count_moves,
    extract_pgn_metadata,
    get_logger,
    require_move_evals,
    require_move_times,
)

logger = get_logger(__name__)

MIN_MOVES_THRESHOLD = 10


class AnalysisService:
    """
    Main orchestration service for game analysis.

    Pipeline: fetch games → filter → parallel Stockfish analysis → aggregate → save JSON.
    """

    def __init__(self, stockfish_path: str = "stockfish", depth: int = 12):
        self.stockfish_path = stockfish_path
        self.depth = depth

    def analyze_player(
        self,
        username: str,
        game_count: int = 200,
        workers: int = 4,
        months: int = 6,
        progress_callback: Callable[[dict], None] | None = None,
        cancellation_event: threading.Event | None = None,
        analysis_config: dict | None = None,
    ) -> dict[str, Any]:
        """
        Complete analysis pipeline for a player.

        1. Load existing data from JSON
        2. Fetch games from Chess.com
        3. Filter already-analyzed games (by URL)
        4. Parallel analysis with Stockfish
        5. Build game entries, merge with existing
        6. Compute aggregates via calculators
        7. Save to JSON
        """
        username = username.strip().lower()

        # Step 1: Load existing player data
        existing_data = load_player(username)
        existing_games = existing_data.get("games", []) if existing_data else []
        analyzed_urls = {g["url"] for g in existing_games if g.get("url")}

        # Step 2: Fetch games from Chess.com
        all_fetched = fetch_games(username, months=months)
        if not all_fetched:
            return {"total_fetched": 0, "new_analyses": 0, "failed_analyses": 0}

        # Limit to requested count (most recent)
        fetched = all_fetched[-game_count:]

        # Step 3: Filter — skip already analyzed + validate
        games_to_analyze = []
        stats = {
            "total_fetched": len(all_fetched),
            "already_analyzed": 0,
            "filtered_short": 0,
        }

        for game_data in fetched:
            metadata = extract_pgn_metadata(game_data["pgn"])
            url = metadata.get("url")
            if url and url in analyzed_urls:
                stats["already_analyzed"] += 1
                continue

            # Validate game quality
            try:
                GameDataValidator.validate_game_data(
                    game_data,
                    require_pgn=True,
                    require_move_times=True,
                    min_move_count=MIN_MOVES_THRESHOLD,
                )
            except Exception:
                stats["filtered_short"] += 1
                continue

            games_to_analyze.append({"game_data": game_data, "metadata": metadata})

        if not games_to_analyze:
            return {**stats, "new_analyses": 0, "failed_analyses": 0}

        # Step 4: Parallel analysis
        results = self._analyze_batch(
            games_to_analyze, username, workers, progress_callback,
            cancellation_event, analysis_config,
        )

        # Step 5: Build game entries from results
        new_games = []
        failed = 0
        for result in results:
            if not result.get("success"):
                failed += 1
                continue
            # The game_data is stashed in the result by _analyze_batch
            game_data = result.pop("_game_data", {})
            metadata = result.pop("_metadata", {})
            entry = self._build_game_entry(result, game_data, metadata, username)
            new_games.append(entry)

        # Merge with existing games
        all_games = existing_games + new_games

        # Step 6: Compute aggregates
        items = build_calculator_items(all_games, username)
        aggregates = self._compute_aggregates(items, all_games, username)

        # Step 7: Save
        from datetime import datetime

        player_data = {
            "username": username,
            "last_updated": datetime.utcnow().isoformat(),
            "games": all_games,
            "aggregates": aggregates,
        }
        save_player(player_data)

        return {
            **stats,
            "new_analyses": len(new_games),
            "failed_analyses": failed,
            "total_games": len(all_games),
        }

    def _build_game_entry(
        self, result: dict, game_data: dict, metadata: dict, username: str,
    ) -> dict:
        """Build a game dict for JSON storage from an analysis result."""
        topn = result.get("topn_rates", {}) or {}
        blunder_stats = result.get("blunder_stats", {}) or {}
        move_evals = result.get("move_evals", [])

        return {
            "url": metadata.get("url"),
            "date": metadata.get("date").isoformat() if metadata.get("date") else None,
            "pgn": game_data.get("pgn", ""),
            "white_username": metadata.get("white_username", ""),
            "black_username": metadata.get("black_username", ""),
            "white_elo": metadata.get("white_elo"),
            "black_elo": metadata.get("black_elo"),
            "time_control_seconds": metadata.get("time_control_seconds"),
            "time_control_category": categorize_time_control(metadata.get("time_control_seconds")),
            "result": metadata.get("result"),
            "move_times": game_data.get("move_times"),
            "clock_times": game_data.get("clock_times"),
            "analysis": {
                "acpl": result.get("acpl"),
                "move_count": len(move_evals) if move_evals else 0,
                "top1_match_rate": topn.get("top1"),
                "top2_match_rate": topn.get("top2"),
                "top3_match_rate": topn.get("top3"),
                "top4_match_rate": topn.get("top4"),
                "top5_match_rate": topn.get("top5"),
                "blunder_count": blunder_stats.get("blunder_count", 0),
                "blunder_rate": blunder_stats.get("blunder_rate", 0.0),
                "move_evals": move_evals,
                "phase_breakdown": result.get("phase_breakdown"),
                "time_analysis": result.get("time_analysis"),
                "precision_bursts": result.get("precision_bursts"),
                "time_complexity": result.get("time_complexity"),
                "enhanced_phase": result.get("enhanced_phase"),
                "psychological_momentum": result.get("psychological_momentum"),
                "difficulty_metrics": result.get("difficulty_metrics"),
                "stockfish_depth": result.get("depth"),
            },
        }

    def _compute_aggregates(
        self, items: list[dict], all_games: list[dict], username: str,
    ) -> dict:
        """Compute aggregates per time-control category + 'All'."""
        if not items:
            return {}

        # Group items by time control category
        grouped: dict[str, list[dict]] = {}
        for item in items:
            cat = item["game"].time_control_category or "Unknown"
            grouped.setdefault(cat, []).append(item)

        aggregates = {}

        # Per-category
        for category, cat_items in grouped.items():
            metrics = calculate_all(cat_items)
            suspicion = self._calculate_suspicion_score(metrics)
            metrics["suspicion_score"] = suspicion
            metrics["games_count"] = len(cat_items)
            aggregates[category] = metrics

        # "All" aggregate
        all_metrics = calculate_all(items)
        suspicion = self._calculate_suspicion_score(all_metrics)
        all_metrics["suspicion_score"] = suspicion
        all_metrics["games_count"] = len(items)
        aggregates["All"] = all_metrics

        return aggregates

    def _calculate_suspicion_score(self, metrics: dict) -> float:
        """Calculate composite suspicion score from flat metrics dict."""
        try:
            result = calculate_suspicion_score(
                anomaly_score_mean=metrics.get("anomaly_score_mean"),
                opening_to_middle_transition=metrics.get("opening_to_middle_transition"),
                collapse_rate=metrics.get("collapse_rate"),
                phase_consistency_middle=metrics.get("phase_consistency_middle"),
                robust_acpl=metrics.get("robust_acpl"),
                match_rate_mean=metrics.get("top5_match_rate_mean"),
                blunder_rate=metrics.get("blunder_rate_mean"),
                top2_match_rate=metrics.get("top2_match_rate_mean"),
                pressure_degradation=metrics.get("pressure_degradation"),
                tilt_rate=metrics.get("tilt_rate"),
                opening_to_middle_improvement=metrics.get("opening_to_middle_improvement"),
                variance_drop=metrics.get("variance_drop"),
                post_pause_improvement=metrics.get("post_pause_improvement"),
                cwmr_delta=metrics.get("cwmr_delta_mean"),
                cpa=metrics.get("cpa_mean"),
                sensitivity=metrics.get("sensitivity_mean"),
                ubma=metrics.get("ubma_mean"),
                difficulty_variance_ratio=metrics.get("variance_ratio_mean"),
                critical_accuracy_boost=metrics.get("critical_accuracy_boost_mean"),
                oscillation_score=metrics.get("oscillation_score_mean"),
                mismatch_rate=metrics.get("mismatch_rate_mean"),
                effort_ratio=metrics.get("effort_ratio_mean"),
            )
            return result["suspicion_score"]
        except Exception:
            return 0.0

    def _analyze_batch(
        self,
        games_to_analyze: list[dict],
        username: str,
        workers: int,
        progress_callback: Callable[[dict], None] | None = None,
        cancellation_event: threading.Event | None = None,
        analysis_config: dict | None = None,
    ) -> list[dict]:
        """Analyze multiple games in parallel."""
        results = []
        games_completed = 0
        total = len(games_to_analyze)

        # Prepare tasks — stash game_data/metadata alongside worker args
        tasks = []
        for item in games_to_analyze:
            tasks.append((
                item["game_data"],
                item["metadata"],
                username,
                self.stockfish_path,
                self.depth,
                analysis_config,
            ))

        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_to_task = {
                executor.submit(
                    _analyze_single_game_worker,
                    task[0], task[2], task[3], task[4], None, task[5],
                ): task
                for task in tasks
            }

            for future in as_completed(future_to_task):
                if cancellation_event and cancellation_event.is_set():
                    break

                task = future_to_task[future]
                try:
                    result = future.result()
                    # Stash original game_data and metadata for _build_game_entry
                    result["_game_data"] = task[0]
                    result["_metadata"] = task[1]
                    results.append(result)
                    games_completed += 1

                    if progress_callback:
                        progress_callback({
                            "username": username,
                            "games_analyzed": games_completed,
                            "games_requested": total,
                            "progress": (games_completed / total) * 100,
                        })
                except Exception as e:
                    results.append({
                        "success": False,
                        "error": f"Worker failed: {str(e)}",
                        "_game_data": task[0],
                        "_metadata": task[1],
                    })

        return results


def _analyze_single_game_worker(
    game_data: dict,
    username: str,
    stockfish_path: str,
    depth: int,
    trace_id: Optional[str] = None,
    analysis_config: Optional[dict] = None,
) -> dict:
    """
    Worker function for parallel game analysis.

    This function is defined at module level to work with multiprocessing.
    """
    from analysis.analysis_config import AnalysisConfig

    if analysis_config is None:
        config = AnalysisConfig.all_enabled()
    else:
        config = AnalysisConfig(**analysis_config)

    try:
        pgn = game_data["pgn"]

        try:
            move_times = require_move_times(game_data)
        except ValidationError as e:
            return {**e.to_dict(), "success": False}

        metadata = extract_pgn_metadata(pgn)
        is_white = metadata["white_username"].lower() == username.lower()
        player_elo = metadata["white_elo"] if is_white else metadata["black_elo"]

        # Analyze with Stockfish (multipv=5)
        player_color = "white" if is_white else "black"
        player_move_evals = analyze_game(
            pgn, stockfish_path=stockfish_path, depth=depth,
            multipv=5, player_color=player_color, skip_book_moves=True,
        )

        try:
            player_move_evals = require_move_evals(player_move_evals)
        except ValidationError as e:
            return {**e.to_dict(), "success": False}

        # Get ALL moves for time analysis context
        all_move_evals = analyze_game(
            pgn, stockfish_path=stockfish_path, depth=depth,
            multipv=5, player_color=None, skip_book_moves=False,
        )

        # Basic metrics
        acpl = None
        blunder_stats = None
        if config.basic_metrics:
            acpl = calculate_acpl(player_move_evals)
            blunder_stats = calculate_blunders(player_move_evals)

        topn_rates = None
        if config.topn_match_rates:
            topn_rates = calculate_topn_match_rates(player_move_evals)

        phase_breakdown = None
        precision_bursts = None
        enhanced_phase = None
        if config.basic_metrics:
            phase_breakdown = calculate_phase_metrics(pgn, player_move_evals)
            precision_bursts = calculate_precision_bursts(player_move_evals)
            enhanced_phase = calculate_enhanced_phase_analysis(pgn, player_move_evals)

        # Count actual book moves to skip in time data (instead of hardcoding 10)
        book_move_count = sum(
            1 for m in player_move_evals if isinstance(m, dict) and m.get("is_book_move")
        )

        # Time analysis
        time_analysis = None
        time_complexity = None
        player_times = []
        aligned_player_evals = player_move_evals

        if config.time_pressure or config.time_complexity_correlation:
            if config.time_pressure:
                time_analysis = calculate_time_pressure_metrics(
                    move_times, all_move_evals, is_white
                )

            if config.time_complexity_correlation:
                player_times = []
                move_counter = 0
                for i in range(0 if is_white else 1, len(move_times), 2):
                    if i < len(move_times):
                        move_counter += 1
                        if move_counter > book_move_count:
                            player_times.append(abs(move_times[i]))

                aligned_player_evals = player_move_evals[: len(player_times)]
                time_complexity = calculate_time_complexity_correlation(
                    aligned_player_evals, player_times
                )

        # Psychological momentum
        psychological_momentum = None
        if config.psychological_momentum:
            if not config.time_complexity_correlation:
                player_times = []
                move_counter = 0
                for i in range(0 if is_white else 1, len(move_times), 2):
                    if i < len(move_times):
                        move_counter += 1
                        if move_counter > book_move_count:
                            player_times.append(abs(move_times[i]))
                aligned_player_evals = player_move_evals[: len(player_times)]

            if aligned_player_evals:
                move_eval_losses = [
                    m.get("cp_loss", 0) for m in aligned_player_evals if isinstance(m, dict)
                ]

                player_clock_times = []
                clock_times = game_data.get("clock_times")
                if clock_times:
                    move_counter = 0
                    for i in range(0 if is_white else 1, len(clock_times), 2):
                        if i < len(clock_times):
                            move_counter += 1
                            if move_counter > book_move_count:
                                player_clock_times.append(clock_times[i])

                time_control = metadata.get("time_control", "blitz")
                aligned_player_clock_times = player_clock_times[: len(move_eval_losses)]

                psychological_momentum = analyze_psychological_momentum(
                    move_evals=move_eval_losses,
                    move_times=player_times,
                    clock_times=aligned_player_clock_times if aligned_player_clock_times else None,
                    time_control=time_control,
                )

        # Difficulty metrics
        difficulty_metrics = None
        if config.basic_metrics and player_move_evals:
            impossibility = calculate_human_impossibility_metrics(player_move_evals)
            toggle_times = None
            try:
                if player_times:
                    toggle_times = player_times
            except NameError:
                pass
            toggle = calculate_toggle_detection_metrics(player_move_evals, toggle_times)
            difficulty_metrics = {**impossibility, **toggle}

        return {
            "success": True,
            "metadata": metadata,
            "player_elo": player_elo,
            "is_white": is_white,
            "acpl": acpl,
            "topn_rates": topn_rates,
            "blunder_stats": blunder_stats,
            "move_evals": player_move_evals,
            "phase_breakdown": phase_breakdown,
            "time_analysis": time_analysis,
            "precision_bursts": precision_bursts,
            "time_complexity": time_complexity,
            "enhanced_phase": enhanced_phase,
            "psychological_momentum": psychological_momentum,
            "difficulty_metrics": difficulty_metrics,
            "depth": depth,
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
