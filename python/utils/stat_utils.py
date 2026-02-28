"""
Statistical utilities with consistent null handling.

This module provides centralized statistical calculations to eliminate code duplication
and ensure consistent behavior when dealing with empty or None values.
"""

import statistics
from collections.abc import Sequence


class StatUtils:
    """
    Centralized statistical calculations with robust null handling.

    Handles common patterns:
    - Empty list handling (returns None or default)
    - Single-value lists for stdev (returns 0.0)
    - Conditional calculations (if values else None)
    - Type safety with proper defaults
    """

    @staticmethod
    def mean(values: Sequence[float], default: float | None = None) -> float | None:
        """
        Calculate mean of values or return default if empty.

        Args:
            values: List of numeric values
            default: Value to return if list is empty (default: None)

        Returns:
            Mean of values, or default if list is empty

        Examples:
            >>> StatUtils.mean([1, 2, 3])
            2.0
            >>> StatUtils.mean([])
            None
            >>> StatUtils.mean([], default=0.0)
            0.0
        """
        return statistics.mean(values) if values else default

    @staticmethod
    def median(values: Sequence[float], default: float | None = None) -> float | None:
        """
        Calculate median of values or return default if empty.

        Args:
            values: List of numeric values
            default: Value to return if list is empty (default: None)

        Returns:
            Median of values, or default if list is empty

        Examples:
            >>> StatUtils.median([1, 2, 3, 4, 5])
            3
            >>> StatUtils.median([])
            None
            >>> StatUtils.median([], default=0.0)
            0.0
        """
        return statistics.median(values) if values else default

    @staticmethod
    def stdev(values: Sequence[float], default: float = 0.0) -> float:
        """
        Calculate standard deviation with safe single-value handling.

        Args:
            values: List of numeric values
            default: Value to return if list has <2 values (default: 0.0)

        Returns:
            Standard deviation, or default if list has fewer than 2 values

        Examples:
            >>> StatUtils.stdev([1, 2, 3, 4, 5])
            1.58...
            >>> StatUtils.stdev([5])
            0.0
            >>> StatUtils.stdev([])
            0.0
        """
        return statistics.stdev(values) if len(values) > 1 else default

    @staticmethod
    def mean_and_std(
        values: Sequence[float], mean_default: float | None = None, std_default: float = 0.0
    ) -> tuple[float | None, float]:
        """
        Calculate both mean and stdev in a single pass.

        Args:
            values: List of numeric values
            mean_default: Value to return for mean if list is empty (default: None)
            std_default: Value to return for stdev if list has <2 values (default: 0.0)

        Returns:
            Tuple of (mean, stdev)

        Examples:
            >>> StatUtils.mean_and_std([1, 2, 3, 4, 5])
            (3.0, 1.58...)
            >>> StatUtils.mean_and_std([5])
            (5.0, 0.0)
            >>> StatUtils.mean_and_std([])
            (None, 0.0)
        """
        if not values:
            return (mean_default, std_default)

        mean_val = statistics.mean(values)
        std_val = statistics.stdev(values) if len(values) > 1 else std_default

        return (mean_val, std_val)

    @staticmethod
    def quantiles(
        values: Sequence[float], n: int = 4, default: list[float] | None = None
    ) -> list[float] | None:
        """
        Calculate n-quantiles (e.g., quartiles, percentiles).

        Args:
            values: List of numeric values
            n: Number of quantiles (4 for quartiles, 100 for percentiles)
            default: Value to return if list is empty (default: None)

        Returns:
            List of n-1 quantile values, or default if list is empty

        Examples:
            >>> StatUtils.quantiles([1, 2, 3, 4, 5], n=4)  # Quartiles
            [2.0, 3.0, 4.0]
            >>> StatUtils.quantiles([])
            None
        """
        return statistics.quantiles(values, n=n) if values else default

    @staticmethod
    def robust_mean(
        values: Sequence[float], trim_percent: float = 0.1, default: float | None = None
    ) -> float | None:
        """
        Calculate trimmed mean (robust to outliers).

        Removes trim_percent from both ends before calculating mean.

        Args:
            values: List of numeric values
            trim_percent: Percentage to trim from each end (0.0 to 0.5)
            default: Value to return if list is empty or too small

        Returns:
            Trimmed mean, or default if list is empty or too small

        Examples:
            >>> StatUtils.robust_mean([1, 2, 3, 4, 100], trim_percent=0.2)
            3.0  # Removed 1 and 100
            >>> StatUtils.robust_mean([1, 2, 3])
            2.0
            >>> StatUtils.robust_mean([])
            None
        """
        if not values:
            return default

        n = len(values)
        trim_count = int(n * trim_percent)

        # Need at least 3 values for meaningful trimming
        if n < 3 or trim_count == 0:
            return statistics.mean(values)

        sorted_values = sorted(values)
        trimmed = sorted_values[trim_count : n - trim_count]

        return statistics.mean(trimmed) if trimmed else default

    @staticmethod
    def percentile(values: Sequence[float], p: float, default: float | None = None) -> float | None:
        """
        Calculate specific percentile value.

        Args:
            values: List of numeric values
            p: Percentile to calculate (0-100)
            default: Value to return if list is empty

        Returns:
            Percentile value, or default if list is empty

        Examples:
            >>> StatUtils.percentile([1, 2, 3, 4, 5], 50)  # Median
            3.0
            >>> StatUtils.percentile([1, 2, 3, 4, 5], 75)
            4.0
            >>> StatUtils.percentile([], 50)
            None
        """
        if not values:
            return default

        # Convert percentile (0-100) to quantile position
        sorted_values = sorted(values)
        n = len(sorted_values)

        if n == 1:
            return sorted_values[0]

        # Linear interpolation between closest ranks
        k = (n - 1) * (p / 100)
        f = int(k)
        c = int(k) + 1

        if c >= n:
            return sorted_values[-1]

        # Interpolate
        return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])

    @staticmethod
    def variance(values: Sequence[float], default: float = 0.0) -> float:
        """
        Calculate variance with safe single-value handling.

        Args:
            values: List of numeric values
            default: Value to return if list has <2 values (default: 0.0)

        Returns:
            Variance, or default if list has fewer than 2 values

        Examples:
            >>> StatUtils.variance([1, 2, 3, 4, 5])
            2.5
            >>> StatUtils.variance([5])
            0.0
            >>> StatUtils.variance([])
            0.0
        """
        return statistics.variance(values) if len(values) > 1 else default

    @staticmethod
    def iqr(values: Sequence[float], default: float | None = None) -> float | None:
        """
        Calculate interquartile range (Q3 - Q1).

        Args:
            values: List of numeric values
            default: Value to return if list is empty or too small

        Returns:
            IQR value, or default if list is empty or too small

        Examples:
            >>> StatUtils.iqr([1, 2, 3, 4, 5, 6, 7, 8, 9])
            4.0
            >>> StatUtils.iqr([1, 2])
            None
        """
        if not values or len(values) < 4:
            return default

        quartiles = statistics.quantiles(values, n=4)
        return quartiles[2] - quartiles[0]  # Q3 - Q1
