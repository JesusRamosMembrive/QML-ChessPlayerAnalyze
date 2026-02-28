"""
Metric calculator modules for aggregation service.

This package contains the calculator registry pattern implementation
for decomposing the AggregationService God Class into focused,
single-responsibility calculator classes.

Architecture:
- base.py: MetricCalculator abstract base class
- registry.py: CalculatorRegistry for managing calculators
- Individual calculator modules: Each implementing specific metrics

Usage:
    from services.calculators import CalculatorRegistry
    from services.calculators.basic_stats import BasicStatsCalculator

    registry = CalculatorRegistry()
    registry.register(BasicStatsCalculator())
    metrics = registry.calculate_all(items)
"""

from services.calculators.base import MetricCalculator
from services.calculators.registry import CalculatorRegistry

__all__ = [
    "MetricCalculator",
    "CalculatorRegistry",
]
