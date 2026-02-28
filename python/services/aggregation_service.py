"""
Aggregation Service.

Calculates and persists player aggregate statistics from game analyses.
"""

import json
from datetime import datetime

from sqlmodel import Session

from analysis.suspicion import calculate_suspicion_score
from database import Game, GameAnalysis, PlayerAggregate
from repositories import AggregateRepository, AnalysisRepository, GameRepository
from services.calculators.advanced_metrics import AdvancedMetricsCalculator
from services.calculators.basic_stats import BasicStatsCalculator
from services.calculators.difficulty_metrics import DifficultyMetricsCalculator
from services.calculators.historical import HistoricalCalculator
from services.calculators.phase_1b_metrics import Phase1BMetricsCalculator
from services.calculators.phase_metrics import PhaseMetricsCalculator
from services.calculators.precision_metrics import PrecisionMetricsCalculator
from services.calculators.psychological import PsychologicalCalculator
from services.calculators.registry import CalculatorRegistry
from services.calculators.time_metrics import TimeMetricsCalculator
from utils import get_logger

logger = get_logger(__name__)


class AggregationService:
    """
    Service for calculating player aggregate statistics.

    Responsibilities:
    - Group analyses by time control category
    - Orchestrate metric calculation through CalculatorRegistry
    - Calculate composite suspicion score from aggregated metrics
    - Save/update PlayerAggregate records
    """

    METRIC_GROUP_KEYS = {
        "basic": [
            "acpl_mean", "acpl_median", "acpl_std", "acpl_min", "acpl_max",
            "acpl_p25", "acpl_p75",
            "top1_match_rate_mean", "top1_match_rate_std", "top1_match_rate_min", "top1_match_rate_max",
            "top2_match_rate_mean", "top2_match_rate_std", "top2_match_rate_min", "top2_match_rate_max",
            "top3_match_rate_mean", "top3_match_rate_std", "top3_match_rate_min", "top3_match_rate_max",
            "top4_match_rate_mean", "top4_match_rate_std", "top4_match_rate_min", "top4_match_rate_max",
            "top5_match_rate_mean", "top5_match_rate_std", "top5_match_rate_min", "top5_match_rate_max",
            "blunder_rate_mean", "blunder_rate_std",
            "move_count_mean", "move_count_median",
        ],
        "advanced": [
            "robust_acpl", "rank_0_mean", "rank_1_mean", "rank_2_mean", "rank_3plus_mean",
        ],
        "precision": [
            "precision_burst_mean", "longest_burst_mean", "precision_rate_mean",
        ],
        "phase": [
            "opening_to_middle_transition", "middle_to_endgame_transition",
            "collapse_rate",
            "phase_consistency_opening", "phase_consistency_middle", "phase_consistency_endgame",
        ],
        "time": [
            "time_complexity_correlation", "anomaly_score_mean",
        ],
        "psych": [
            "tilt_rate", "recovery_rate", "closing_acpl", "pressure_degradation",
        ],
        "phase_1b": [
            "opening_to_middle_improvement", "variance_drop", "post_pause_improvement",
        ],
        "difficulty": [
            "cwmr_mean", "cwmr_delta_mean", "cpa_mean", "sensitivity_mean", "ubma_mean",
            "variance_ratio_mean", "critical_accuracy_boost_mean", "oscillation_score_mean",
            "mismatch_rate_mean", "effort_ratio_mean", "avg_sharpness_mean",
        ],
    }

    HISTORICAL_KEYS = ["acpl_timeline", "match_rate_timeline", "elo_timeline", "games_count"]

    def __init__(self, session: Session):
        """
        Initialize aggregation service.

        Args:
            session: SQLModel database session
        """
        self.session = session

        # Initialize repositories
        self.game_repo = GameRepository(session)
        self.analysis_repo = AnalysisRepository(session)
        self.aggregate_repo = AggregateRepository(session)

        # Initialize calculator registry with all metric calculators
        self.calculator_registry = CalculatorRegistry()
        self.calculator_registry.register(BasicStatsCalculator())
        self.calculator_registry.register(AdvancedMetricsCalculator())
        self.calculator_registry.register(PrecisionMetricsCalculator())
        self.calculator_registry.register(PhaseMetricsCalculator())
        self.calculator_registry.register(TimeMetricsCalculator())
        self.calculator_registry.register(PsychologicalCalculator())
        self.calculator_registry.register(Phase1BMetricsCalculator())
        self.calculator_registry.register(DifficultyMetricsCalculator())
        self.calculator_registry.register(HistoricalCalculator(max_games=50))

    def recalculate_aggregates(
        self,
        username: str,
        time_control_filter: str | None = None,
        window_analysis: dict | None = None,
        window_id: int = 0,
        window_range: tuple[int, int] | None = None,
    ) -> list[PlayerAggregate]:
        """
        Calculate and save aggregate statistics for a player.

        Args:
            username: Chess.com username
            time_control_filter: Optional filter by time control category (Bullet/Blitz/Rapid)
            window_analysis: Optional window analysis results from Phase 1 (lightweight pre-screening)
            window_id: Window ID (0 = full analysis, 1+ = window analysis)
            window_range: Optional (start_idx, end_idx) for window analysis

        Returns:
            List of PlayerAggregate records created/updated

        Raises:
            ValueError: If no games or analyses found for player
        """
        # Get games and analyses
        all_games = self.game_repo.get_by_username(username)
        if not all_games:
            raise ValueError(f"No games found for {username}")

        analyses = self.analysis_repo.get_by_username(username)
        if not analyses:
            raise ValueError(f"No analyses found for {username}")

        # Filter by window range if provided
        if window_range:
            # Sort games by date (descending) to match window detection indexing
            sorted_games = sorted(all_games, key=lambda g: g.date, reverse=True)

            # Extract games in window range
            start_idx, end_idx = window_range
            window_games = sorted_games[start_idx : end_idx + 1]
            window_game_ids = {game.id for game in window_games}

            # Filter analyses to only those for games in the window
            analyses = [a for a in analyses if a.game_id in window_game_ids]
            games = window_games

            logger.info(
                f"Window mode: filtered to {len(analyses)} analyses from {len(games)} games "
                f"(indices {start_idx}-{end_idx})"
            )
        else:
            games = all_games

        # Group by time control
        grouped = self._group_by_time_control(analyses, games, time_control_filter)

        if not grouped:
            raise ValueError(f"No analyses match filter: {time_control_filter}")

        # Calculate aggregates for each category
        aggregates = []
        for category, items in grouped.items():
            aggregate = self._calculate_and_save_aggregate(
                username, category, items, window_analysis, window_id, window_range
            )
            aggregates.append(aggregate)

        # If no filter, also calculate "All" aggregate combining all time controls
        if not time_control_filter:
            all_items = []
            for items in grouped.values():
                all_items.extend(items)

            all_aggregate = self._calculate_and_save_aggregate(
                username, "All", all_items, window_analysis, window_id, window_range
            )
            aggregates.append(all_aggregate)

        return aggregates

    def _group_by_time_control(
        self,
        analyses: list[GameAnalysis],
        games: list[Game],
        time_control_filter: str | None,
    ) -> dict[str, list[dict]]:
        """
        Group analyses by time control category.

        Args:
            analyses: List of GameAnalysis objects
            games: List of Game objects
            time_control_filter: Optional filter

        Returns:
            Dict mapping category -> list of {analysis, game} dicts
        """
        # Build game lookup
        game_lookup = {game.id: game for game in games}

        grouped = {}
        for analysis in analyses:
            game = game_lookup.get(analysis.game_id)
            if not game:
                continue

            category = game.time_control_category or "Unknown"

            # Apply filter
            if time_control_filter and category != time_control_filter:
                continue

            if category not in grouped:
                grouped[category] = []

            grouped[category].append({"analysis": analysis, "game": game})

        return grouped

    def _calculate_and_save_aggregate(
        self,
        username: str,
        category: str,
        items: list[dict],
        window_analysis: dict | None = None,
        window_id: int = 0,
        window_range: tuple[int, int] | None = None,
    ) -> PlayerAggregate:
        """
        Calculate aggregate statistics for a category and save to database.

        ARCHITECTURE CHANGE (Per-Window Scoring):
        - Detects suspicious windows PER CATEGORY (not globally)
        - Each window gets its own complete analysis (prevents score dilution)
        - Detects ego-based cyclic cheating patterns (gaps > 20 games between windows)
        - If no windows, calculate global aggregate (legacy path)

        Args:
            username: Player username
            category: Time control category
            items: List of dicts with {analysis: GameAnalysis, game: Game}
            window_analysis: Optional window analysis results from Phase 1 (IGNORED - we detect per-category)
            window_id: Window ID (0 = full analysis, 1+ = window analysis)
            window_range: Optional (start_idx, end_idx) for window analysis

        Returns:
            PlayerAggregate record (created or updated)
        """
        # Run window detection PER CATEGORY to get correct indices
        category_window_analysis = self._detect_windows_for_category(username, category, items)

        # Extract suspicious windows from category-specific detection
        # Note: Windows come as WindowMetrics objects, extract [start_index, end_index]
        suspicious_windows = []
        if category_window_analysis:
            for key in ["elo_slope", "win_streaks", "performance_bursts"]:
                if key in category_window_analysis and category_window_analysis[key]:
                    method_windows = category_window_analysis[key].get("suspicious_windows", [])
                    # Convert WindowMetrics to [start, end] tuples
                    for window in method_windows:
                        suspicious_windows.append([window["start_index"], window["end_index"]])

        # Merge overlapping windows
        suspicious_windows = self._merge_overlapping_windows(suspicious_windows)

        logger.info(
            f"[{category}] Extracted {len(suspicious_windows)} suspicious windows "
            f"from category_window_analysis"
        )
        if suspicious_windows:
            logger.info(f"[{category}] Suspicious windows: {suspicious_windows}")

        # If we have suspicious windows, calculate per-window aggregates
        if suspicious_windows:
            logger.info(
                f"Found {len(suspicious_windows)} suspicious windows for category {category} "
                f"({len(items)} games)"
            )
            return self._calculate_windowed_aggregate(
                username, category, items, category_window_analysis, suspicious_windows,
                window_id, window_range
            )

        # No suspicious windows - calculate global aggregate (legacy path)
        # Calculate all metrics using registry (replaces 750+ LOC of individual methods)
        all_metrics = self.calculator_registry.calculate_all(items)

        # Extract metric groups and historical data
        groups = self._extract_metric_groups(all_metrics)
        historical_data = {k: all_metrics[k] for k in self.HISTORICAL_KEYS if k in all_metrics}

        # Calculate suspicion score (orchestration logic - integrates calculator results)
        suspicion_score = self._calculate_suspicion_score(groups)

        # Date range
        dates = [item["game"].date for item in items]
        first_game_date = min(dates)
        last_game_date = max(dates)

        # Save or update aggregate
        return self._save_or_update_aggregate(
            username, category, len(items), groups, historical_data,
            suspicion_score, first_game_date, last_game_date,
            window_analysis, window_id, window_range,
        )

    def _calculate_suspicion_score(self, groups: dict[str, dict]) -> float:
        """Calculate composite suspicion score from metric groups."""
        basic = groups.get("basic", {})
        advanced = groups.get("advanced", {})
        phase = groups.get("phase", {})
        time = groups.get("time", {})
        psych = groups.get("psych", {})
        phase_1b = groups.get("phase_1b", {})
        difficulty = groups.get("difficulty", {})

        try:
            suspicion_result = calculate_suspicion_score(
                anomaly_score_mean=time.get("anomaly_score_mean"),
                opening_to_middle_transition=phase.get("opening_to_middle_transition"),
                collapse_rate=phase.get("collapse_rate"),
                phase_consistency_middle=phase.get("phase_consistency_middle"),
                robust_acpl=advanced.get("robust_acpl"),
                match_rate_mean=basic.get("top5_match_rate_mean"),
                blunder_rate=basic.get("blunder_rate_mean"),
                top2_match_rate=basic.get("top2_match_rate_mean"),
                pressure_degradation=psych.get("pressure_degradation"),
                tilt_rate=psych.get("tilt_rate"),
                opening_to_middle_improvement=phase_1b.get("opening_to_middle_improvement"),
                variance_drop=phase_1b.get("variance_drop"),
                post_pause_improvement=phase_1b.get("post_pause_improvement"),
                cwmr_delta=difficulty.get("cwmr_delta_mean"),
                cpa=difficulty.get("cpa_mean"),
                sensitivity=difficulty.get("sensitivity_mean"),
                ubma=difficulty.get("ubma_mean"),
                difficulty_variance_ratio=difficulty.get("variance_ratio_mean"),
                critical_accuracy_boost=difficulty.get("critical_accuracy_boost_mean"),
                oscillation_score=difficulty.get("oscillation_score_mean"),
                mismatch_rate=difficulty.get("mismatch_rate_mean"),
                effort_ratio=difficulty.get("effort_ratio_mean"),
            )
            return suspicion_result["suspicion_score"]
        except Exception:
            return 0.0

    def _save_or_update_aggregate(
        self,
        username: str,
        category: str,
        games_count: int,
        groups: dict[str, dict],
        historical_data: dict,
        suspicion_score: float,
        first_game_date: datetime,
        last_game_date: datetime,
        window_analysis: dict | None = None,
        window_id: int = 0,
        window_range: tuple[int, int] | None = None,
    ) -> PlayerAggregate:
        """Save or update PlayerAggregate record."""
        existing = self.aggregate_repo.get_by_username_and_time_control(username, category, window_id)

        if existing:
            self._update_aggregate_fields(
                existing, games_count, groups, historical_data,
                suspicion_score, first_game_date, last_game_date,
                window_analysis, window_range,
            )
            return self.aggregate_repo.update(existing)
        else:
            # Merge all group stats, filtering None values for optional fields
            # basic group is always fully populated; other groups may have None values
            all_stats = {}
            for group_name, group_stats in groups.items():
                if group_name == "basic":
                    all_stats.update(group_stats)
                else:
                    all_stats.update({k: v for k, v in group_stats.items() if v is not None})

            aggregate = PlayerAggregate(
                username=username,
                time_control_category=category,
                window_id=window_id,
                window_start_game=window_range[0] if window_range else None,
                window_end_game=window_range[1] if window_range else None,
                games_count=games_count,
                **all_stats,
                historical_data=json.dumps(historical_data),
                window_analysis=json.dumps(window_analysis) if window_analysis else None,
                suspicion_score=suspicion_score,
                first_game_date=first_game_date,
                last_game_date=last_game_date,
            )
            return self.aggregate_repo.create(aggregate)

    def _update_aggregate_fields(
        self,
        aggregate: PlayerAggregate,
        games_count: int,
        groups: dict[str, dict],
        historical_data: dict,
        suspicion_score: float,
        first_game_date: datetime,
        last_game_date: datetime,
        window_analysis: dict | None = None,
        window_range: tuple[int, int] | None = None,
    ):
        """Update fields on existing PlayerAggregate."""
        aggregate.games_count = games_count

        if window_range:
            aggregate.window_start_game = window_range[0]
            aggregate.window_end_game = window_range[1]

        for group_stats in groups.values():
            for key, value in group_stats.items():
                setattr(aggregate, key, value)

        aggregate.historical_data = json.dumps(historical_data)
        aggregate.window_analysis = json.dumps(window_analysis) if window_analysis else None
        aggregate.suspicion_score = suspicion_score
        aggregate.first_game_date = first_game_date
        aggregate.last_game_date = last_game_date

    def _detect_windows_for_category(
        self, username: str, category: str, items: list[dict]
    ) -> dict | None:
        """
        Detect suspicious windows for a specific time control category.

        This runs Phase 1 window detection on ONLY the games in this category,
        ensuring that window indices correspond exactly to the games in items.

        Args:
            username: Player username
            category: Time control category (Bullet/Blitz/Rapid/All)
            items: List of {analysis: GameAnalysis, game: Game} dicts for this category

        Returns:
            Window analysis dict with category-specific suspicious windows, or None
        """
        if len(items) < 20:
            # Not enough games for meaningful window analysis
            logger.info(
                f"Skipping window detection for {category}: only {len(items)} games (need 20+)"
            )
            return None

        from analysis.temporal_windows import (
            calculate_elo_slope,
            detect_performance_bursts,
            detect_win_streaks,
        )

        # Convert items to format expected by temporal_windows functions
        # Sort by game date to ensure chronological order
        sorted_items = sorted(items, key=lambda x: x["game"].date)

        game_dicts = []
        for item in sorted_items:
            game = item["game"]
            analysis = item["analysis"]

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
                    "game_id": game.id,
                    "acpl": analysis.acpl,  # ← FIX: Add ACPL for detect_performance_bursts()
                }
            )

        logger.info(
            f"Running window detection for {category}: {len(game_dicts)} games"
        )

        # Run lightweight window detection algorithms
        elo_result = calculate_elo_slope(
            game_dicts, window_size=20, slope_threshold=10.0
        )

        win_result = detect_win_streaks(
            game_dicts, window_size=20, winrate_threshold=0.85, min_games=10
        )

        burst_result = detect_performance_bursts(
            game_dicts,
            window_size=20,
            elo_slope_threshold=8.0,
            winrate_threshold=0.80,
            acpl_threshold=15.0,
        )

        # Build window analysis structure
        # Convert @dataclass results to dicts for JSON serialization
        from dataclasses import asdict

        def convert_datetime_to_iso(obj):
            """Recursively convert datetime objects to ISO format strings."""
            if isinstance(obj, dict):
                return {k: convert_datetime_to_iso(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime_to_iso(item) for item in obj]
            elif hasattr(obj, 'isoformat'):  # datetime objects
                return obj.isoformat()
            else:
                return obj

        window_analysis = {
            "elo_slope": convert_datetime_to_iso(asdict(elo_result)) if elo_result.suspicious_windows else None,
            "win_streaks": convert_datetime_to_iso(asdict(win_result)) if win_result.suspicious_windows else None,
            "performance_bursts": convert_datetime_to_iso(asdict(burst_result))
            if burst_result.suspicious_windows
            else None,
            "games_filtered": 0,  # Will be calculated later
            "games_analyzed": len(items),
            "total_games": len(items),
            "time_saved_percentage": None,
        }

        # Count suspicious windows
        total_suspicious = 0
        for key in ["elo_slope", "win_streaks", "performance_bursts"]:
            if window_analysis[key]:
                total_suspicious += len(
                    window_analysis[key].get("suspicious_windows", [])
                )

        logger.info(
            f"Window detection for {category}: Found {total_suspicious} suspicious window ranges"
        )

        return window_analysis if total_suspicious > 0 else None

    def _merge_overlapping_windows(self, windows: list[list[int]]) -> list[list[int]]:
        """
        Merge overlapping or adjacent windows.

        Args:
            windows: List of [start, end] ranges

        Returns:
            List of merged non-overlapping windows
        """
        if not windows:
            return []

        # Sort by start index
        sorted_windows = sorted(windows, key=lambda w: w[0])

        merged = [sorted_windows[0]]
        for current in sorted_windows[1:]:
            last = merged[-1]
            # If windows overlap or are adjacent (gap <= 5 games), merge them
            if current[0] <= last[1] + 5:
                merged[-1] = [last[0], max(last[1], current[1])]
            else:
                merged.append(current)

        return merged

    def _detect_ego_pattern(self, windows: list[list[int]]) -> bool:
        """
        Detect ego-based cyclic cheating pattern.

        Pattern: cheat → climb ELO → normal play → drop ELO → cheat again
        Detection: Multiple suspicious windows with gaps > 20 games between them

        Args:
            windows: List of suspicious windows [start, end]

        Returns:
            True if ego cycling pattern detected
        """
        if len(windows) < 2:
            return False

        # Check for gaps > 20 games between windows
        for i in range(len(windows) - 1):
            gap = windows[i + 1][0] - windows[i][1]
            if gap > 20:
                logger.info(
                    f"Ego cycling pattern detected: {gap} game gap between "
                    f"windows {windows[i]} and {windows[i+1]}"
                )
                return True

        return False

    def _filter_items_by_window(
        self, items: list[dict], window_start: int, window_end: int
    ) -> list[dict]:
        """
        Filter items to only include games within the specified window.

        IMPORTANT: Window indices come from Phase 1 (ALL games including short ones),
        but items only contains games that were analyzed (short games filtered out).
        We need to map indices from the full game list to the analyzed game list.

        Args:
            items: List of {analysis: GameAnalysis, game: Game} dicts (ONLY analyzed games)
            window_start: Start game index in FULL game list (inclusive)
            window_end: End game index in FULL game list (inclusive)

        Returns:
            Filtered list of items that fall within the window date range
        """
        # Sort items by game date to get chronological order
        sorted_items = sorted(items, key=lambda x: x["game"].date)

        if not sorted_items:
            return []

        # Get date range of the window from the game repository
        # Window indices refer to the FULL game list, so we need to:
        # 1. Get all games (including short ones) from the repository
        # 2. Find the date range for the window
        # 3. Filter items by that date range

        # For now, use a simpler approach: Use indices directly on sorted_items
        # This assumes window indices have already been adjusted for filtered games
        # TODO: Proper index mapping from full game list to filtered game list

        # Check if window is out of bounds
        if window_start >= len(sorted_items):
            logger.warning(
                f"Window start {window_start} >= items length {len(sorted_items)}, "
                "returning empty list"
            )
            return []

        # Adjust end index if it exceeds list length
        actual_end = min(window_end, len(sorted_items) - 1)

        if actual_end < window_start:
            logger.warning(
                f"Adjusted window end {actual_end} < start {window_start}, "
                "returning empty list"
            )
            return []

        # Filter by adjusted index range (0-based indexing)
        window_items = sorted_items[window_start : actual_end + 1]

        logger.info(
            f"Window [{window_start}-{window_end}] mapped to "
            f"{len(window_items)} games in analyzed set (indices {window_start}-{actual_end})"
        )

        return window_items

    def _calculate_windowed_aggregate(
        self,
        username: str,
        category: str,
        items: list[dict],
        window_analysis: dict,
        suspicious_windows: list[list[int]],
        window_id: int = 0,
        window_range: tuple[int, int] | None = None,
    ) -> PlayerAggregate:
        """
        Calculate per-window aggregates for suspicious windows.

        This prevents score dilution by calculating independent suspicion scores
        for each suspicious window instead of averaging across all games.

        Args:
            username: Player username
            category: Time control category
            items: All game items for this category
            window_analysis: Phase 1 window detection results
            suspicious_windows: Merged list of suspicious windows [[start, end], ...]

        Returns:
            PlayerAggregate with window_scores populated
        """
        logger.info(
            f"Calculating per-window aggregates for {len(suspicious_windows)} windows"
        )

        window_scores = []
        max_suspicion_score = 0.0

        # Calculate aggregate for each window independently
        for window_range in suspicious_windows:
            window_start, window_end = window_range

            # Filter items to this window
            window_items = self._filter_items_by_window(items, window_start, window_end)

            if not window_items:
                logger.warning(f"No games found for window {window_range}, skipping")
                continue

            logger.info(
                f"Analyzing window {window_range}: {len(window_items)} games"
            )

            # Calculate metrics for this window
            window_metrics = self.calculator_registry.calculate_all(window_items)

            # Extract metric groups
            groups = self._extract_metric_groups(window_metrics)
            basic = groups.get("basic", {})
            precision = groups.get("precision", {})
            time_g = groups.get("time", {})
            phase = groups.get("phase", {})
            psych = groups.get("psych", {})
            phase_1b = groups.get("phase_1b", {})
            difficulty = groups.get("difficulty", {})

            # Calculate suspicion score for THIS WINDOW ONLY (not averaged!)
            window_suspicion_score = self._calculate_suspicion_score(groups)

            # Track max score across all windows
            max_suspicion_score = max(max_suspicion_score, window_suspicion_score)

            # Get date range for window
            dates = [item["game"].date for item in window_items]
            first_date = min(dates)
            last_date = max(dates)

            # Build WindowScore structure
            window_score = {
                "game_range": window_range,
                "games_count": len(window_items),
                "basic_info": {
                    "games_count": len(window_items),
                    "move_count_mean": basic.get("move_count_mean", 0.0),
                    "move_count_median": basic.get("move_count_median", 0.0),
                    "first_game_date": first_date.isoformat(),
                    "last_game_date": last_date.isoformat(),
                },
                "quality_metrics": {
                    "acpl_mean": basic.get("acpl_mean", 0.0),
                    "acpl_median": basic.get("acpl_median", 0.0),
                    "acpl_std": basic.get("acpl_std", 0.0),
                },
                "move_quality": {
                    "top1_match_rate_mean": basic.get("top1_match_rate_mean", 0.0),
                    "top5_match_rate_mean": basic.get("top5_match_rate_mean", 0.0),
                    "blunder_rate_mean": basic.get("blunder_rate_mean", 0.0),
                },
                "precision_analysis": {
                    "precision_burst_mean": precision.get("precision_burst_mean", 0.0),
                    "longest_burst_mean": precision.get("longest_burst_mean", 0.0),
                    "precision_rate_mean": precision.get("precision_rate_mean", 0.0),
                },
                "time_complexity": {
                    "time_complexity_correlation": time_g.get("time_complexity_correlation", 0.0),
                    "anomaly_score_mean": time_g.get("anomaly_score_mean", 0.0),
                },
                "phase_analysis": {
                    "opening_to_middle_transition": phase.get("opening_to_middle_transition", 0.0),
                    "middle_to_endgame_transition": phase.get("middle_to_endgame_transition", 0.0),
                    "collapse_rate": phase.get("collapse_rate", 0.0),
                },
                "suspicion": {
                    "score": window_suspicion_score,
                    "risk_level": self._get_risk_level(window_suspicion_score),
                },
                "psychological": {
                    "tilt_rate": psych.get("tilt_rate", 0.0),
                    "recovery_rate": psych.get("recovery_rate", 0.0),
                    "closing_acpl": psych.get("closing_acpl", 0.0),
                    "pressure_degradation": psych.get("pressure_degradation", 0.0),
                },
                "temporal_detection": (
                    {
                        "opening_to_middle_improvement": phase_1b.get("opening_to_middle_improvement"),
                        "variance_drop": phase_1b.get("variance_drop"),
                        "post_pause_improvement": phase_1b.get("post_pause_improvement"),
                    }
                    if any(phase_1b.values())
                    else None
                ),
                "difficulty_metrics": (
                    {
                        "cwmr_delta": difficulty.get("cwmr_delta_mean"),
                        "cpa": difficulty.get("cpa_mean"),
                        "sensitivity": difficulty.get("sensitivity_mean"),
                        "ubma": difficulty.get("ubma_mean"),
                        "variance_ratio": difficulty.get("variance_ratio_mean"),
                        "critical_accuracy_boost": difficulty.get("critical_accuracy_boost_mean"),
                        "oscillation_score": difficulty.get("oscillation_score_mean"),
                        "mismatch_rate": difficulty.get("mismatch_rate_mean"),
                        "avg_sharpness": difficulty.get("avg_sharpness_mean"),
                    }
                    if any(v is not None for v in difficulty.values())
                    else None
                ),
            }

            window_scores.append(window_score)

        # Detect ego cycling pattern
        ego_pattern = self._detect_ego_pattern(suspicious_windows)

        # Update window_analysis with new fields
        enhanced_window_analysis = {
            **(window_analysis or {}),
            "window_scores": window_scores,
            "max_suspicion_score": max_suspicion_score,
            "suspicious_windows_count": len(suspicious_windows),
            "ego_pattern_detected": ego_pattern,
        }

        # For the main PlayerAggregate record, use the highest window score
        # This ensures the player is flagged appropriately in the UI
        dates = [item["game"].date for item in items]
        first_game_date = min(dates)
        last_game_date = max(dates)

        # Use global metrics for the aggregate (for historical continuity)
        # but suspicion_score reflects the max window score
        all_metrics = self.calculator_registry.calculate_all(items)
        groups = self._extract_metric_groups(all_metrics)
        historical_data = {k: all_metrics[k] for k in self.HISTORICAL_KEYS if k in all_metrics}

        # Save with enhanced window analysis and max suspicion score
        return self._save_or_update_aggregate(
            username, category, len(items), groups, historical_data,
            max_suspicion_score, first_game_date, last_game_date,
            enhanced_window_analysis, window_id, window_range,
        )

    def _extract_metric_groups(self, metrics: dict) -> dict[str, dict]:
        """
        Extract and organize metrics into named groups.

        Returns:
            Dict mapping group name -> {metric_key: value} for keys present in metrics.
        """
        return {
            group: {k: metrics[k] for k in keys if k in metrics}
            for group, keys in self.METRIC_GROUP_KEYS.items()
        }

    def _get_risk_level(self, suspicion_score: float) -> str:
        """
        Get risk level label for suspicion score.

        Args:
            suspicion_score: Suspicion score (0-300)

        Returns:
            Risk level string
        """
        if suspicion_score < 80:
            return "LOW"
        elif suspicion_score < 130:
            return "MODERATE"
        elif suspicion_score < 180:
            return "HIGH"
        else:
            return "VERY HIGH"
