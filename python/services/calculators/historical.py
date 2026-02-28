"""
Historical data calculator.

Calculates historical timeline data for visualizing player performance trends
over time.
"""

from typing import Any

from services.calculators.base import MetricCalculator


class HistoricalCalculator(MetricCalculator):
    """
    Calculator for historical timeline data.

    This calculator processes recent games to create timeline data for:
    - ACPL evolution over time
    - Match rate trends (Top-1, Top-3)
    - ELO rating progression over time
    - Game dates and URLs for reference

    The timeline data is used for trend visualization in reports and dashboards.
    """

    def __init__(self, max_games: int = 50):
        """
        Initialize historical calculator.

        Args:
            max_games: Maximum number of recent games to include (default: 50)
        """
        self.max_games = max_games

    def calculate(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Calculate historical timeline data for charts.

        Processes the most recent N games to create timeline data showing
        performance trends over time.

        Args:
            items: List of game-analysis pairs sorted by date (oldest first).
                   Each item contains:
                   - game: Game model with date, url
                   - analysis: GameAnalysis model with acpl, top1_match_rate, top3_match_rate

        Returns:
            Dictionary with timeline data:
            - acpl_timeline: List of {game_date, acpl, game_url}
            - match_rate_timeline: List of {game_date, top1, top3, game_url}
            - elo_timeline: List of {game_date, elo, game_url}
            - games_count: Number of games included in timeline
        """
        # Take the most recent N games
        recent_items = items[-self.max_games :] if len(items) > self.max_games else items

        acpl_timeline = []
        match_rate_timeline = []
        elo_timeline = []

        for item in recent_items:
            game = item["game"]
            analysis = item["analysis"]

            # ACPL data point
            acpl_timeline.append(
                {
                    "game_date": game.date.isoformat() if game.date else None,
                    "acpl": round(analysis.acpl, 2),
                    "game_url": game.url,
                }
            )

            # Match rate data point
            match_rate_timeline.append(
                {
                    "game_date": game.date.isoformat() if game.date else None,
                    "top1": round(analysis.top1_match_rate * 100, 1),  # Convert to percentage
                    "top3": round(analysis.top3_match_rate * 100, 1),
                    "game_url": game.url,
                }
            )

            # ELO data point - extract player's ELO from game
            player_elo = None
            if hasattr(game, "username") and hasattr(game, "white_username") and hasattr(game, "black_username"):
                # Determine which color the analyzed player was
                if game.username == game.white_username and game.white_elo:
                    player_elo = game.white_elo
                elif game.username == game.black_username and game.black_elo:
                    player_elo = game.black_elo

            if player_elo is not None:
                elo_timeline.append(
                    {
                        "game_date": game.date.isoformat() if game.date else None,
                        "elo": player_elo,
                        "game_url": game.url,
                    }
                )

        return {
            "acpl_timeline": acpl_timeline,
            "match_rate_timeline": match_rate_timeline,
            "elo_timeline": elo_timeline,
            "games_count": len(recent_items),
        }

    @property
    def calculator_name(self) -> str:
        """Return calculator identifier."""
        return "historical"
