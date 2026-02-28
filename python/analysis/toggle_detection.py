"""
Selective engine usage (toggle) detection.

Detects patterns where a player turns an engine on/off during a game,
such as using assistance only in critical moments or alternating between
human and engine play.

Signals 18-21 of the suspicion scoring system.
"""

from analysis.difficulty import calculate_sharpness_score, is_forced_move


def calculate_variance_ratio(move_evals: list[dict]) -> dict:
    """
    Variance of Precision by Difficulty (Signal 18).

    Compares cp_loss standard deviation in easy vs difficult positions.
    Humans have similar variance in both. Toggle users are perfect in
    hard positions (low variance) but normal in easy ones (high variance).

    Args:
        move_evals: List of move evaluation dicts (player moves, non-book).

    Returns:
        Dict with:
        - variance_ratio: std_easy / std_hard (>2.0 suspicious)
        - std_cp_loss_easy: Std dev of cp_loss in easy positions
        - std_cp_loss_hard: Std dev of cp_loss in hard positions
    """
    easy_losses = []
    hard_losses = []

    for m in move_evals:
        if m.get("is_book_move", False):
            continue
        if is_forced_move(m):
            continue

        cp_loss = m.get("cp_loss")
        if cp_loss is None:
            continue

        sharpness = calculate_sharpness_score(m)
        capped_loss = min(cp_loss, 500)

        if sharpness < 35:
            easy_losses.append(capped_loss)
        elif sharpness >= 60:
            hard_losses.append(capped_loss)

    if len(easy_losses) < 3 or len(hard_losses) < 3:
        return {
            "variance_ratio": None,
            "std_cp_loss_easy": None,
            "std_cp_loss_hard": None,
        }

    mean_easy = sum(easy_losses) / len(easy_losses)
    mean_hard = sum(hard_losses) / len(hard_losses)

    std_easy = (sum((x - mean_easy) ** 2 for x in easy_losses) / len(easy_losses)) ** 0.5
    std_hard = (sum((x - mean_hard) ** 2 for x in hard_losses) / len(hard_losses)) ** 0.5

    # Avoid division by zero
    if std_hard < 1.0:
        # Very low hard variance itself is suspicious, cap ratio high
        variance_ratio = 10.0 if std_easy > 5.0 else 1.0
    else:
        variance_ratio = std_easy / std_hard

    return {
        "variance_ratio": round(variance_ratio, 4),
        "std_cp_loss_easy": round(std_easy, 2),
        "std_cp_loss_hard": round(std_hard, 2),
    }


def calculate_critical_moment_accuracy(move_evals: list[dict]) -> dict:
    """
    Precision in Critical Moments (Signal 19).

    Critical moments = eval is balanced (|eval| < 150cp) AND high swing
    potential (eval_spread >= 80cp). Measures if player "turns on the engine"
    when it matters most.

    Args:
        move_evals: List of move evaluation dicts (player moves, non-book).

    Returns:
        Dict with:
        - critical_accuracy_boost: accuracy_critical - accuracy_rest
        - accuracy_critical: Match rate in critical moments
        - accuracy_rest: Match rate in non-critical moments
        - critical_moment_count: Number of critical moments found
    """
    critical_matches = 0
    critical_count = 0
    rest_matches = 0
    rest_count = 0

    for m in move_evals:
        if m.get("is_book_move", False):
            continue
        if is_forced_move(m):
            continue

        eval_before = m.get("eval_before", 0)
        eval_spread = m.get("eval_spread", 0)
        is_match = 1 if m.get("best_rank", 5) == 0 else 0

        # Critical moment: balanced position with high swing potential
        is_critical = abs(eval_before) < 150 and eval_spread >= 80

        if is_critical:
            critical_count += 1
            critical_matches += is_match
        else:
            rest_count += 1
            rest_matches += is_match

    if critical_count < 3 or rest_count < 3:
        return {
            "critical_accuracy_boost": None,
            "accuracy_critical": None,
            "accuracy_rest": None,
            "critical_moment_count": critical_count,
        }

    accuracy_critical = critical_matches / critical_count
    accuracy_rest = rest_matches / rest_count
    boost = accuracy_critical - accuracy_rest

    return {
        "critical_accuracy_boost": round(boost, 4),
        "accuracy_critical": round(accuracy_critical, 4),
        "accuracy_rest": round(accuracy_rest, 4),
        "critical_moment_count": critical_count,
    }


