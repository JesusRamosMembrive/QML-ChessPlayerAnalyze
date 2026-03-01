"""
Temporal window analysis calculator.

Bridges the gap between stored game data (PGN result format, split ELO)
and the temporal_windows module (win/loss/draw, single elo field).
Runs sliding window analysis to detect suspicious ELO jumps, impossible
win streaks, and correlated performance bursts.
"""

from typing import Any

from analysis.temporal_windows import (
    calculate_elo_slope,
    detect_performance_bursts,
    detect_win_streaks,
)
from services.calculators.base import MetricCalculator


class TemporalWindowsCalculator(MetricCalculator):
    """Calculator for temporal window analysis metrics."""

    def _convert_item(self, item: dict) -> dict | None:
        """Convert a calculator item to the dict format temporal_windows expects."""
        game = item["game"]
        analysis = item["analysis"]

        # Determine player's ELO
        is_white = game.username.lower() == game.white_username.lower()
        elo = game.white_elo if is_white else game.black_elo
        if elo is None:
            return None

        # Convert PGN result to win/loss/draw from player's perspective
        result_str = game.result  # "1-0", "0-1", "1/2-1/2"
        if result_str == "1-0":
            outcome = "win" if is_white else "loss"
        elif result_str == "0-1":
            outcome = "loss" if is_white else "win"
        else:
            outcome = "draw"

        return {
            "date": game.date,
            "elo": elo,
            "result": outcome,
            "acpl": analysis.acpl,
            "top1_match_rate": analysis.top1_match_rate,
            "blunder_rate": analysis.blunder_rate,
        }

    def calculate(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Run all temporal window analyses and return flattened metrics."""
        # Convert items, filtering out any that can't be converted
        converted = []
        for item in items:
            c = self._convert_item(item)
            if c is not None:
                converted.append(c)

        # Sort by date (oldest first) — temporal_windows expects chronological order
        converted.sort(key=lambda g: g["date"])

        # Run all 3 analysis functions
        elo_result = calculate_elo_slope(converted)
        streak_result = detect_win_streaks(converted)
        burst_result = detect_performance_bursts(converted)

        # Extract key values from results
        max_slope_window = elo_result.max_slope_window
        max_wr_window = streak_result.max_winrate_window
        strongest = burst_result.strongest_burst

        return {
            # ELO slope
            "tw_elo_slope_max": max_slope_window.elo_slope if max_slope_window else None,
            "tw_elo_suspicious_windows": len(elo_result.suspicious_windows),
            "tw_elo_total_delta": elo_result.total_elo_delta,
            # Win streaks
            "tw_max_win_rate": max_wr_window.win_rate if max_wr_window else None,
            "tw_win_suspicious_windows": len(streak_result.suspicious_windows),
            "tw_overall_win_rate": streak_result.overall_win_rate,
            # Performance bursts
            "tw_burst_count": len(burst_result.suspicious_windows),
            "tw_has_burst": len(burst_result.suspicious_windows) > 0,
            "tw_strongest_burst_signals": len(strongest.suspicion_reasons) if strongest else 0,
        }

    @property
    def calculator_name(self) -> str:
        """Return calculator identifier."""
        return "temporal_windows"
