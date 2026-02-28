"""
Temporal Window Analysis for Cheat Detection.

This module implements sliding window analysis to detect suspicious behavioral
changes over time. Unlike aggregate statistics that can mask recent cheating
with historical legitimate play, windowed analysis identifies:

1. ELO Slope Analysis: Sudden rating jumps indicating boosting/cheating
2. Win Streak Detection: Impossible win rates in specific time windows
3. Performance Burst Detection: Correlated improvements in ELO+ACPL+WinRate

Design Philosophy:
- Subtle detection: Focus on time windows where cheating behavior manifests
- Temporal precision: Don't let old legitimate games mask recent cheating
- Multiple signals: Combine ELO, win/loss, and performance metrics

Example Use Case:
    Player with 500 games history:
    - Games 1-480: Legitimate play (50% win rate, stable ELO)
    - Games 481-500: Engine activation (95% win rate, +300 ELO jump)

    Aggregate analysis → Hidden pattern (masked by history)
    Window analysis → Clear detection (20-game window shows burst)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from utils import get_logger

logger = get_logger(__name__)


@dataclass
class WindowMetrics:
    """Metrics for a single analysis window."""

    # Window identification
    start_index: int  # Game index where window starts (0-based)
    end_index: int  # Game index where window ends (exclusive)
    window_size: int  # Number of games in window
    start_date: datetime  # Date of first game in window
    end_date: datetime  # Date of last game in window

    # ELO metrics
    elo_start: int  # ELO at start of window
    elo_end: int  # ELO at end of window
    elo_delta: int  # Total ELO change in window
    elo_slope: float  # ELO change per game (delta / window_size)
    elo_min: int  # Minimum ELO in window
    elo_max: int  # Maximum ELO in window

    # Win/Loss metrics
    wins: int
    losses: int
    draws: int
    total_games: int
    win_rate: float  # wins / (wins + losses), excludes draws
    win_loss_ratio: float  # wins / losses (0 if no losses)

    # Performance metrics (if available)
    avg_acpl: Optional[float] = None  # Average ACPL in window
    avg_match_rate: Optional[float] = None  # Average top-1 match rate
    avg_blunder_rate: Optional[float] = None  # Average blunder rate

    # Suspicion flags
    is_suspicious: bool = False  # Overall suspicion flag
    suspicion_reasons: list[str] = None  # Why this window is suspicious

    def __post_init__(self):
        """Initialize suspicion_reasons if not provided."""
        if self.suspicion_reasons is None:
            self.suspicion_reasons = []


@dataclass
class ELOSlopeResult:
    """Result of ELO slope analysis."""

    # Overall statistics
    total_games: int
    total_elo_delta: int
    avg_slope: float  # Average ELO change per game across all windows

    # Suspicious windows
    suspicious_windows: list[WindowMetrics]
    max_slope_window: Optional[WindowMetrics]  # Window with steepest slope

    # Thresholds used
    slope_threshold: float  # ELO/game threshold for suspicion
    window_size: int  # Size of sliding window


@dataclass
class WinStreakResult:
    """Result of win streak analysis."""

    # Overall statistics
    total_games: int
    overall_win_rate: float

    # Suspicious streaks
    suspicious_windows: list[WindowMetrics]
    max_winrate_window: Optional[WindowMetrics]  # Window with highest win rate

    # Thresholds used
    winrate_threshold: float  # Win rate threshold for suspicion (0-1)
    min_games: int  # Minimum games for valid streak
    window_size: int


@dataclass
class PerformanceBurstResult:
    """Result of performance burst detection (multi-metric correlation)."""

    # Overall statistics
    total_games: int

    # Suspicious bursts (windows where multiple metrics spike)
    suspicious_windows: list[WindowMetrics]
    strongest_burst: Optional[WindowMetrics]  # Window with most signals

    # Thresholds used
    elo_slope_threshold: float
    winrate_threshold: float
    acpl_threshold: float  # Low ACPL is suspicious
    min_signals: int  # Minimum signals required for burst detection


def calculate_elo_slope(
    games: list[dict],
    window_size: int = 20,
    slope_threshold: float = 10.0,
) -> ELOSlopeResult:
    """
    Detect suspicious ELO jumps using sliding window analysis.

    Analyzes ELO progression over time to identify windows where the player's
    rating increases abnormally fast. Legitimate players have gradual ELO
    changes (~2-5 pts/game), while boosted/cheating accounts show steep
    climbs (>10 pts/game).

    Args:
        games: List of game dictionaries with 'date', 'elo', 'result' keys
               Sorted by date (oldest first)
        window_size: Number of consecutive games per window (default: 20)
        slope_threshold: ELO points per game threshold for suspicion (default: 10)

    Returns:
        ELOSlopeResult with suspicious windows identified

    Example:
        >>> games = fetch_games_for_player("username")
        >>> result = calculate_elo_slope(games, window_size=20, slope_threshold=10)
        >>> if result.suspicious_windows:
        >>>     print(f"Found {len(result.suspicious_windows)} suspicious windows")
        >>>     for window in result.suspicious_windows:
        >>>         print(f"Games {window.start_index}-{window.end_index}: "
        >>>               f"+{window.elo_delta} ELO ({window.elo_slope:.1f} pts/game)")
    """
    if len(games) < window_size:
        logger.warning(
            f"Insufficient games for ELO slope analysis: {len(games)} < {window_size}"
        )
        return ELOSlopeResult(
            total_games=len(games),
            total_elo_delta=0,
            avg_slope=0.0,
            suspicious_windows=[],
            max_slope_window=None,
            slope_threshold=slope_threshold,
            window_size=window_size,
        )

    windows = []
    total_elo_delta = games[-1]["elo"] - games[0]["elo"]
    slopes = []

    # Sliding window analysis
    for i in range(len(games) - window_size + 1):
        window_games = games[i : i + window_size]

        # Calculate window metrics
        elo_start = window_games[0]["elo"]
        elo_end = window_games[-1]["elo"]
        elo_delta = elo_end - elo_start
        elo_slope = elo_delta / window_size

        # Count wins/losses/draws
        wins = sum(1 for g in window_games if g["result"] == "win")
        losses = sum(1 for g in window_games if g["result"] == "loss")
        draws = sum(1 for g in window_games if g["result"] == "draw")

        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0
        win_loss_ratio = wins / losses if losses > 0 else float(wins)

        # Get performance metrics if available
        acpls = [g.get("acpl") for g in window_games if g.get("acpl") is not None]
        avg_acpl = sum(acpls) / len(acpls) if acpls else None

        match_rates = [
            g.get("top1_match_rate") for g in window_games if g.get("top1_match_rate") is not None
        ]
        avg_match_rate = sum(match_rates) / len(match_rates) if match_rates else None

        blunder_rates = [
            g.get("blunder_rate") for g in window_games if g.get("blunder_rate") is not None
        ]
        avg_blunder_rate = sum(blunder_rates) / len(blunder_rates) if blunder_rates else None

        # Create window metrics
        window = WindowMetrics(
            start_index=i,
            end_index=i + window_size,
            window_size=window_size,
            start_date=window_games[0]["date"],
            end_date=window_games[-1]["date"],
            elo_start=elo_start,
            elo_end=elo_end,
            elo_delta=elo_delta,
            elo_slope=elo_slope,
            elo_min=min(g["elo"] for g in window_games),
            elo_max=max(g["elo"] for g in window_games),
            wins=wins,
            losses=losses,
            draws=draws,
            total_games=window_size,
            win_rate=win_rate,
            win_loss_ratio=win_loss_ratio,
            avg_acpl=avg_acpl,
            avg_match_rate=avg_match_rate,
            avg_blunder_rate=avg_blunder_rate,
        )

        slopes.append(elo_slope)

        # Check if window is suspicious
        if elo_slope >= slope_threshold:
            window.is_suspicious = True
            window.suspicion_reasons.append(
                f"ELO slope {elo_slope:.1f} pts/game (threshold: {slope_threshold})"
            )

        windows.append(window)

    # Find suspicious windows and max slope
    suspicious_windows = [w for w in windows if w.is_suspicious]
    max_slope_window = max(windows, key=lambda w: w.elo_slope) if windows else None

    avg_slope = sum(slopes) / len(slopes) if slopes else 0.0

    return ELOSlopeResult(
        total_games=len(games),
        total_elo_delta=total_elo_delta,
        avg_slope=avg_slope,
        suspicious_windows=suspicious_windows,
        max_slope_window=max_slope_window,
        slope_threshold=slope_threshold,
        window_size=window_size,
    )


def detect_win_streaks(
    games: list[dict],
    window_size: int = 20,
    winrate_threshold: float = 0.85,
    min_games: int = 10,
) -> WinStreakResult:
    """
    Detect impossible win rate streaks.

    Analyzes win/loss patterns to identify windows where the player wins
    an unrealistic percentage of games. Even strong players lose ~20-30%
    of games to variance, tactics, time trouble, etc.

    Args:
        games: List of game dictionaries with 'result' key
               Sorted by date (oldest first)
        window_size: Number of consecutive games per window (default: 20)
        winrate_threshold: Win rate threshold for suspicion (default: 0.85 = 85%)
        min_games: Minimum games in window for valid analysis (default: 10)

    Returns:
        WinStreakResult with suspicious streaks identified

    Thresholds Guide:
        - 90%+ win rate over 20+ games: Extremely suspicious (engine)
        - 85%+ win rate over 30+ games: Very suspicious
        - 80%+ win rate over 50+ games: Suspicious
        - 75%+ sustained: Strong player but not impossible
    """
    if len(games) < min_games:
        logger.warning(f"Insufficient games for streak analysis: {len(games)} < {min_games}")

        overall_wins = sum(1 for g in games if g["result"] == "win")
        overall_losses = sum(1 for g in games if g["result"] == "loss")
        overall_winrate = (
            overall_wins / (overall_wins + overall_losses)
            if (overall_wins + overall_losses) > 0
            else 0.0
        )

        return WinStreakResult(
            total_games=len(games),
            overall_win_rate=overall_winrate,
            suspicious_windows=[],
            max_winrate_window=None,
            winrate_threshold=winrate_threshold,
            min_games=min_games,
            window_size=window_size,
        )

    windows = []

    # Sliding window analysis
    for i in range(len(games) - window_size + 1):
        window_games = games[i : i + window_size]

        # Count wins/losses/draws
        wins = sum(1 for g in window_games if g["result"] == "win")
        losses = sum(1 for g in window_games if g["result"] == "loss")
        draws = sum(1 for g in window_games if g["result"] == "draw")

        # Skip windows with too many draws
        if (wins + losses) < min_games:
            continue

        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0
        win_loss_ratio = wins / losses if losses > 0 else float(wins)

        # Get ELO data
        elo_start = window_games[0]["elo"]
        elo_end = window_games[-1]["elo"]
        elo_delta = elo_end - elo_start

        # Get performance metrics if available
        acpls = [g.get("acpl") for g in window_games if g.get("acpl") is not None]
        avg_acpl = sum(acpls) / len(acpls) if acpls else None

        # Create window metrics
        window = WindowMetrics(
            start_index=i,
            end_index=i + window_size,
            window_size=window_size,
            start_date=window_games[0]["date"],
            end_date=window_games[-1]["date"],
            elo_start=elo_start,
            elo_end=elo_end,
            elo_delta=elo_delta,
            elo_slope=elo_delta / window_size,
            elo_min=min(g["elo"] for g in window_games),
            elo_max=max(g["elo"] for g in window_games),
            wins=wins,
            losses=losses,
            draws=draws,
            total_games=window_size,
            win_rate=win_rate,
            win_loss_ratio=win_loss_ratio,
            avg_acpl=avg_acpl,
        )

        # Check if window is suspicious
        if win_rate >= winrate_threshold:
            window.is_suspicious = True
            window.suspicion_reasons.append(
                f"Win rate {win_rate*100:.1f}% ({wins}W-{losses}L) (threshold: {winrate_threshold*100:.0f}%)"
            )

        windows.append(window)

    # Find suspicious windows and max win rate
    suspicious_windows = [w for w in windows if w.is_suspicious]
    max_winrate_window = max(windows, key=lambda w: w.win_rate) if windows else None

    # Calculate overall win rate
    overall_wins = sum(1 for g in games if g["result"] == "win")
    overall_losses = sum(1 for g in games if g["result"] == "loss")
    overall_winrate = (
        overall_wins / (overall_wins + overall_losses)
        if (overall_wins + overall_losses) > 0
        else 0.0
    )

    return WinStreakResult(
        total_games=len(games),
        overall_win_rate=overall_winrate,
        suspicious_windows=suspicious_windows,
        max_winrate_window=max_winrate_window,
        winrate_threshold=winrate_threshold,
        min_games=min_games,
        window_size=window_size,
    )


def detect_performance_bursts(
    games: list[dict],
    window_size: int = 20,
    elo_slope_threshold: float = 8.0,
    winrate_threshold: float = 0.80,
    acpl_threshold: float = 15.0,
    min_signals: int = 2,
) -> PerformanceBurstResult:
    """
    Detect correlated performance bursts across multiple metrics.

    This is the most powerful temporal detection method. It identifies windows
    where multiple suspicious signals appear simultaneously:
    - ELO jumps sharply
    - Win rate increases dramatically
    - ACPL drops to engine-like levels

    Single metrics can have legitimate explanations, but correlated bursts
    across all metrics indicate external assistance (engine use).

    Args:
        games: List of game dictionaries with all metrics
        window_size: Number of consecutive games per window (default: 20)
        elo_slope_threshold: ELO pts/game for signal (default: 8.0)
        winrate_threshold: Win rate for signal (default: 0.80 = 80%)
        acpl_threshold: Low ACPL for signal (default: 15.0)
        min_signals: Minimum signals required for burst (default: 2)

    Returns:
        PerformanceBurstResult with burst windows identified

    Detection Logic:
        For each window, count signals:
        1. ELO Signal: slope >= elo_slope_threshold
        2. Win Rate Signal: win_rate >= winrate_threshold
        3. ACPL Signal: avg_acpl <= acpl_threshold (low = suspicious)
        4. Blunder Signal: blunder_rate < 0.05 (low = suspicious)

        If signals >= min_signals → Performance burst detected
    """
    if len(games) < window_size:
        logger.warning(
            f"Insufficient games for burst analysis: {len(games)} < {window_size}"
        )
        return PerformanceBurstResult(
            total_games=len(games),
            suspicious_windows=[],
            strongest_burst=None,
            elo_slope_threshold=elo_slope_threshold,
            winrate_threshold=winrate_threshold,
            acpl_threshold=acpl_threshold,
            min_signals=min_signals,
        )

    windows = []

    # Sliding window analysis
    for i in range(len(games) - window_size + 1):
        window_games = games[i : i + window_size]

        # Calculate all metrics
        elo_start = window_games[0]["elo"]
        elo_end = window_games[-1]["elo"]
        elo_delta = elo_end - elo_start
        elo_slope = elo_delta / window_size

        wins = sum(1 for g in window_games if g["result"] == "win")
        losses = sum(1 for g in window_games if g["result"] == "loss")
        draws = sum(1 for g in window_games if g["result"] == "draw")
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0

        acpls = [g.get("acpl") for g in window_games if g.get("acpl") is not None]
        avg_acpl = sum(acpls) / len(acpls) if acpls else None

        blunder_rates = [
            g.get("blunder_rate") for g in window_games if g.get("blunder_rate") is not None
        ]
        avg_blunder_rate = sum(blunder_rates) / len(blunder_rates) if blunder_rates else None

        match_rates = [
            g.get("top1_match_rate") for g in window_games if g.get("top1_match_rate") is not None
        ]
        avg_match_rate = sum(match_rates) / len(match_rates) if match_rates else None

        # Create window
        window = WindowMetrics(
            start_index=i,
            end_index=i + window_size,
            window_size=window_size,
            start_date=window_games[0]["date"],
            end_date=window_games[-1]["date"],
            elo_start=elo_start,
            elo_end=elo_end,
            elo_delta=elo_delta,
            elo_slope=elo_slope,
            elo_min=min(g["elo"] for g in window_games),
            elo_max=max(g["elo"] for g in window_games),
            wins=wins,
            losses=losses,
            draws=draws,
            total_games=window_size,
            win_rate=win_rate,
            win_loss_ratio=wins / losses if losses > 0 else float(wins),
            avg_acpl=avg_acpl,
            avg_match_rate=avg_match_rate,
            avg_blunder_rate=avg_blunder_rate,
        )

        # Count signals
        signals = []

        if elo_slope >= elo_slope_threshold:
            signals.append(f"ELO burst: +{elo_slope:.1f} pts/game")

        if win_rate >= winrate_threshold and (wins + losses) >= 10:
            signals.append(f"Win streak: {win_rate*100:.0f}% ({wins}W-{losses}L)")

        if avg_acpl is not None and avg_acpl <= acpl_threshold:
            signals.append(f"Low ACPL: {avg_acpl:.1f} (engine-like)")

        if avg_blunder_rate is not None and avg_blunder_rate < 0.05:
            signals.append(f"Low blunders: {avg_blunder_rate*100:.1f}%")

        # Check if burst detected
        if len(signals) >= min_signals:
            window.is_suspicious = True
            window.suspicion_reasons = signals

        windows.append(window)

    # Find suspicious bursts and strongest
    suspicious_windows = [w for w in windows if w.is_suspicious]
    strongest_burst = (
        max(suspicious_windows, key=lambda w: len(w.suspicion_reasons))
        if suspicious_windows
        else None
    )

    return PerformanceBurstResult(
        total_games=len(games),
        suspicious_windows=suspicious_windows,
        strongest_burst=strongest_burst,
        elo_slope_threshold=elo_slope_threshold,
        winrate_threshold=winrate_threshold,
        acpl_threshold=acpl_threshold,
        min_signals=min_signals,
    )
