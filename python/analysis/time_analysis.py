"""
Time pressure and time management analysis.

Analyzes how players perform under time pressure and how they allocate time
across different positions.
"""

from typing import Any

from .phase_analysis import calculate_position_complexity


def calculate_time_pressure_metrics(
    move_times: list[int], move_evals: list[dict], is_white: bool
) -> dict[str, float | int | bool | Any]:
    """
    Calculate time pressure and time management metrics.

    Chess.com stores move times as:
    - Positive numbers for white
    - Negative numbers for black

    Graceful degradation: Returns default values if insufficient data (< 5 moves).
    This prevents crashes on short games while allowing partial analysis.

    Args:
        move_times: List of move times (positive=white, negative=black)
        move_evals: List of move evaluations from analyze_single_game()
        is_white: True if analyzing white player, False for black

    Returns:
        Dict with time pressure metrics:
        {
            "mean_move_time": float,          # Average seconds per move
            "time_std": float,                # Standard deviation
            "time_variance": float,           # Variance in move times
            "fast_moves": int,                # Moves < 2 seconds
            "slow_moves": int,                # Moves > 30 seconds
            "endgame_time_pressure": bool,    # Running low on time at end
            "clutch_acpl": float,             # ACPL in last 10 moves
            "regular_acpl": float,            # ACPL before last 10 moves
            "time_trouble_detected": bool,    # Performance drop under time pressure
            "has_sufficient_data": bool       # True if >= 5 player moves
        }
    """
    # Graceful degradation: check for missing data
    if not move_times or not move_evals:
        return {
            "mean_move_time": 0.0,
            "time_std": 0.0,
            "time_variance": 0.0,
            "fast_moves": 0,
            "slow_moves": 0,
            "endgame_time_pressure": False,
            "clutch_acpl": 0.0,
            "regular_acpl": 0.0,
            "time_trouble_detected": False,
            "has_sufficient_data": False,
        }

    # Extract player's move times (filter by color)
    player_times = []
    player_evals = []

    for i, time in enumerate(move_times):
        # White moves are positive, black moves are negative
        # FIXED: Skip None values to prevent comparison errors
        if time is None:
            continue
        if is_white and time > 0:
            player_times.append(time)
            if i < len(move_evals):
                player_evals.append(move_evals[i])
        elif not is_white and time < 0:
            player_times.append(abs(time))
            if i < len(move_evals):
                player_evals.append(move_evals[i])

    # Graceful degradation: return defaults if insufficient player moves
    MIN_MOVES_FOR_ANALYSIS = 5
    if len(player_times) < MIN_MOVES_FOR_ANALYSIS:
        return {
            "mean_move_time": 0.0,
            "time_std": 0.0,
            "time_variance": 0.0,
            "fast_moves": 0,
            "slow_moves": 0,
            "endgame_time_pressure": False,
            "clutch_acpl": 0.0,
            "regular_acpl": 0.0,
            "time_trouble_detected": False,
            "has_sufficient_data": False,
        }

    # Basic time statistics
    mean_time = sum(player_times) / len(player_times)
    time_variance = sum((t - mean_time) ** 2 for t in player_times) / len(player_times)
    time_std = time_variance**0.5

    # Fast and slow moves
    fast_moves = sum(1 for t in player_times if t < 2)
    slow_moves = sum(1 for t in player_times if t > 30)

    # Endgame time pressure (last 10 moves average < 5 seconds)
    last_10_times = player_times[-10:] if len(player_times) >= 10 else player_times
    avg_last_10 = sum(last_10_times) / len(last_10_times)
    endgame_time_pressure = avg_last_10 < 5

    # Clutch performance (last 10 moves)
    if len(player_evals) >= 10:
        last_10_evals = player_evals[-10:]
        regular_evals = player_evals[:-10]

        # Calculate ACPL for both sections
        # FIXED: Handle None cp_loss values
        clutch_losses = [
            min(m["cp_loss"], 1500) for m in last_10_evals if m.get("cp_loss") is not None
        ]
        clutch_acpl = sum(clutch_losses) / len(clutch_losses) if clutch_losses else 0

        if regular_evals:
            # FIXED: Handle None cp_loss values
            regular_losses = [
                min(m["cp_loss"], 1500) for m in regular_evals if m.get("cp_loss") is not None
            ]
            regular_acpl = sum(regular_losses) / len(regular_losses) if regular_losses else 0
        else:
            regular_acpl = clutch_acpl

        # Time trouble detected if clutch ACPL significantly worse (>20% increase)
        time_trouble_detected = clutch_acpl > regular_acpl * 1.2
    else:
        clutch_acpl = 0
        regular_acpl = 0
        time_trouble_detected = False

    return {
        "mean_move_time": round(mean_time, 2),
        "time_std": round(time_std, 2),
        "time_variance": round(time_variance, 2),
        "fast_moves": fast_moves,
        "slow_moves": slow_moves,
        "endgame_time_pressure": endgame_time_pressure,
        "clutch_acpl": round(clutch_acpl, 2),
        "regular_acpl": round(regular_acpl, 2),
        "time_trouble_detected": time_trouble_detected,
        "has_sufficient_data": True,
    }


