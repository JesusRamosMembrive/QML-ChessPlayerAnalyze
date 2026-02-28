"""
Precision metrics calculator.

Calculates precision burst metrics from per-game precision data.
"""

from typing import Any

from services.calculators.base import MetricCalculator
from utils import get_logger
from utils.json_parser import JSONFieldParser
from utils.stat_utils import StatUtils

logger = get_logger(__name__)


class PrecisionMetricsCalculator(MetricCalculator):
    """
    Calculator for precision burst metrics.

    This calculator processes precision burst data to compute:
    - precision_burst_mean: Average precision bursts per game
    - longest_burst_mean: Average longest burst length
    - precision_rate_mean: Average precision rate (0-1)

    Precision bursts indicate consecutive high-quality moves, which can be
    used to detect unusual performance patterns.
    """

    def calculate(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Calculate precision burst metrics from game analysis items.

        Args:
            items: List of analysis items containing precision_bursts JSON field

        Returns:
            Dictionary with precision metric fields:
            - precision_burst_mean: Average number of bursts per game
            - longest_burst_mean: Average length of longest burst
            - precision_rate_mean: Average precision rate (0.0-1.0)
        """
        burst_counts = []
        longest_bursts = []
        precision_rates = []

        for item in items:
            analysis = item["analysis"]

            # Parse precision_bursts JSON field
            precision_data = JSONFieldParser.parse_field(analysis, "precision_bursts", default=None)

            if not precision_data:
                continue

            # Extract metrics
            burst_count = precision_data.get("burst_count")
            longest_burst = precision_data.get("longest_burst")
            precision_rate = precision_data.get("precision_rate")

            if burst_count is not None:
                burst_counts.append(burst_count)
            if longest_burst is not None:
                longest_bursts.append(longest_burst)
            if precision_rate is not None:
                precision_rates.append(precision_rate)

        logger.info(
            f"Precision metrics aggregated: {len(burst_counts)} burst counts, "
            f"{len(longest_bursts)} longest bursts, {len(precision_rates)} precision rates"
        )

        return {
            "precision_burst_mean": StatUtils.mean(burst_counts),
            "longest_burst_mean": StatUtils.mean(longest_bursts),
            "precision_rate_mean": StatUtils.mean(precision_rates),
        }

    @property
    def calculator_name(self) -> str:
        """Return calculator identifier."""
        return "precision_metrics"
