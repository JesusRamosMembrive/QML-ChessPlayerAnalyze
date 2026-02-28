"""
Psychological metrics calculator.

Calculates psychological behavior metrics including tilt, recovery,
and performance under pressure.
"""

from typing import Any

from services.calculators.base import MetricCalculator
from utils import get_logger
from utils.json_parser import JSONFieldParser
from utils.stat_utils import StatUtils

logger = get_logger(__name__)


class PsychologicalCalculator(MetricCalculator):
    """
    Calculator for psychological behavior metrics.

    This calculator processes psychological_momentum data to detect:
    - Tilt patterns: Emotional deterioration after mistakes
    - Recovery patterns: Ability to bounce back from errors
    - Closing performance: ACPL in endgame (fatigue indicator)
    - Pressure degradation: Performance decline under time pressure

    NOTE: Since refactoring (2025-11-12), psychological_momentum NEVER contains
    None values. All fields are guaranteed to be numeric or 0.0. We only filter
    out 0.0 values which indicate "no data available" (e.g., no time pressure).
    """

    def calculate(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Calculate psychological metrics from game analysis items.

        Args:
            items: List of analysis items containing psychological_momentum JSON field

        Returns:
            Dictionary with psychological metric fields:
            - tilt_rate: Rate of tilt detection (0-1)
            - recovery_rate: Rate of recovery patterns (0-1)
            - closing_acpl: Average ACPL in endgame (fatigue indicator)
            - pressure_degradation: Performance decline under time pressure
        """
        tilt_rates = []
        recovery_rates = []
        closing_acpls = []
        pressure_degradations = []

        for item in items:
            analysis = item["analysis"]

            # Parse psychological_momentum JSON field
            psych_data = JSONFieldParser.parse_field(
                analysis, "psychological_momentum", default=None
            )

            if not psych_data:
                continue

            # Check if game has sufficient data (new field added in refactor)
            if not psych_data.get("has_sufficient_data", True):
                logger.debug(f"Skipping game {item['game'].id}: insufficient psychological data")
                continue

            if "tilt_detected" in psych_data:
                tilt_rates.append(1 if psych_data["tilt_detected"] else 0)

            if "recovery_pattern" in psych_data:
                recovery_rates.append(1 if psych_data["recovery_pattern"] else 0)

            # Closing ACPL: 0.0 means no data (skip), otherwise include
            if "closing_acpl" in psych_data and psych_data["closing_acpl"] > 0:
                closing_acpls.append(psych_data["closing_acpl"])

            # Pressure degradation: Include ALL values (0.0 is valid - means no degradation)
            # Only skip if field doesn't exist or is None
            # Note: 0.0 can mean either "no pressure detected" OR "exact same performance"
            # Both are valid and suspicious (humans should degrade 10-30%)
            if "pressure_degradation" in psych_data and psych_data["pressure_degradation"] is not None:
                pressure_degradations.append(psych_data["pressure_degradation"])

        logger.info(
            f"Psychological metrics aggregated: {len(closing_acpls)} closing ACPL values, "
            f"{len(pressure_degradations)} pressure degradation values"
        )

        return {
            "tilt_rate": StatUtils.mean(tilt_rates),
            "recovery_rate": StatUtils.mean(recovery_rates),
            "closing_acpl": StatUtils.mean(closing_acpls),
            "pressure_degradation": StatUtils.mean(pressure_degradations),
        }

    @property
    def calculator_name(self) -> str:
        """Return calculator identifier."""
        return "psychological"
