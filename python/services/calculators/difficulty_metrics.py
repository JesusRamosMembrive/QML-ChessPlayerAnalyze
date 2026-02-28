"""
Difficulty metrics calculator.

Aggregates per-game difficulty metrics (sharpness, CWMR, CPA, sensitivity,
UBMA, variance ratio, critical moment boost, oscillation, mismatch, effort)
into player-level averages for the suspicion scoring system.
"""

from typing import Any

from services.calculators.base import MetricCalculator
from utils import get_logger
from utils.json_parser import JSONFieldParser
from utils.stat_utils import StatUtils

logger = get_logger(__name__)


class DifficultyMetricsCalculator(MetricCalculator):
    """
    Calculator for difficulty-based cheat detection metrics.

    Reads the 'difficulty_metrics' JSON column from GameAnalysis and
    aggregates each field across all games into player-level means.
    """

    def calculate(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Calculate aggregated difficulty metrics across games.

        Args:
            items: List of game-analysis pairs containing:
                   - analysis.difficulty_metrics: JSON with per-game metrics

        Returns:
            Dictionary with 11 aggregated fields for PlayerAggregate.
        """
        cwmr_values = []
        cwmr_delta_values = []
        cpa_values = []
        sensitivity_values = []
        ubma_values = []
        variance_ratio_values = []
        critical_accuracy_boost_values = []
        oscillation_score_values = []
        mismatch_rate_values = []
        effort_ratio_values = []
        avg_sharpness_values = []

        for item in items:
            analysis = item["analysis"]

            # Parse difficulty_metrics JSON field
            metrics = JSONFieldParser.parse_field(
                analysis, "difficulty_metrics", default=None
            )
            if not metrics:
                continue

            # Collect non-None values for each metric
            if metrics.get("cwmr") is not None:
                cwmr_values.append(metrics["cwmr"])
            if metrics.get("cwmr_delta") is not None:
                cwmr_delta_values.append(metrics["cwmr_delta"])
            if metrics.get("cpa") is not None:
                cpa_values.append(metrics["cpa"])
            if metrics.get("sensitivity") is not None:
                sensitivity_values.append(metrics["sensitivity"])
            if metrics.get("ubma") is not None:
                ubma_values.append(metrics["ubma"])
            if metrics.get("variance_ratio") is not None:
                variance_ratio_values.append(metrics["variance_ratio"])
            if metrics.get("critical_accuracy_boost") is not None:
                critical_accuracy_boost_values.append(metrics["critical_accuracy_boost"])
            if metrics.get("oscillation_score") is not None:
                oscillation_score_values.append(metrics["oscillation_score"])
            if metrics.get("mismatch_rate") is not None:
                mismatch_rate_values.append(metrics["mismatch_rate"])
            if metrics.get("effort_ratio") is not None:
                effort_ratio_values.append(metrics["effort_ratio"])
            if metrics.get("avg_sharpness") is not None:
                avg_sharpness_values.append(metrics["avg_sharpness"])

        logger.info(
            f"Difficulty metrics aggregated: {len(cwmr_values)} CWMR, "
            f"{len(cpa_values)} CPA, {len(sensitivity_values)} sensitivity, "
            f"{len(ubma_values)} UBMA, {len(variance_ratio_values)} variance_ratio, "
            f"{len(mismatch_rate_values)} mismatch"
        )

        return {
            "cwmr_mean": StatUtils.mean(cwmr_values),
            "cwmr_delta_mean": StatUtils.mean(cwmr_delta_values),
            "cpa_mean": StatUtils.mean(cpa_values),
            "sensitivity_mean": StatUtils.mean(sensitivity_values),
            "ubma_mean": StatUtils.mean(ubma_values),
            "variance_ratio_mean": StatUtils.mean(variance_ratio_values),
            "critical_accuracy_boost_mean": StatUtils.mean(critical_accuracy_boost_values),
            "oscillation_score_mean": StatUtils.mean(oscillation_score_values),
            "mismatch_rate_mean": StatUtils.mean(mismatch_rate_values),
            "effort_ratio_mean": StatUtils.mean(effort_ratio_values),
            "avg_sharpness_mean": StatUtils.mean(avg_sharpness_values),
        }

    @property
    def calculator_name(self) -> str:
        """Return calculator identifier."""
        return "difficulty_metrics"