def calculate_oscillation_pattern(move_evals: list[dict], window_size: int = 5) -> dict:
    """
    Selective Accuracy Oscillation Pattern (Signal 20).

    Uses a sliding window to detect alternation between low-quality and
    high-quality play windows. Suspicious when high-quality windows
    coincide with more difficult positions.

    Args:
        move_evals: List of move evaluation dicts (player moves, non-book).
        window_size: Size of the sliding window (default: 5 moves).

    Returns:
        Dict with:
        - oscillation_score: Frequency of transitions * difficulty amplifier (0-100)
        - transition_count: Number of quality transitions detected
        - high_quality_windows: Number of high-quality windows
    """
    # Filter eligible moves
    eligible = []
    for m in move_evals:
        if m.get("is_book_move", False):
            continue
        if is_forced_move(m):
            continue
        if m.get("cp_loss") is None:
            continue
        eligible.append(m)

    if len(eligible) < window_size * 2:
        return {
            "oscillation_score": None,
            "transition_count": 0,
            "high_quality_windows": 0,
        }

    # Calculate window qualities
    window_data = []
    for i in range(len(eligible) - window_size + 1):
        window = eligible[i : i + window_size]
        avg_cp_loss = sum(min(m.get("cp_loss", 0), 500) for m in window) / window_size
        avg_sharpness = sum(calculate_sharpness_score(m) for m in window) / window_size
        match_rate = sum(1 for m in window if m.get("best_rank", 5) == 0) / window_size

        # High quality: low cp_loss AND high match rate
        is_high_quality = avg_cp_loss < 15 and match_rate >= 0.6

        window_data.append({
            "avg_cp_loss": avg_cp_loss,
            "avg_sharpness": avg_sharpness,
            "match_rate": match_rate,
            "is_high_quality": is_high_quality,
        })

    # Count transitions between high and low quality
    transitions = 0
    high_quality_windows = 0
    difficulty_amplifier_sum = 0.0

    for i in range(1, len(window_data)):
        prev = window_data[i - 1]
        curr = window_data[i]

        if curr["is_high_quality"]:
            high_quality_windows += 1

        if prev["is_high_quality"] != curr["is_high_quality"]:
            transitions += 1
            # If transitioning TO high quality in a harder position, amplify
            if curr["is_high_quality"] and curr["avg_sharpness"] > 45:
                difficulty_amplifier_sum += curr["avg_sharpness"] / 50.0

    if len(window_data) <= 1:
        return {
            "oscillation_score": 0.0,
            "transition_count": 0,
            "high_quality_windows": 0,
        }

    # Normalize transition frequency
    max_possible_transitions = len(window_data) - 1
    transition_freq = transitions / max_possible_transitions if max_possible_transitions > 0 else 0

    # Combine frequency and difficulty amplification
    # High transitions alone aren't suspicious (could be noisy play)
    # Suspicious when transitions correlate with difficulty
    if transitions > 0:
        avg_amplifier = difficulty_amplifier_sum / transitions
    else:
        avg_amplifier = 0.0

    oscillation_score = min(transition_freq * avg_amplifier * 100, 100)

    return {
        "oscillation_score": round(oscillation_score, 2),
        "transition_count": transitions,
        "high_quality_windows": high_quality_windows,
    }