def calculate_time_complexity_correlation(move_evals: list[dict], move_times: list[int]) -> dict:
    """
    Analyze correlation between position complexity and time used.

    Players should generally use more time on complex positions.
    Anomalies:
    - Too fast on complex positions (suspicious - may indicate engine use)
    - Too slow on simple positions (overthinking)

    Graceful degradation: Returns default values if insufficient data (< 5 moves).
    This prevents crashes on short games while allowing partial analysis.

    Args:
        move_evals: List of move evaluations with complexity data
        move_times: List of time spent per move (in seconds)

    Returns:
        Dict with:
        - correlation: Pearson correlation coefficient (-1 to 1)
        - avg_time_simple: Average time on simple positions (complexity < 33)
        - avg_time_medium: Average time on medium positions (33-66)
        - avg_time_complex: Average time on complex positions (> 66)
        - anomaly_score: 0-100, higher = more suspicious
        - has_sufficient_data: True if >= 5 moves analyzed
    """
    # Graceful degradation: check for missing or mismatched data
    MIN_MOVES_FOR_ANALYSIS = 5

    if not move_evals or not move_times:
        return {
            "correlation": 0.0,
            "avg_time_simple": 0.0,
            "avg_time_medium": 0.0,
            "avg_time_complex": 0.0,
            "anomaly_score": 0.0,
            "has_sufficient_data": False,
        }

    if len(move_evals) != len(move_times):
        return {
            "correlation": 0.0,
            "avg_time_simple": 0.0,
            "avg_time_medium": 0.0,
            "avg_time_complex": 0.0,
            "anomaly_score": 0.0,
            "has_sufficient_data": False,
        }

    if len(move_evals) < MIN_MOVES_FOR_ANALYSIS:
        return {
            "correlation": 0.0,
            "avg_time_simple": 0.0,
            "avg_time_medium": 0.0,
            "avg_time_complex": 0.0,
            "anomaly_score": 0.0,
            "has_sufficient_data": False,
        }

    # Calculate complexity for each position
    complexities = [calculate_position_complexity(m) for m in move_evals]

    # Categorize positions
    simple_times = []
    medium_times = []
    complex_times = []

    for complexity, time in zip(complexities, move_times, strict=False):
        if complexity < 33:
            simple_times.append(time)
        elif complexity < 66:
            medium_times.append(time)
        else:
            complex_times.append(time)

    # Calculate averages
    avg_simple = sum(simple_times) / len(simple_times) if simple_times else 0
    avg_medium = sum(medium_times) / len(medium_times) if medium_times else 0
    avg_complex = sum(complex_times) / len(complex_times) if complex_times else 0

    # Calculate correlation (simplified - proper Pearson would use statistics module)
    # For now, use a simple ratio-based approach
    if avg_simple > 0 and avg_complex > 0:
        # Expected: avg_complex > avg_simple
        ratio = avg_complex / avg_simple

        # Good correlation: ratio > 1.5 (50% more time on complex)
        # Suspicious: ratio < 1.0 (less time on complex!)
        if ratio > 1.5:
            correlation = 0.7  # Strong positive
            anomaly_score = 0
        elif ratio > 1.0:
            correlation = 0.3  # Weak positive
            anomaly_score = 20
        else:
            correlation = -0.3  # Negative (suspicious!)
            anomaly_score = min(100, (1.0 - ratio) * 100)
    else:
        correlation = 0.0
        anomaly_score = 0

    return {
        "correlation": correlation,
        "avg_time_simple": avg_simple,
        "avg_time_medium": avg_medium,
        "avg_time_complex": avg_complex,
        "anomaly_score": anomaly_score,
        "has_sufficient_data": True,
    }


