"""
Basic statistics calculator.

Calculates comprehensive basic statistical metrics (mean, median, std, percentiles)
for ACPL, match rates, blunder rates, and move counts.
"""

from typing import Any

from services.calculators.base import MetricCalculator
from utils.stat_utils import StatUtils


class BasicStatsCalculator(MetricCalculator):
    """
    Calculator for basic statistical metrics.

    This calculator processes pre-extracted lists to compute:
    - ACPL statistics: mean, median, std, min, max, percentiles
    - Top-N match rate statistics: mean, std, min, max for top1/2/3/5
    - Blunder rate statistics: mean, std
    - Move count statistics: mean, median

    Note: This calculator uses an adapter pattern because it receives
    pre-extracted lists instead of raw items.
    """

    def calculate(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Calculate basic statistics from game analysis items.

        This method extracts the necessary lists from items and delegates
        to _calculate_from_lists() for the actual computation.

        Args:
            items: List of analysis items to extract data from

        Returns:
            Dictionary with basic statistic fields (24 metrics total)
        """
        # Extract lists from items
        acpls = []
        blunder_rates = []
        move_counts = []
        top1_rates = []
        top2_rates = []
        top3_rates = []
        top4_rates = []
        top5_rates = []

        for item in items:
            analysis = item["analysis"]

            if analysis.acpl is not None:
                acpls.append(analysis.acpl)
            if analysis.blunder_rate is not None:
                blunder_rates.append(analysis.blunder_rate)
            if analysis.move_count is not None:
                move_counts.append(analysis.move_count)
            if analysis.top1_match_rate is not None:
                top1_rates.append(analysis.top1_match_rate)
            if analysis.top2_match_rate is not None:
                top2_rates.append(analysis.top2_match_rate)
            if analysis.top3_match_rate is not None:
                top3_rates.append(analysis.top3_match_rate)
            if hasattr(analysis, 'top4_match_rate') and analysis.top4_match_rate is not None:
                top4_rates.append(analysis.top4_match_rate)
            if analysis.top5_match_rate is not None:
                top5_rates.append(analysis.top5_match_rate)

        # Delegate to list-based calculation
        return self._calculate_from_lists(
            acpls, blunder_rates, move_counts, top1_rates, top2_rates, top3_rates, top4_rates, top5_rates
        )

    def _calculate_from_lists(
        self,
        acpls: list[float],
        blunder_rates: list[float],
        move_counts: list[int],
        top1_rates: list[float],
        top2_rates: list[float],
        top3_rates: list[float],
        top4_rates: list[float],
        top5_rates: list[float],
    ) -> dict[str, Any]:
        """
        Calculate basic statistical metrics from pre-extracted lists.

        Args:
            acpls: List of ACPL values
            blunder_rates: List of blunder rates
            move_counts: List of move counts
            top1_rates: List of top-1 match rates
            top2_rates: List of top-2 match rates
            top3_rates: List of top-3 match rates
            top4_rates: List of top-4 match rates
            top5_rates: List of top-5 match rates

        Returns:
            Dictionary with 28 statistical metrics (including top4)
        """
        if not acpls:
            # Return None for all metrics if no data
            return self._empty_result()

        # ACPL statistics
        acpl_mean, acpl_std = StatUtils.mean_and_std(acpls)
        acpl_median = StatUtils.median(acpls)
        acpl_min = min(acpls)
        acpl_max = max(acpls)

        # Percentiles
        acpl_p25, acpl_p75 = None, None
        if len(acpls) >= 4:
            sorted_acpls = sorted(acpls)
            q1_idx = len(sorted_acpls) // 4
            q3_idx = 3 * len(sorted_acpls) // 4
            acpl_p25 = sorted_acpls[q1_idx]
            acpl_p75 = sorted_acpls[q3_idx]

        # Top-N match rate statistics
        top1_match_rate_mean, top1_match_rate_std = StatUtils.mean_and_std(top1_rates)
        top1_match_rate_min = min(top1_rates) if top1_rates else None
        top1_match_rate_max = max(top1_rates) if top1_rates else None

        top2_match_rate_mean, top2_match_rate_std = StatUtils.mean_and_std(top2_rates)
        top2_match_rate_min = min(top2_rates) if top2_rates else None
        top2_match_rate_max = max(top2_rates) if top2_rates else None

        top3_match_rate_mean, top3_match_rate_std = StatUtils.mean_and_std(top3_rates)
        top3_match_rate_min = min(top3_rates) if top3_rates else None
        top3_match_rate_max = max(top3_rates) if top3_rates else None

        top4_match_rate_mean, top4_match_rate_std = StatUtils.mean_and_std(top4_rates)
        top4_match_rate_min = min(top4_rates) if top4_rates else None
        top4_match_rate_max = max(top4_rates) if top4_rates else None

        top5_match_rate_mean, top5_match_rate_std = StatUtils.mean_and_std(top5_rates)
        top5_match_rate_min = min(top5_rates) if top5_rates else None
        top5_match_rate_max = max(top5_rates) if top5_rates else None

        # Blunder rate statistics
        blunder_rate_mean, blunder_rate_std = StatUtils.mean_and_std(blunder_rates)

        # Move count statistics
        move_count_mean = StatUtils.mean(move_counts)
        move_count_median = StatUtils.median(move_counts)

        return {
            "acpl_mean": acpl_mean,
            "acpl_median": acpl_median,
            "acpl_std": acpl_std,
            "acpl_min": acpl_min,
            "acpl_max": acpl_max,
            "acpl_p25": acpl_p25,
            "acpl_p75": acpl_p75,
            "top1_match_rate_mean": top1_match_rate_mean,
            "top1_match_rate_std": top1_match_rate_std,
            "top1_match_rate_min": top1_match_rate_min,
            "top1_match_rate_max": top1_match_rate_max,
            "top2_match_rate_mean": top2_match_rate_mean,
            "top2_match_rate_std": top2_match_rate_std,
            "top2_match_rate_min": top2_match_rate_min,
            "top2_match_rate_max": top2_match_rate_max,
            "top3_match_rate_mean": top3_match_rate_mean,
            "top3_match_rate_std": top3_match_rate_std,
            "top3_match_rate_min": top3_match_rate_min,
            "top3_match_rate_max": top3_match_rate_max,
            "top4_match_rate_mean": top4_match_rate_mean,
            "top4_match_rate_std": top4_match_rate_std,
            "top4_match_rate_min": top4_match_rate_min,
            "top4_match_rate_max": top4_match_rate_max,
            "top5_match_rate_mean": top5_match_rate_mean,
            "top5_match_rate_std": top5_match_rate_std,
            "top5_match_rate_min": top5_match_rate_min,
            "top5_match_rate_max": top5_match_rate_max,
            "blunder_rate_mean": blunder_rate_mean,
            "blunder_rate_std": blunder_rate_std,
            "move_count_mean": move_count_mean,
            "move_count_median": move_count_median,
        }

    def _empty_result(self) -> dict[str, Any]:
        """Return empty result with all metrics set to None."""
        return {
            "acpl_mean": None,
            "acpl_median": None,
            "acpl_std": None,
            "acpl_min": None,
            "acpl_max": None,
            "acpl_p25": None,
            "acpl_p75": None,
            "top1_match_rate_mean": None,
            "top1_match_rate_std": None,
            "top1_match_rate_min": None,
            "top1_match_rate_max": None,
            "top2_match_rate_mean": None,
            "top2_match_rate_std": None,
            "top2_match_rate_min": None,
            "top2_match_rate_max": None,
            "top3_match_rate_mean": None,
            "top3_match_rate_std": None,
            "top3_match_rate_min": None,
            "top3_match_rate_max": None,
            "top4_match_rate_mean": None,
            "top4_match_rate_std": None,
            "top4_match_rate_min": None,
            "top4_match_rate_max": None,
            "top5_match_rate_mean": None,
            "top5_match_rate_std": None,
            "top5_match_rate_min": None,
            "top5_match_rate_max": None,
            "blunder_rate_mean": None,
            "blunder_rate_std": None,
            "move_count_mean": None,
            "move_count_median": None,
        }

    @property
    def calculator_name(self) -> str:
        """Return calculator identifier."""
        return "basic_stats"
