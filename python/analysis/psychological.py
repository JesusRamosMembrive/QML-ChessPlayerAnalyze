"""
Psychological momentum and pattern analysis.

Analyzes psychological patterns from move quality sequences including tilt,
recovery ability, and performance under pressure.
"""

from typing import Optional

from utils import get_logger

logger = get_logger(__name__)


def get_pressure_threshold(time_control: str | None = None) -> float:
    """
    Get clock-based pressure threshold by time control.

    Determines when a player is under "time pressure" based on remaining
    clock time (not move time). Uses dynamic thresholds per time control.

    Args:
        time_control: Time control string (e.g., "bullet", "blitz", "rapid")

    Returns:
        Threshold in seconds. If remaining clock < threshold → under pressure.

    Examples:
        - Bullet (1+0): 10 seconds
        - Blitz (2+1 to 5+0): 20 seconds
        - Rapid (10+0 to 60+0): 60 seconds
        - Classical (30+ minutes): 120 seconds
    """
    if not time_control:
        return 20.0  # Default: blitz threshold

    tc_lower = time_control.lower()

    if "bullet" in tc_lower:
        return 10.0  # < 10 seconds on clock = pressure
    elif "blitz" in tc_lower:
        return 20.0  # < 20 seconds on clock = pressure
    elif "rapid" in tc_lower:
        return 60.0  # < 60 seconds on clock = pressure
    else:
        return 120.0  # Classical/other: < 120 seconds = pressure


