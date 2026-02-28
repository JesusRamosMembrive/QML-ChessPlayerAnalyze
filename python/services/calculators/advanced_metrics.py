"""
Advanced metrics calculator.

Calculates robust ACPL and rank distribution metrics from move evaluations.
"""

from typing import Any

from analysis.basic_metrics import calculate_rank_distribution, calculate_robust_acpl
from services.calculators.base import MetricCalculator
from utils.json_parser import JSONFieldParser
from utils.stat_utils import StatUtils


class AdvancedMetricsCalculator(MetricCalculator):
    """
    Calculator for advanced metrics (robust ACPL, rank distribution).

    This calculator processes move evaluations to compute:
    - Robust ACPL: ACPL with outlier removal
    - Rank distribution: Percentage of moves at each engine rank (0-3+)

    These metrics provide deeper insight into move quality consistency
    and strategic decision-making patterns.
    """

    def calculate(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Calculate advanced metrics from game analysis items.

        Args:
            items: List of analysis items containing move_evals JSON field

        Returns:
            Dictionary with advanced metric fields:
            - robust_acpl: Mean ACPL with outliers removed
            - rank_0_mean: Average % of top engine moves
            - rank_1_mean: Average % of 2nd best moves
            - rank_2_mean: Average % of 3rd best moves
            - rank_3plus_mean: Average % of moves ranked 4th or lower
        """
        robust_acpls = []
        rank_0_values = []
        rank_1_values = []
        rank_2_values = []
        rank_3plus_values = []

        for item in items:
            # Parse move_evals JSON field
            move_evals = JSONFieldParser.parse_field(item["analysis"], "move_evals", default=None)
            if not move_evals:
                continue

            # Robust ACPL
            robust_acpl = calculate_robust_acpl(move_evals)
            robust_acpls.append(robust_acpl)

            # Rank distribution
            rank_dist = calculate_rank_distribution(move_evals)
            rank_0_values.append(rank_dist["rank_0"])
            rank_1_values.append(rank_dist["rank_1"])
            rank_2_values.append(rank_dist["rank_2"])
            rank_3plus_values.append(rank_dist["rank_3plus"])

        return {
            "robust_acpl": StatUtils.mean(robust_acpls),
            "rank_0_mean": StatUtils.mean(rank_0_values),
            "rank_1_mean": StatUtils.mean(rank_1_values),
            "rank_2_mean": StatUtils.mean(rank_2_values),
            "rank_3plus_mean": StatUtils.mean(rank_3plus_values),
        }

    @property
    def calculator_name(self) -> str:
        """Return calculator identifier."""
        return "advanced_metrics"