def detect_post_pause_quality(
    move_times: list[int], move_evals: list[dict], is_white: bool, pause_threshold: int = 30
) -> dict:
    """
    Detect if move quality improves after long pauses (ENGINE INDICATOR).

    PHASE 1B: Humans think during pauses but may still blunder.
    Engine users "consult" during pauses → perfect moves follow.

    Args:
        move_times: List of move times (positive=white, negative=black)
        move_evals: List of move evaluations
        is_white: True if analyzing white player
        pause_threshold: Seconds to consider "long pause" (default: 30)

    Returns:
        Dict with pause analysis:
        {
            "long_pauses_count": int,           # Number of pauses > threshold
            "post_pause_avg_quality": float,    # Avg cp_loss after long pauses
            "normal_avg_quality": float,        # Avg cp_loss after normal pauses
            "improvement_after_pause": float,   # normal - post_pause (positive = better after pause)
            "pause_improvement_rate": float,    # % of excellent moves (cp_loss < 10) after pauses
            "pauses_analyzed": int,             # Number of pauses with valid next move
        }
    """
    if not move_times or not move_evals:
        return {
            "long_pauses_count": 0,
            "post_pause_avg_quality": None,
            "normal_avg_quality": None,
            "improvement_after_pause": None,
            "pause_improvement_rate": None,
            "pauses_analyzed": 0,
        }

    # Extract player's move times and evals
    player_times = []
    player_evals = []

    for i, time in enumerate(move_times):
        # White moves are positive, black moves are negative
        # FIXED: Skip None values to prevent comparison errors
        if time is None:
            continue
        if is_white and time > 0:
            player_times.append(time)
            if i < len(move_evals):
                player_evals.append(move_evals[i])
        elif not is_white and time < 0:
            player_times.append(abs(time))
            if i < len(move_evals):
                player_evals.append(move_evals[i])

    if len(player_times) < 2 or len(player_evals) < 2:
        return {
            "long_pauses_count": 0,
            "post_pause_avg_quality": None,
            "normal_avg_quality": None,
            "improvement_after_pause": None,
            "pause_improvement_rate": None,
            "pauses_analyzed": 0,
        }

    # Analyze move quality after pauses
    post_long_pause_quality = []  # Quality of moves after long pauses
    post_normal_quality = []  # Quality of moves after normal pauses
    excellent_after_pause = 0  # Count of excellent moves after long pauses
    long_pauses_count = 0

    for i in range(len(player_times) - 1):
        # Check if next move exists
        if i + 1 >= len(player_evals):
            break

        move_time = player_times[i]
        # FIXED: Handle None cp_loss values
        next_cp_loss = player_evals[i + 1].get("cp_loss")
        if next_cp_loss is None:
            continue  # Skip moves without cp_loss

        next_move_quality = min(next_cp_loss, 1500)

        if move_time >= pause_threshold:
            # Long pause detected
            long_pauses_count += 1
            post_long_pause_quality.append(next_move_quality)

            # Excellent move? (< 10cp loss)
            if next_move_quality < 10:
                excellent_after_pause += 1
        else:
            # Normal timing
            post_normal_quality.append(next_move_quality)

    # Calculate statistics
    post_pause_avg = (
        sum(post_long_pause_quality) / len(post_long_pause_quality)
        if post_long_pause_quality
        else None
    )

    normal_avg = (
        sum(post_normal_quality) / len(post_normal_quality) if post_normal_quality else None
    )

    # Improvement calculation (positive = better after pauses = SUSPICIOUS)
    improvement = None
    if post_pause_avg is not None and normal_avg is not None:
        improvement = round(normal_avg - post_pause_avg, 2)

    # Improvement rate (% of excellent moves after pauses)
    pause_improvement_rate = None
    if post_long_pause_quality:
        pause_improvement_rate = round(excellent_after_pause / len(post_long_pause_quality), 4)

    return {
        "long_pauses_count": long_pauses_count,
        "post_pause_avg_quality": round(post_pause_avg, 2) if post_pause_avg else None,
        "normal_avg_quality": round(normal_avg, 2) if normal_avg else None,
        "improvement_after_pause": improvement,
        "pause_improvement_rate": pause_improvement_rate,
        "pauses_analyzed": len(post_long_pause_quality),
    }