def calculate_effort_quality_mismatch(
    move_evals: list[dict], move_times: list[float] | None = None
) -> dict:
    """
    Effort-Quality Mismatch (Signal 21).

    Detects perfect moves in difficult positions WITHOUT proportional time
    investment. Humans think longer when they find the best move in a hard
    position; engine users answer quickly and perfectly.

    Also calculates effort_ratio as a human-behavior penalty.

    Args:
        move_evals: List of move evaluation dicts (player moves, non-book).
        move_times: List of move times (seconds) aligned with move_evals.
                   If None, this signal is skipped.

    Returns:
        Dict with:
        - mismatch_rate: Fraction of hard positions with fast perfect moves
        - effort_ratio: Time on correct hard moves / avg time (>1.5 = human penalty)
        - mismatch_count: Number of mismatch instances
        - hard_positions: Total hard positions examined
    """
    if move_times is None or len(move_times) == 0:
        return {
            "mismatch_rate": None,
            "effort_ratio": None,
            "mismatch_count": 0,
            "hard_positions": 0,
        }

    # Calculate mean move time (excluding very short moves that might be premoves)
    valid_times = [t for t in move_times if t > 0.5]
    if not valid_times:
        return {
            "mismatch_rate": None,
            "effort_ratio": None,
            "mismatch_count": 0,
            "hard_positions": 0,
        }

    mean_time = sum(valid_times) / len(valid_times)

    mismatch_count = 0
    hard_positions = 0
    time_on_correct_hard = []

    # Align move_times with move_evals
    min_len = min(len(move_evals), len(move_times))

    for i in range(min_len):
        m = move_evals[i]

        if m.get("is_book_move", False):
            continue
        if is_forced_move(m):
            continue

        sharpness = calculate_sharpness_score(m)

        if sharpness < 60:
            continue

        hard_positions += 1
        is_best = m.get("best_rank", 5) == 0
        move_time = move_times[i]

        if is_best:
            time_on_correct_hard.append(move_time)
            # Mismatch: perfect move in hard position but fast
            if move_time < mean_time * 0.5:
                mismatch_count += 1

    if hard_positions == 0:
        return {
            "mismatch_rate": None,
            "effort_ratio": None,
            "mismatch_count": 0,
            "hard_positions": 0,
        }

    mismatch_rate = mismatch_count / hard_positions

    # Effort ratio: how much longer player thinks on correct hard moves vs average
    if time_on_correct_hard and mean_time > 0:
        effort_ratio = (sum(time_on_correct_hard) / len(time_on_correct_hard)) / mean_time
    else:
        effort_ratio = None

    return {
        "mismatch_rate": round(mismatch_rate, 4),
        "effort_ratio": round(effort_ratio, 4) if effort_ratio is not None else None,
        "mismatch_count": mismatch_count,
        "hard_positions": hard_positions,
    }


def calculate_toggle_detection_metrics(
    move_evals: list[dict], move_times: list[float] | None = None
) -> dict:
    """
    Calculate all toggle detection metrics for a game.

    Convenience function that runs all four signals and returns a combined dict.

    Args:
        move_evals: List of move evaluation dicts (player moves, non-book).
        move_times: Optional list of move times (seconds) aligned with move_evals.

    Returns:
        Dict with all metrics from signals 18-21.
    """
    variance_result = calculate_variance_ratio(move_evals)
    critical_result = calculate_critical_moment_accuracy(move_evals)
    oscillation_result = calculate_oscillation_pattern(move_evals)
    effort_result = calculate_effort_quality_mismatch(move_evals, move_times)

    return {
        "variance_ratio": variance_result["variance_ratio"],
        "critical_accuracy_boost": critical_result["critical_accuracy_boost"],
        "critical_moment_count": critical_result["critical_moment_count"],
        "oscillation_score": oscillation_result["oscillation_score"],
        "mismatch_rate": effort_result["mismatch_rate"],
        "effort_ratio": effort_result["effort_ratio"],
    }
