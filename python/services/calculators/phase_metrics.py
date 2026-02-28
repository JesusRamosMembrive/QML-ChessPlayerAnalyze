"""
Phase metrics calculator.

Calculates phase transition and consistency metrics for detecting
suspicious performance patterns.
"""

from typing import Any

from services.calculators.base import MetricCalculator
from utils import get_logger
from utils.json_parser import JSONFieldParser
from utils.stat_utils import StatUtils

logger = get_logger(__name__)


class PhaseMetricsCalculator(MetricCalculator):
    """
    Calculator for phase transition and consistency metrics.

    This calculator processes phase-based data to detect suspicious patterns:
    - Signal 2: Phase Transition - Opening → middlegame ACPL change
      (engines improve, humans deteriorate)
    - Signal 3: Collapse Rate - % games with sudden worsening >50cp
      (humans collapse, engines don't)
    - Signal 4: Phase Consistency - Variance within each game phase
      (engines are consistent, humans vary)

    Phase transitions:
    - Positive transition = deterioration (normal human pattern)
    - Negative transition = improvement (suspicious - "turns on engine")
    """

    def calculate(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Calculate phase transition and consistency metrics.

        Args:
            items: List of analysis items containing:
                   - analysis.phase_breakdown: Phase-specific ACPL data
                   - analysis.enhanced_phase: Phase consistency scores

        Returns:
            Dictionary with phase metric fields:
            - opening_to_middle_transition: Avg ACPL change opening→middle
            - middle_to_endgame_transition: Avg ACPL change middle→endgame
            - collapse_rate: Rate of transitions >50cp (0-1)
            - phase_consistency_opening: Avg consistency score opening (0-100)
            - phase_consistency_middle: Avg consistency score middle (0-100)
            - phase_consistency_endgame: Avg consistency score endgame (0-100)
        """
        opening_to_middle_transitions = []
        middle_to_end_transitions = []
        collapses = []

        # For Signal 4: Phase Consistency - collect from enhanced_phase
        opening_consistency_scores = []
        middle_consistency_scores = []
        endgame_consistency_scores = []

        for item in items:
            analysis = item["analysis"]

            # Parse phase_breakdown JSON field
            phase_data = JSONFieldParser.parse_field(analysis, "phase_breakdown", default={})
            if not phase_data:
                continue

            # Extract ACPLs for each phase using safe nested get
            opening_acpl = JSONFieldParser.safe_get_nested(phase_data, "opening", "acpl")
            middle_acpl = JSONFieldParser.safe_get_nested(phase_data, "middlegame", "acpl")
            endgame_acpl = JSONFieldParser.safe_get_nested(phase_data, "endgame", "acpl")

            # Signal 2: Opening to Middlegame Transition
            # Positive value = got worse (human pattern)
            # Negative value = got better (suspicious - "turns on engine")
            if (
                opening_acpl is not None
                and middle_acpl is not None
                and opening_acpl > 0
                and middle_acpl > 0
            ):
                # Transition = middle - opening
                # Positive = deterioration, Negative = improvement
                transition = middle_acpl - opening_acpl
                opening_to_middle_transitions.append(transition)

                # Signal 3: Collapse Detection
                # Collapse = deterioration > 50cp
                if transition > 50:
                    collapses.append(1)
                else:
                    collapses.append(0)

            # Middle to Endgame Transition (for completeness)
            if (
                middle_acpl is not None
                and endgame_acpl is not None
                and middle_acpl > 0
                and endgame_acpl > 0
            ):
                transition = endgame_acpl - middle_acpl
                middle_to_end_transitions.append(transition)

                # Also count endgame collapses
                if transition > 50:
                    collapses.append(1)
                else:
                    collapses.append(0)

            # Signal 4: Phase Consistency - NEW: Use final_match_rate instead of ACPL
            # Extract final_match_rate from phase_breakdown for more stable consistency metric
            # (Match rate is less sensitive to outliers than ACPL)

            # Extract final_match_rate for middlegame (primary focus for Signal 4)
            middlegame_final_match_rate = JSONFieldParser.safe_get_nested(
                phase_data, "middlegame", "final_match_rate"
            )
            if middlegame_final_match_rate is not None:
                # Store as percentage (0-100) for consistency calculation
                middle_consistency_scores.append(middlegame_final_match_rate * 100)

            # Optional: Also extract for opening and endgame (for completeness)
            opening_final_match_rate = JSONFieldParser.safe_get_nested(
                phase_data, "opening", "final_match_rate"
            )
            if opening_final_match_rate is not None:
                opening_consistency_scores.append(opening_final_match_rate * 100)

            endgame_final_match_rate = JSONFieldParser.safe_get_nested(
                phase_data, "endgame", "final_match_rate"
            )
            if endgame_final_match_rate is not None:
                endgame_consistency_scores.append(endgame_final_match_rate * 100)

        # Calculate aggregated metrics

        # Signal 2: Average phase transition
        opening_to_middle = StatUtils.mean(opening_to_middle_transitions)
        middle_to_end = StatUtils.mean(middle_to_end_transitions)

        # Signal 3: Collapse rate (% of transitions that are collapses)
        collapse_rate = StatUtils.mean(collapses)

        # Signal 4: Phase Consistency - NEW: Calculate from match rate variability
        # Convert per-game match rates to consistency score using CV formula
        # Formula: Consistency = 100 * (1 - CV / 2.0), where CV = std_dev / mean
        # Higher consistency = more mechanical (suspicious)

        def calculate_consistency_from_match_rates(match_rates: list[float]) -> float | None:
            """Calculate consistency score from list of match rates (0-100 scale)."""
            if not match_rates or len(match_rates) < 2:
                return None

            import statistics

            mean_rate = statistics.mean(match_rates)
            if mean_rate == 0:
                return None

            std_dev = statistics.stdev(match_rates)
            cv = std_dev / mean_rate  # Coefficient of Variation
            consistency = max(0, min(100, 100 * (1 - cv / 2.0)))
            return round(consistency, 1)

        phase_consistency_opening = calculate_consistency_from_match_rates(opening_consistency_scores)
        phase_consistency_middle = calculate_consistency_from_match_rates(middle_consistency_scores)
        phase_consistency_endgame = calculate_consistency_from_match_rates(endgame_consistency_scores)

        logger.info(
            f"Phase metrics: transition={(opening_to_middle if opening_to_middle is not None else 0):.2f} cp, "
            f"collapse_rate={(collapse_rate*100 if collapse_rate is not None else 0):.1f}%, "
            f"opening_consistency={(phase_consistency_opening if phase_consistency_opening is not None else 0):.1f}, "
            f"middle_consistency={(phase_consistency_middle if phase_consistency_middle is not None else 0):.1f}, "
            f"endgame_consistency={(phase_consistency_endgame if phase_consistency_endgame is not None else 0):.1f}"
        )

        return {
            "opening_to_middle_transition": opening_to_middle,
            "middle_to_endgame_transition": middle_to_end,
            "collapse_rate": collapse_rate,
            "phase_consistency_opening": phase_consistency_opening,
            "phase_consistency_middle": phase_consistency_middle,
            "phase_consistency_endgame": phase_consistency_endgame,
        }

    @property
    def calculator_name(self) -> str:
        """Return calculator identifier."""
        return "phase_metrics"
