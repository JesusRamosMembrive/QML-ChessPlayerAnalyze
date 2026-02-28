"""
Position difficulty and sharpness scoring.

Replaces the simplistic legal-moves-only complexity proxy with a composite
score that leverages MultiPV evaluation data from Stockfish.
"""


def calculate_eval_spread_score(move_eval: dict) -> float:
    """
    Normalize eval_spread to a 0-100 score.

    Higher spread means more evaluation difference between best and worst PV,
    indicating a more demanding position where finding the right move matters.

    Args:
        move_eval: Single move evaluation dict with 'eval_spread' field.

    Returns:
        Score 0-100 (higher = more demanding position).
    """
    spread = move_eval.get("eval_spread", 0)

    # Normalize: 0cp -> 0, 200cp+ -> 100
    # Sigmoid-like curve for smooth scaling
    if spread <= 0:
        return 0.0
    elif spread <= 50:
        return spread * 0.6  # 0-30
    elif spread <= 100:
        return 30 + (spread - 50) * 0.6  # 30-60
    elif spread <= 200:
        return 60 + (spread - 100) * 0.3  # 60-90
    else:
        return min(90 + (spread - 200) * 0.05, 100)  # 90-100


def calculate_top_gap_score(move_eval: dict) -> float:
    """
    Normalize top_gap to a 0-100 score.

    Higher gap between 1st and 2nd best move means the position has a more
    critical "only move" character - finding it matters a lot.

    Args:
        move_eval: Single move evaluation dict with 'top_gap' field.

    Returns:
        Score 0-100 (higher = more critical move).
    """
    gap = move_eval.get("top_gap", 0)

    if gap <= 0:
        return 0.0
    elif gap <= 30:
        return gap * 0.5  # 0-15
    elif gap <= 80:
        return 15 + (gap - 30) * 0.7  # 15-50
    elif gap <= 150:
        return 50 + (gap - 80) * 0.5  # 50-85
    else:
        return min(85 + (gap - 150) * 0.1, 100)  # 85-100


def calculate_sharpness_score(move_eval: dict) -> float:
    """
    Composite position sharpness score (0-100).

    Combines multiple indicators:
    - 35% eval_spread (how different are the top moves)
    - 25% top_gap (how critical is the best move)
    - 20% legal_moves (more options = harder to navigate)
    - 20% tactical tension (captures/checks available via eval volatility)

    This replaces calculate_position_complexity() with a richer signal.

    Args:
        move_eval: Single move evaluation dict with fields:
            - eval_spread, top_gap, legal_moves
            - multipv_evals (optional, for tension calculation)

    Returns:
        Sharpness score 0-100 (higher = more difficult/sharp position).
    """
    spread_score = calculate_eval_spread_score(move_eval)
    gap_score = calculate_top_gap_score(move_eval)

    # Legal moves component (more legal moves = harder to choose)
    legal_moves = move_eval.get("legal_moves", 30)
    if legal_moves <= 5:
        legal_score = 10.0
    elif legal_moves <= 20:
        legal_score = 10 + (legal_moves - 5) * 2.67  # 10-50
    elif legal_moves <= 40:
        legal_score = 50 + (legal_moves - 20) * 1.5  # 50-80
    else:
        legal_score = min(80 + (legal_moves - 40) * 0.5, 100)

    # Tactical tension: variance of multipv evals indicates volatile position
    multipv_evals = move_eval.get("multipv_evals", [])
    if len(multipv_evals) >= 3:
        mean_eval = sum(multipv_evals) / len(multipv_evals)
        variance = sum((e - mean_eval) ** 2 for e in multipv_evals) / len(multipv_evals)
        tension_raw = variance ** 0.5  # std dev in centipawns
        # Normalize: 0cp -> 0, 150cp+ -> 100
        if tension_raw <= 0:
            tension_score = 0.0
        elif tension_raw <= 50:
            tension_score = tension_raw * 1.0  # 0-50
        elif tension_raw <= 150:
            tension_score = 50 + (tension_raw - 50) * 0.5  # 50-100
        else:
            tension_score = 100.0
    else:
        # Fallback: use spread as tension proxy
        tension_score = spread_score * 0.5

    # Weighted composite
    sharpness = (
        0.35 * spread_score
        + 0.25 * gap_score
        + 0.20 * legal_score
        + 0.20 * tension_score
    )

    return round(min(max(sharpness, 0), 100), 2)


def classify_move_difficulty(sharpness: float) -> str:
    """
    Classify a move by difficulty based on sharpness score.

    Args:
        sharpness: Sharpness score 0-100.

    Returns:
        One of: "forced", "easy", "moderate", "hard", "critical".
    """
    if sharpness < 25:
        return "easy"
    elif sharpness < 50:
        return "moderate"
    elif sharpness < 75:
        return "hard"
    else:
        return "critical"


def is_forced_move(move_eval: dict) -> bool:
    """
    Determine if a move is effectively forced (only one reasonable choice).

    Forced moves should be excluded from precision metrics since finding
    them doesn't indicate engine assistance.

    Args:
        move_eval: Single move evaluation dict with 'top_gap' and 'legal_moves'.

    Returns:
        True if the position has essentially one good move.
    """
    top_gap = move_eval.get("top_gap", 0)
    legal_moves = move_eval.get("legal_moves", 30)

    # Large gap between best and second-best: only one good move
    if top_gap > 150:
        return True

    # Very few legal moves AND meaningful gap
    if legal_moves <= 3 and top_gap >= 50:
        return True

    return False
