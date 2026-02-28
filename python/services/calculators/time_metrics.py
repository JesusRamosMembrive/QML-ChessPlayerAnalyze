"""
Time metrics calculator.

Calculates time pressure metrics including time-complexity correlation.
"""

from typing import Any

from services.calculators.base import MetricCalculator
from utils import get_logger
from utils.json_parser import JSONFieldParser
from utils.stat_utils import StatUtils

logger = get_logger(__name__)


class TimeMetricsCalculator(MetricCalculator):
    """
    Calculator for time pressure metrics.

    This calculator processes time-complexity correlation data to detect:
    - Time-complexity anomalies: Humans think longer on complex positions
      (positive correlation >0.3), while engines analyze at constant speed
      (correlation ≈0 or negative)
    - Anomaly scores indicating deviation from expected human behavior

    The calculator aggregates per-game time_complexity data to produce:
    - time_complexity_correlation: Average correlation across games
    - anomaly_score_mean: Average anomaly score indicating suspicious patterns
    """

    def calculate(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Calculate time pressure metrics from game analysis items.

        Args:
            items: List of analysis items containing time_complexity JSON field

        Returns:
            Dictionary with time metric fields:
            - time_complexity_correlation: Average time-complexity correlation
            - anomaly_score_mean: Average anomaly score
        """
        correlations = []
        anomaly_scores = []

        for item in items:
            analysis = item["analysis"]

            # Parse time_complexity JSON field
            time_data = JSONFieldParser.parse_field(analysis, "time_complexity", default=None)

            if not time_data:
                continue

            # Extract correlation and anomaly score
            correlation = time_data.get("correlation")
            anomaly_score = time_data.get("anomaly_score")

            if correlation is not None:
                correlations.append(correlation)
            if anomaly_score is not None:
                anomaly_scores.append(anomaly_score)

        # Need minimum data points
        if not correlations:
            logger.info("No time-complexity data available")
            return {
                "time_complexity_correlation": None,
                "anomaly_score_mean": None,
            }

        # Calculate averages
        avg_correlation = StatUtils.mean(correlations, default=0.0)
        avg_anomaly = StatUtils.mean(anomaly_scores)

        anomaly_str = f"{avg_anomaly:.1f}" if avg_anomaly is not None else "N/A"
        logger.info(
            f"Time-complexity aggregated: avg_correlation={avg_correlation:.3f}, "
            f"avg_anomaly={anomaly_str}, "
            f"games={len(correlations)}"
        )

        return {
            "time_complexity_correlation": avg_correlation,
            "anomaly_score_mean": avg_anomaly,
        }

    @property
    def calculator_name(self) -> str:
        """Return calculator identifier."""
        return "time_metrics"
