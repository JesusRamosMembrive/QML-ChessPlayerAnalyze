"""
Metric calculators for player aggregate statistics.

Provides calculate_all() which runs all calculators and merges results.
"""

from services.calculators.advanced_metrics import AdvancedMetricsCalculator
from services.calculators.base import MetricCalculator
from services.calculators.basic_stats import BasicStatsCalculator
from services.calculators.difficulty_metrics import DifficultyMetricsCalculator
from services.calculators.historical import HistoricalCalculator
from services.calculators.phase_1b_metrics import Phase1BMetricsCalculator
from services.calculators.phase_metrics import PhaseMetricsCalculator
from services.calculators.precision_metrics import PrecisionMetricsCalculator
from services.calculators.psychological import PsychologicalCalculator
from services.calculators.time_metrics import TimeMetricsCalculator

_CALCULATORS = [
    BasicStatsCalculator(),
    AdvancedMetricsCalculator(),
    PrecisionMetricsCalculator(),
    PhaseMetricsCalculator(),
    TimeMetricsCalculator(),
    PsychologicalCalculator(),
    Phase1BMetricsCalculator(),
    DifficultyMetricsCalculator(),
    HistoricalCalculator(max_games=50),
]


def calculate_all(items: list[dict]) -> dict:
    """Run all metric calculators and merge results into a single dict."""
    result = {}
    for calc in _CALCULATORS:
        result.update(calc.calculate(items))
    return result


__all__ = ["MetricCalculator", "calculate_all"]
