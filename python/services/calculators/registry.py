"""
Calculator registry for managing and executing metric calculators.

This module provides the CalculatorRegistry class that manages calculator
instances and orchestrates their execution to produce aggregated metrics.
"""

from typing import Any

from services.calculators.base import MetricCalculator


class CalculatorRegistry:
    """
    Registry for managing and executing metric calculators.

    The registry follows the Registry pattern to decouple the AggregationService
    from specific calculator implementations. New calculators can be added
    without modifying the service code.

    Responsibilities:
    - Maintain collection of registered calculator instances
    - Execute all calculators in registration order
    - Merge results into single aggregate dictionary
    - Provide introspection capabilities (count, names)

    Example:
        >>> registry = CalculatorRegistry()
        >>> registry.register(BasicStatsCalculator())
        >>> registry.register(SuspicionCalculator())
        >>> items = [{"acpl": 15, "move_count": 40}]
        >>> result = registry.calculate_all(items)
        >>> print(result.keys())
        dict_keys(['acpl_mean', 'acpl_std', 'suspicion_score', ...])
    """

    def __init__(self):
        """Initialize empty calculator registry."""
        self._calculators: list[MetricCalculator] = []

    def register(self, calculator: MetricCalculator) -> None:
        """
        Register a calculator instance.

        Calculators are executed in registration order, so dependencies
        should be registered first if calculators depend on each other's
        results (though this should be avoided).

        Args:
            calculator: MetricCalculator instance to register

        Example:
            >>> registry = CalculatorRegistry()
            >>> registry.register(BasicStatsCalculator())
        """
        self._calculators.append(calculator)

    def calculate_all(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Execute all registered calculators and merge results.

        Calculators are executed sequentially in registration order.
        Each calculator's results are merged into a single dictionary.
        If multiple calculators produce the same key, later calculators
        will overwrite earlier values (avoid this design).

        Args:
            items: List of dictionaries containing game analysis data

        Returns:
            Merged dictionary containing all calculated metrics from
            all registered calculators

        Example:
            >>> registry = CalculatorRegistry()
            >>> registry.register(BasicStatsCalculator())
            >>> registry.register(SuspicionCalculator())
            >>> items = [{"acpl": 15, "blunders": 2}]
            >>> result = registry.calculate_all(items)
            >>> result
            {
                "acpl_mean": 15.0,
                "acpl_std": 0.0,
                "suspicion_score": 0.23,
                ...
            }
        """
        result = {}

        for calculator in self._calculators:
            metrics = calculator.calculate(items)
            result.update(metrics)

        return result

    @property
    def calculator_count(self) -> int:
        """
        Return number of registered calculators.

        Returns:
            Count of registered calculators

        Example:
            >>> registry = CalculatorRegistry()
            >>> registry.register(BasicStatsCalculator())
            >>> registry.calculator_count
            1
        """
        return len(self._calculators)

    @property
    def calculator_names(self) -> list[str]:
        """
        Return names of all registered calculators.

        Useful for debugging, logging, and introspection.

        Returns:
            List of calculator names in registration order

        Example:
            >>> registry = CalculatorRegistry()
            >>> registry.register(BasicStatsCalculator())
            >>> registry.register(SuspicionCalculator())
            >>> registry.calculator_names
            ['basic_stats', 'suspicion']
        """
        return [calc.calculator_name for calc in self._calculators]
