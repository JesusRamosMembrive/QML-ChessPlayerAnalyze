"""
Phase 1B metrics calculator.

Calculates advanced temporal detection metrics including opening-to-middle
improvement, variance drops, and post-pause performance changes.
"""

from typing import Any

from analysis.phase_analysis import calculate_phase_variance
from analysis.time_analysis import detect_post_pause_quality
from services.calculators.base import MetricCalculator
from utils import get_logger
from utils.json_parser import JSONFieldParser
from utils.stat_utils import StatUtils

logger = get_logger(__name__)


class Phase1BMetricsCalculator(MetricCalculator):
    """
    Calculator for Phase 1B advanced temporal detection metrics.

    This calculator processes phase-based and time-based data to detect:
    - Opening-to-middle improvement: Suspicious ACPL improvement from opening
      to middlegame (engines perform consistently across phases)
    - Variance drop: Consistency increase from opening to middlegame
      (engines have consistent variance)
    - Post-pause improvement: ACPL improvement after long pauses
      (suspicious if player performs better after pauses)

    These metrics help detect patterns inconsistent with human play.
    """

    def calculate(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Calculate Phase 1B temporal detection metrics.

        Args:
            items: List of game-analysis pairs containing:
                   - analysis.move_evals: Move evaluation data
                   - analysis.phase_breakdown: Phase-specific metrics
                   - game.pgn: PGN text for phase detection
                   - game.move_times: Move time data
                   - game.white_username, game.username: For color determination

        Returns:
            Dictionary with Phase 1B metric fields:
            - opening_to_middle_improvement: Avg ACPL improvement opening→middle
            - variance_drop: Avg std dev drop opening→middle (consistency increase)
            - post_pause_improvement: Avg ACPL improvement after long pauses
        """
        opening_to_middle_improvements = []
        variance_drops = []
        post_pause_improvements = []

        for item in items:
            analysis = item["analysis"]
            game = item["game"]

            # Parse move_evals JSON field
            move_evals = JSONFieldParser.parse_field(analysis, "move_evals", default=None)
            if not move_evals:
                continue

            # Parse phase_breakdown JSON field
            phase_breakdown = JSONFieldParser.parse_field(analysis, "phase_breakdown", default=None)
            if not phase_breakdown:
                continue

            # Get PGN text for phase analysis
            pgn_text = game.pgn
            if not pgn_text:
                continue

            # 1. Calculate phase variance (for variance_drop and opening_to_middle_improvement)
            variance_result = calculate_phase_variance(
                pgn_text=pgn_text,
                move_evals=move_evals,
                opening_moves=15,
                endgame_pieces=6,
            )

            # Variance drop (consistency increase)
            if variance_result["variance_drop"] is not None:
                variance_drops.append(variance_result["variance_drop"])

            # Opening to middle improvement (ACPL improvement = opening worse than middle)
            # Calculate from phase_breakdown
            opening_acpl = phase_breakdown.get("opening", {}).get("acpl")
            middle_acpl = phase_breakdown.get("middlegame", {}).get("acpl")

            if (
                opening_acpl is not None
                and middle_acpl is not None
                and opening_acpl > 0
                and middle_acpl > 0
            ):
                # Improvement = opening ACPL - middlegame ACPL
                # Positive = got better (suspicious)
                improvement = opening_acpl - middle_acpl
                if improvement > 0:  # Only count improvements
                    opening_to_middle_improvements.append(improvement)

            # 2. Calculate post-pause improvement
            # Parse move_times from Game table
            move_times = JSONFieldParser.parse_field(game, "move_times", default=None)
            if move_times:
                # Determine player color
                is_white = game.white_username.lower() == game.username.lower()

                pause_result = detect_post_pause_quality(
                    move_times=move_times,
                    move_evals=move_evals,
                    is_white=is_white,
                    pause_threshold=30,
                )

                # Post-pause improvement
                if pause_result["improvement_after_pause"] is not None:
                    post_pause_improvements.append(pause_result["improvement_after_pause"])

        logger.info(
            f"Phase 1B metrics aggregated: {len(opening_to_middle_improvements)} improvements, "
            f"{len(variance_drops)} variance drops, {len(post_pause_improvements)} pause improvements"
        )

        return {
            "opening_to_middle_improvement": StatUtils.mean(opening_to_middle_improvements),
            "variance_drop": StatUtils.mean(variance_drops),
            "post_pause_improvement": StatUtils.mean(post_pause_improvements),
        }

    @property
    def calculator_name(self) -> str:
        """Return calculator identifier."""
        return "phase_1b_metrics"
