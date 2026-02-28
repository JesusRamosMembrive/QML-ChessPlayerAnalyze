"""
Base abstraction for metric calculators.

This module provides the abstract base class that all metric calculators
must inherit from, ensuring a consistent interface across all calculators.
"""

from abc import ABC, abstractmethod
from typing import Any


class MetricCalculator(ABC):
    """
    Abstract base class for all metric calculators.

    Each calculator is responsible for computing a specific set of metrics
    from aggregated game analysis data. Calculators follow the Single
    Responsibility Principle by focusing on one cohesive metric domain.

    Subclasses must implement:
    - calculate(): Compute metrics from analysis items
    - calculator_name: Unique identifier for the calculator
    """

    @abstractmethod
    def calculate(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Calculate metrics from aggregated analysis items.

        Args:
            items: List of dictionaries containing game analysis data.
                   Each item represents one analyzed game with fields like:
                   - acpl: Average centipawn loss
                   - move_count: Number of moves
                   - top1_match_rate: Top-1 engine match rate
                   - blunders: Number of blunders
                   - etc.

        Returns:
            Dictionary with calculated metric fields. Keys should be
            descriptive field names (e.g., "acpl_mean", "consistency_score").
            Values can be int, float, None, or other JSON-serializable types.

        Example:
            >>> items = [
            ...     {"acpl": 15, "move_count": 40},
            ...     {"acpl": 18, "move_count": 35}
            ... ]
            >>> calculator.calculate(items)
            {"acpl_mean": 16.5, "acpl_median": 16.5, "acpl_std": 1.5}
        """
        pass

    @property
    @abstractmethod
    def calculator_name(self) -> str:
        """
        Return unique identifier for this calculator.

        This name is used for logging, debugging, and registry management.

        Returns:
            String identifier (e.g., "basic_stats", "suspicion", "phase_metrics")
        """
        pass