def analyze_psychological_momentum(
    move_evals: list[float],
    move_times: Optional[list[int]] = None,
    complexities: Optional[list[int]] = None,
    clock_times: Optional[list[float]] = None,  # NEW: Remaining clock times
    time_control: Optional[str] = None,  # NEW: Time control for threshold
) -> dict:
    """
    Analyze psychological patterns from move quality sequences.

    Detects:
    - Tilt: Error rate increases after blunders
    - Recovery: Ability to bounce back from mistakes
    - Closing: Precision when winning
    - Pressure: Performance under time constraints (using clock remaining)

    Args:
        move_evals: List of centipawn losses for each move - REQUIRED
        move_times: Optional list of time spent per move (seconds) - DEPRECATED for pressure
        complexities: Optional list of position complexity scores
        clock_times: Optional list of remaining clock time after each move (seconds)
        time_control: Optional time control string (e.g., "bullet", "blitz", "rapid")

    Returns:
        Dict with psychological metrics (NO None values):
        {
            "tilt_episodes": int,
            "recovery_count": int,
            "recovery_rate": float,
            "closing_acpl": float,  # 0.0 if insufficient data
            "pressure_acpl": float,  # 0.0 if no time data
            "pressure_degradation": float,  # 0.0 if no time data
            "psychological_profile": str,
            "has_sufficient_data": bool  # False if <10 moves
        }

    Raises:
        AssertionError: If move_evals is missing (should be validated upstream)

    Note:
        Pressure detection now uses clock_times (remaining time on clock) instead of
        move_times (time spent per move) for accurate pressure detection.
        Falls back to move_times if clock_times not available.
    """
    # Data validation - fail fast
    assert move_evals, "move_evals required - should be validated in analyze_single_game()"

    # Log data availability
    logger.info(
        f"Psychological analysis: {len(move_evals)} moves, "
        f"times={'yes' if move_times else 'no'}, "
        f"complexities={'yes' if complexities else 'no'}"
    )

    # Check if we have sufficient data for meaningful analysis
    has_sufficient_data = len(move_evals) >= 10

    if not has_sufficient_data:
        logger.warning(
            f"Insufficient data for psychological analysis: {len(move_evals)} moves (need 10+)"
        )
        return {
            "tilt_episodes": 0,
            "recovery_count": 0,
            "recovery_rate": 0.0,
            "closing_acpl": 0.0,  # Changed from None to 0.0
            "pressure_acpl": 0.0,  # Changed from None to 0.0
            "pressure_degradation": 0.0,  # Changed from None to 0.0
            "psychological_profile": "INSUFFICIENT_DATA",
            "has_sufficient_data": False,
        }

    # Define thresholds
    BLUNDER_THRESHOLD = 100  # cp loss > 100 is blunder
    ERROR_THRESHOLD = 50  # cp loss > 50 is significant error
    # TIME_PRESSURE_THRESHOLD removed - now using dynamic threshold via get_pressure_threshold()

    # Detect blunders (major errors)
    blunder_indices = [i for i, eval_loss in enumerate(move_evals) if eval_loss > BLUNDER_THRESHOLD]

    # Analyze tilt and recovery
    tilt_episodes = 0
    recovery_count = 0

    for blunder_idx in blunder_indices:
        # Look at next 5 moves after blunder
        window_end = min(blunder_idx + 6, len(move_evals))
        post_blunder_moves = move_evals[blunder_idx + 1 : window_end]

        if not post_blunder_moves:
            continue

        # Tilt detection: 3+ consecutive errors (>50 cp) after blunder
        consecutive_errors = 0
        for eval_loss in post_blunder_moves[:5]:
            if eval_loss > ERROR_THRESHOLD:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    tilt_episodes += 1
                    break
            else:
                consecutive_errors = 0

        # Recovery detection: ACPL returns to normal within 5 moves
        avg_post_blunder = sum(post_blunder_moves) / len(post_blunder_moves)
        overall_acpl = sum(move_evals) / len(move_evals)

        if avg_post_blunder < overall_acpl * 1.2:  # Within 20% of normal
            recovery_count += 1

    recovery_rate = recovery_count / len(blunder_indices) if blunder_indices else 0.0

    logger.debug(
        f"Tilt/recovery: {tilt_episodes} tilt episodes, "
        f"{recovery_count}/{len(blunder_indices) if blunder_indices else 0} recoveries "
        f"({recovery_rate*100:.1f}%)"
    )

    # Closing precision analysis
    # We don't have position evals, so use ACPL when few errors (proxy for winning)
    # Better implementation would require position evaluations
    # For now, use last 20% of moves as "endgame/closing" phase
    closing_moves_start = int(len(move_evals) * 0.8)
    closing_moves_raw = move_evals[closing_moves_start:]

    # Cap extreme values at 300 cp to avoid outliers from mates/blunders
    MAX_CP_LOSS = 300
    closing_moves = [min(eval_loss, MAX_CP_LOSS) for eval_loss in closing_moves_raw]
    closing_acpl = sum(closing_moves) / len(closing_moves) if closing_moves else 0.0

    logger.debug(f"Closing ACPL: {closing_acpl:.2f} (from {len(closing_moves)} moves)")

    # Pressure response analysis - NEW CLOCK-BASED APPROACH
    pressure_acpl = 0.0  # Changed from None to 0.0
    pressure_degradation = 0.0  # Changed from None to 0.0

    # Priority 1: Use clock_times (remaining time on clock) - OPTIMAL
    if clock_times and len(clock_times) == len(move_evals):
        # Get dynamic threshold based on time control
        threshold = get_pressure_threshold(time_control)

        logger.info(
            f"✓ Using clock-based pressure detection: {len(clock_times)} clocks, "
            f"{len(move_evals)} evals, threshold={threshold}s, time_control={time_control}"
        )

        # Find moves with time pressure (clock remaining < threshold)
        pressure_moves = [
            (i, eval_loss)
            for i, (clock, eval_loss) in enumerate(zip(clock_times, move_evals, strict=False))
            if clock is not None and clock < threshold
        ]

        if pressure_moves:
            # Cap extreme values to avoid outliers from mates/blunders
            pressure_evals_raw = [eval_loss for _, eval_loss in pressure_moves]
            pressure_evals = [min(eval_loss, MAX_CP_LOSS) for eval_loss in pressure_evals_raw]
            pressure_acpl = sum(pressure_evals) / len(pressure_evals)

            logger.debug(
                f"Clock pressure: {len(pressure_moves)} moves with clock < {threshold}s, "
                f"ACPL={pressure_acpl:.2f}"
            )

            # Calculate degradation vs normal (clock >= threshold)
            normal_moves = [
                (i, eval_loss)
                for i, (clock, eval_loss) in enumerate(zip(clock_times, move_evals, strict=False))
                if clock is not None and clock >= threshold
            ]

            if normal_moves:
                # Cap extreme values for normal moves too
                normal_evals_raw = [eval_loss for _, eval_loss in normal_moves]
                normal_evals = [min(eval_loss, MAX_CP_LOSS) for eval_loss in normal_evals_raw]
                normal_acpl = sum(normal_evals) / len(normal_evals)

                pressure_degradation = (
                    ((pressure_acpl - normal_acpl) / normal_acpl * 100) if normal_acpl > 0 else 0.0
                )

                logger.debug(
                    f"Clock pressure degradation: {pressure_degradation:.1f}% "
                    f"(pressure_acpl={pressure_acpl:.2f} vs normal_acpl={normal_acpl:.2f}, "
                    f"threshold={threshold}s)"
                )
            else:
                logger.debug(f"No normal moves (all moves under {threshold}s)")
        else:
            logger.debug(f"No pressure moves detected (clock always >= {threshold}s)")

    # Priority 2: Fallback to move_times (time spent per move) - DEPRECATED
    elif move_times and len(move_times) == len(move_evals):
        logger.warning(
            f"⚠ Falling back to move_time-based pressure detection (less accurate): "
            f"{len(move_times)} times, {len(move_evals)} evals. "
            f"clock_times={'available' if clock_times else 'missing'}, "
            f"clock_len={len(clock_times) if clock_times else 0}"
        )

        # Use old logic as fallback (time spent < 30s)
        TIME_PRESSURE_THRESHOLD = 30  # Kept for backward compatibility

        pressure_moves = [
            (i, eval_loss)
            for i, (time, eval_loss) in enumerate(zip(move_times, move_evals, strict=False))
            if time is not None and time > 0 and time < TIME_PRESSURE_THRESHOLD
        ]

        if pressure_moves:
            pressure_evals_raw = [eval_loss for _, eval_loss in pressure_moves]
            pressure_evals = [min(eval_loss, MAX_CP_LOSS) for eval_loss in pressure_evals_raw]
            pressure_acpl = sum(pressure_evals) / len(pressure_evals)

            logger.debug(
                f"Move-time pressure (fallback): {len(pressure_moves)} moves < {TIME_PRESSURE_THRESHOLD}s, "
                f"ACPL={pressure_acpl:.2f}"
            )

            normal_moves = [
                (i, eval_loss)
                for i, (time, eval_loss) in enumerate(zip(move_times, move_evals, strict=False))
                if time is not None and time >= TIME_PRESSURE_THRESHOLD
            ]

            if normal_moves:
                normal_evals_raw = [eval_loss for _, eval_loss in normal_moves]
                normal_evals = [min(eval_loss, MAX_CP_LOSS) for eval_loss in normal_evals_raw]
                normal_acpl = sum(normal_evals) / len(normal_evals)

                pressure_degradation = (
                    ((pressure_acpl - normal_acpl) / normal_acpl * 100) if normal_acpl > 0 else 0.0
                )

                logger.debug(
                    f"Move-time pressure degradation (fallback): {pressure_degradation:.1f}% "
                    f"(pressure={pressure_acpl:.2f} vs normal={normal_acpl:.2f})"
                )
        else:
            logger.debug("No time pressure moves detected (fallback)")

    else:
        # No time data available at all
        if clock_times:
            logger.warning(
                f"Clock time data mismatch: {len(clock_times)} clocks vs {len(move_evals)} evals"
            )
        elif move_times:
            logger.warning(
                f"Move time data mismatch: {len(move_times)} times vs {len(move_evals)} evals"
            )
        else:
            logger.debug("No time data available for pressure analysis")

    # Determine psychological profile
    profile = _determine_psychological_profile(
        tilt_episodes, recovery_rate, closing_acpl, pressure_degradation, len(move_evals)
    )

    logger.info(f"Psychological profile: {profile}")

    return {
        "tilt_episodes": tilt_episodes,
        "recovery_count": recovery_count,
        "recovery_rate": round(recovery_rate * 100, 1),  # Convert to percentage
        "closing_acpl": round(closing_acpl, 2),  # Always float, never None
        "pressure_acpl": round(pressure_acpl, 2),  # Always float, never None
        "pressure_degradation": round(pressure_degradation, 1),  # Always float, never None
        "psychological_profile": profile,
        "has_sufficient_data": True,  # If we reach here, we have enough data
    }


