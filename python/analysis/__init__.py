"""
Chess game analysis package.

Modular analysis toolkit for chess performance evaluation.
Split from monolithic stockfish_wrapper.py for better maintainability.
"""

# Core engine
# Basic metrics
from .basic_metrics import (
    calculate_acpl,
    calculate_blunders,
    calculate_final_match_rate,
    calculate_rank_distribution,
    calculate_robust_acpl,
    calculate_topn_match_rates,
    count_precision_moves,
)
from .engine import analyze_game

# Phase analysis
from .phase_analysis import (
    calculate_enhanced_phase_analysis,
    calculate_phase_metrics,
    calculate_position_complexity,
)

# Psychological patterns
from .psychological import (
    analyze_psychological_momentum,
)

# Suspicion scoring
from .suspicion import (
    calculate_precision_bursts,
    calculate_suspicion_score,
)

# Time analysis
from .time_analysis import (
    calculate_time_complexity_correlation,
    calculate_time_pressure_metrics,
)

# Position difficulty
from .difficulty import (
    calculate_sharpness_score,
    is_forced_move,
)

# Human impossibility detection
from .human_impossibility import (
    calculate_human_impossibility_metrics,
)

# Toggle detection
from .toggle_detection import (
    calculate_toggle_detection_metrics,
)

# Temporal window analysis
from .temporal_windows import (
    calculate_elo_slope,
    detect_win_streaks,
    detect_performance_bursts,
)

__all__ = [
    # Engine
    "analyze_game",
    # Basic metrics
    "calculate_acpl",
    "calculate_blunders",
    "count_precision_moves",
    "calculate_robust_acpl",
    "calculate_rank_distribution",
    "calculate_topn_match_rates",
    "calculate_final_match_rate",
    # Phase analysis
    "calculate_phase_metrics",
    "calculate_position_complexity",
    "calculate_enhanced_phase_analysis",
    # Time analysis
    "calculate_time_pressure_metrics",
    "calculate_time_complexity_correlation",
    # Psychological
    "analyze_psychological_momentum",
    # Suspicion
    "calculate_precision_bursts",
    "calculate_suspicion_score",
    # Difficulty
    "calculate_sharpness_score",
    "is_forced_move",
    # Human impossibility
    "calculate_human_impossibility_metrics",
    # Toggle detection
    "calculate_toggle_detection_metrics",
    # Temporal window analysis
    "calculate_elo_slope",
    "detect_win_streaks",
    "detect_performance_bursts",
]
