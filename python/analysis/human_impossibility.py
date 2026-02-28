"""
Human impossibility detection metrics.

Signals that identify play patterns statistically impossible for humans,
based on how accuracy correlates (or doesn't) with position difficulty.

Signals 14-17 of the suspicion scoring system.
"""

from analysis.difficulty import calculate_sharpness_score, is_forced_move


def calculate_cwmr(move_evals: list[dict]) -> dict:
    """
    Complexity-Weighted Match Rate (Signal 14).

    Weights each top-1 match by the sharpness of the position. Humans perform
    worse in difficult positions, so their CWMR is significantly lower than
    their raw match rate. Engines maintain accuracy regardless of difficulty.

    Args:
        move_evals: List of move evaluation dicts (player moves, non-book).

    Returns:
        Dict with:
        - cwmr: Weighted match rate (0-1)
        - cwmr_delta: raw_match_rate - cwmr (higher = more human-like)
        - raw_match_rate: Unweighted top-1 match rate
        - eligible_moves: Number of moves used in calculation
    """
    weighted_matches = 0.0
    total_weight = 0.0
    raw_matches = 0
    eligible = 0

    for m in move_evals:
        # Skip book moves and forced moves
        if m.get("is_book_move", False):
            continue
        if is_forced_move(m):
            continue

        sharpness = calculate_sharpness_score(m)
        weight = sharpness / 50.0  # Normalize so sharpness=50 has weight=1.0
        weight = max(weight, 0.1)  # Floor to avoid zero-weight easy moves

        is_match = 1 if m.get("best_rank", 5) == 0 else 0

        weighted_matches += weight * is_match
        total_weight += weight
        raw_matches += is_match
        eligible += 1

    if eligible == 0 or total_weight == 0:
        return {
            "cwmr": None,
            "cwmr_delta": None,
            "raw_match_rate": None,
            "eligible_moves": 0,
        }

    cwmr = weighted_matches / total_weight
    raw_match_rate = raw_matches / eligible
    cwmr_delta = raw_match_rate - cwmr

    return {
        "cwmr": round(cwmr, 4),
        "cwmr_delta": round(cwmr_delta, 4),
        "raw_match_rate": round(raw_match_rate, 4),
        "eligible_moves": eligible,
    }


def calculate_cpa(move_evals: list[dict]) -> dict:
    """
    Critical Position Accuracy (Signal 15).

    Match rate ONLY in positions that are both difficult (sharpness >= 65)
    AND complex (legal_moves >= 25). These are the hardest decisions in chess.

    Args:
        move_evals: List of move evaluation dicts (player moves, non-book).

    Returns:
        Dict with:
        - cpa: Critical position accuracy (0-1)
        - critical_positions: Number of critical positions found
    """
    matches = 0
    critical_count = 0

    for m in move_evals:
        if m.get("is_book_move", False):
            continue
        if is_forced_move(m):
            continue

        sharpness = calculate_sharpness_score(m)
        legal_moves = m.get("legal_moves", 0)

        if sharpness >= 65 and legal_moves >= 25:
            critical_count += 1
            if m.get("best_rank", 5) == 0:
                matches += 1

    if critical_count == 0:
        return {"cpa": None, "critical_positions": 0}

    return {
        "cpa": round(matches / critical_count, 4),
        "critical_positions": critical_count,
    }


def calculate_difficulty_sensitivity(move_evals: list[dict]) -> dict:
    """
    Difficulty Sensitivity (Signal 16).

    Measures how much accuracy drops between easy and hard positions.
    Humans show a significant drop (0.10-0.40); engines show almost none (<0.05).

    Args:
        move_evals: List of move evaluation dicts (player moves, non-book).

    Returns:
        Dict with:
        - sensitivity: accuracy_easy - accuracy_hard (higher = more human)
        - accuracy_easy: Match rate in easy positions (sharpness < 35)
        - accuracy_hard: Match rate in hard positions (sharpness >= 60)
        - easy_count: Number of easy positions
        - hard_count: Number of hard positions
    """
    easy_matches = 0
    easy_count = 0
    hard_matches = 0
    hard_count = 0

    for m in move_evals:
        if m.get("is_book_move", False):
            continue
        if is_forced_move(m):
            continue

        sharpness = calculate_sharpness_score(m)
        is_match = 1 if m.get("best_rank", 5) == 0 else 0

        if sharpness < 35:
            easy_count += 1
            easy_matches += is_match
        elif sharpness >= 60:
            hard_count += 1
            hard_matches += is_match

    if easy_count < 3 or hard_count < 3:
        return {
            "sensitivity": None,
            "accuracy_easy": None,
            "accuracy_hard": None,
            "easy_count": easy_count,
            "hard_count": hard_count,
        }

    accuracy_easy = easy_matches / easy_count
    accuracy_hard = hard_matches / hard_count
    sensitivity = accuracy_easy - accuracy_hard

    return {
        "sensitivity": round(sensitivity, 4),
        "accuracy_easy": round(accuracy_easy, 4),
        "accuracy_hard": round(accuracy_hard, 4),
        "easy_count": easy_count,
        "hard_count": hard_count,
    }


def calculate_ubma(move_evals: list[dict]) -> dict:
    """
    Unique Best Move Accuracy (Signal 17).

    Accuracy in positions where there is exactly one good move
    (100cp < top_gap < 300cp). These are positions where finding the
    best move requires precise calculation, not general principles.

    Args:
        move_evals: List of move evaluation dicts (player moves, non-book).

    Returns:
        Dict with:
        - ubma: Unique best move accuracy (0-1)
        - unique_positions: Number of unique-best-move positions found
    """
    matches = 0
    unique_count = 0

    for m in move_evals:
        if m.get("is_book_move", False):
            continue

        top_gap = m.get("top_gap", 0)

        # Position has exactly one good move (not trivially forced, not ambiguous)
        if 100 < top_gap < 300:
            unique_count += 1
            if m.get("best_rank", 5) == 0:
                matches += 1

    if unique_count == 0:
        return {"ubma": None, "unique_positions": 0}

    return {
        "ubma": round(matches / unique_count, 4),
        "unique_positions": unique_count,
    }


def calculate_human_impossibility_metrics(move_evals: list[dict]) -> dict:
    """
    Calculate all human impossibility metrics for a game.

    Convenience function that runs all four signals and returns a combined dict.

    Args:
        move_evals: List of move evaluation dicts (player moves, non-book).

    Returns:
        Dict with all metrics from signals 14-17 plus avg_sharpness.
    """
    cwmr_result = calculate_cwmr(move_evals)
    cpa_result = calculate_cpa(move_evals)
    sensitivity_result = calculate_difficulty_sensitivity(move_evals)
    ubma_result = calculate_ubma(move_evals)

    # Calculate average sharpness across all non-book, non-forced moves
    sharpness_values = []
    for m in move_evals:
        if m.get("is_book_move", False):
            continue
        if is_forced_move(m):
            continue
        sharpness_values.append(calculate_sharpness_score(m))

    avg_sharpness = (
        round(sum(sharpness_values) / len(sharpness_values), 2)
        if sharpness_values
        else None
    )

    return {
        "cwmr": cwmr_result["cwmr"],
        "cwmr_delta": cwmr_result["cwmr_delta"],
        "cpa": cpa_result["cpa"],
        "critical_positions": cpa_result["critical_positions"],
        "sensitivity": sensitivity_result["sensitivity"],
        "ubma": ubma_result["ubma"],
        "unique_positions": ubma_result["unique_positions"],
        "avg_sharpness": avg_sharpness,
    }