def _determine_psychological_profile(
    tilt_episodes: int,
    recovery_rate: float,
    closing_acpl: float,
    pressure_degradation: float,
    total_moves: int,
) -> str:
    """
    Determine overall psychological profile based on metrics.

    Profiles:
    - RESILIENT_CLOSER: Good recovery, good closing
    - RESILIENT_SHAKY: Good recovery, poor closing
    - FRAGILE_CLOSER: Poor recovery, good closing
    - FRAGILE_CRUMBLER: Poor recovery, poor closing
    - PRESSURE_FIGHTER: Handles pressure well
    - PRESSURE_VULNERABLE: Struggles under pressure
    - ENGINE_LIKE: Suspiciously consistent (no tilt, perfect recovery)
    - NORMAL_HUMAN: Average patterns

    Args:
        tilt_episodes: Number of tilt sequences
        recovery_rate: Recovery rate (0.0-1.0)
        closing_acpl: Closing ACPL (0.0 if no data)
        pressure_degradation: Pressure degradation % (0.0 if no data)
        total_moves: Total moves analyzed
    """
    # Normalize tilt rate (per 50 moves)
    (tilt_episodes / total_moves) * 50 if total_moves > 0 else 0

    # Check for engine-like behavior (no None checks needed now)
    if tilt_episodes == 0 and recovery_rate > 0.95 and pressure_degradation < 5:
        logger.debug("ENGINE_LIKE profile detected")
        return "ENGINE_LIKE"

    # Determine resilience
    is_resilient = recovery_rate > 0.6  # >60% recovery rate
    is_fragile = recovery_rate < 0.3  # <30% recovery rate

    # Determine closing ability (0.0 means no data, skip evaluation)
    good_closer = closing_acpl > 0 and closing_acpl < 50
    poor_closer = closing_acpl > 80

    # Determine pressure response (0.0 means no data, skip evaluation)
    handles_pressure = pressure_degradation != 0.0 and pressure_degradation < 20
    struggles_pressure = pressure_degradation > 50

    # Build profile
    if is_resilient and good_closer:
        return "RESILIENT_CLOSER"
    elif is_resilient and poor_closer:
        return "RESILIENT_SHAKY"
    elif is_fragile and good_closer:
        return "FRAGILE_CLOSER"
    elif is_fragile and poor_closer:
        return "FRAGILE_CRUMBLER"
    elif handles_pressure:
        return "PRESSURE_FIGHTER"
    elif struggles_pressure:
        return "PRESSURE_VULNERABLE"
    else:
        return "NORMAL_HUMAN"
