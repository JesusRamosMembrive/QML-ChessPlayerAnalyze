"""
Basic chess performance metrics.

Simple statistical calculations for game analysis including ACPL, match rate,
blunders, and precision moves.
"""

def calculate_acpl(move_evals: list[dict], cap_cp: int = 1500) -> float:
    """
    Calculate Average Centipawn Loss (ACPL).

    Args:
        move_evals: List of move evaluations from analyze_game()
        cap_cp: Maximum cp_loss to consider (prevents mate scores from skewing)

    Returns:
        Average centipawn loss
    """
    if not move_evals:
        return 0.0

    # Cap cp_loss to prevent mate evaluations from dominating
    # FIXED: Handle None cp_loss values (book moves or forced mate positions)
    capped_losses = [min(m["cp_loss"], cap_cp) for m in move_evals if m.get("cp_loss") is not None]

    if not capped_losses:
        return 0.0

    return sum(capped_losses) / len(capped_losses)


def calculate_blunders(move_evals: list[dict], blunder_threshold: int = 100) -> dict:
    """
    Calculate blunder statistics.

    A blunder is a move with cp_loss > threshold (default 100).

    Args:
        move_evals: List of move evaluations
        blunder_threshold: Centipawn loss threshold for blunder (default: 100)

    Returns:
        Dict with:
        - blunder_count: Number of blunders
        - blunder_rate: Blunder rate (0.0 to 1.0)
        - blunder_moves: List of move numbers where blunders occurred
    """
    if not move_evals:
        return {"blunder_count": 0, "blunder_rate": 0.0, "blunder_moves": []}

    # FIXED: Handle None cp_loss values (book moves or forced mate positions)
    blunders = [
        m for m in move_evals if m.get("cp_loss") is not None and m["cp_loss"] > blunder_threshold
    ]
    blunder_count = len(blunders)

    # Calculate rate based on moves with valid cp_loss
    valid_moves = [m for m in move_evals if m.get("cp_loss") is not None]
    blunder_rate = blunder_count / len(valid_moves) if valid_moves else 0.0
    blunder_moves = [m["move_number"] for m in blunders]

    return {
        "blunder_count": blunder_count,
        "blunder_rate": blunder_rate,
        "blunder_moves": blunder_moves,
    }


def count_precision_moves(move_evals: list[dict], complexity_threshold: int = 20) -> int:
    """
    Count precision moves: best moves in complex positions.

    A precision move is a move with best_rank=0 in a position with
    many legal moves (>= complexity_threshold).

    Args:
        move_evals: List of move evaluations
        complexity_threshold: Minimum legal moves to consider position complex

    Returns:
        Number of precision moves
    """
    if not move_evals:
        return 0

    precision_moves = [
        m for m in move_evals if m["best_rank"] == 0 and m["legal_moves"] >= complexity_threshold
    ]

    return len(precision_moves)


def calculate_robust_acpl(move_evals: list[dict], cap_cp: int = 300) -> float:
    """
    Calculate Robust ACPL (resistant to extreme outliers).

    Uses median instead of mean and caps outliers at a lower threshold
    to provide a more stable measure of typical performance.

    Args:
        move_evals: List of move evaluations from analyze_game()
        cap_cp: Maximum cp_loss to consider (default: 300)

    Returns:
        Median of capped centipawn losses
    """
    if not move_evals:
        return 0.0

    # Cap losses to prevent extreme outliers
    # FIXED: Handle None cp_loss values
    capped_losses = [min(m["cp_loss"], cap_cp) for m in move_evals if m.get("cp_loss") is not None]

    if not capped_losses:
        return 0.0

    # Use median instead of mean for robustness
    capped_losses.sort()
    n = len(capped_losses)
    mid = n // 2

    median = (capped_losses[mid - 1] + capped_losses[mid]) / 2 if n % 2 == 0 else capped_losses[mid]

    return median


def calculate_rank_distribution(move_evals: list[dict]) -> dict:
    """
    Calculate distribution of move rankings.

    Provides richer information than just match rate by showing
    the full distribution of how often the player plays the 1st, 2nd,
    3rd best move, etc.

    Args:
        move_evals: List of move evaluations

    Returns:
        Dict with:
        - rank_0: Percentage of moves matching best move (rank 0)
        - rank_1: Percentage of moves matching 2nd best move
        - rank_2: Percentage of moves matching 3rd best move
        - rank_3plus: Percentage of moves worse than 3rd best
    """
    if not move_evals:
        return {"rank_0": 0.0, "rank_1": 0.0, "rank_2": 0.0, "rank_3plus": 0.0}

    total = len(move_evals)

    rank_0_count = sum(1 for m in move_evals if m["best_rank"] == 0)
    rank_1_count = sum(1 for m in move_evals if m["best_rank"] == 1)
    rank_2_count = sum(1 for m in move_evals if m["best_rank"] == 2)
    rank_3plus_count = sum(1 for m in move_evals if m["best_rank"] >= 3)

    return {
        "rank_0": rank_0_count / total,
        "rank_1": rank_1_count / total,
        "rank_2": rank_2_count / total,
        "rank_3plus": rank_3plus_count / total,
    }


def calculate_topn_match_rates(move_evals: list[dict]) -> dict:
    """
    Calculate Top-N match rates for chess engine comparison.

    Top-N match rate = percentage of moves in the engine's top N choices.
    This provides multiple accuracy thresholds:
    - Top-1: Exact engine match (strictest)
    - Top-2: Move is in top 2 engine choices (Chess.com alignment)
    - Top-3: Move is in top 3 engine choices
    - Top-4: Move is in top 4 engine choices
    - Top-5: Move is in top 5 engine choices

    Opening book moves are automatically filtered out using the 'is_book_move' field
    that was set during analysis. This ensures a single source of truth for
    opening book detection and prevents field name inconsistencies.

    Args:
        move_evals: List of move evaluations with required fields:
                    - 'best_rank': int (0-based rank, 0 = best move)
                    - 'is_book_move': bool (True if move is from opening theory)

    Returns:
        Dict with top-N match rates (0.0 to 1.0):
        - top1: Percentage matching best move (rank 0)
        - top2: Percentage in top 2 moves (rank 0-1)
        - top3: Percentage in top 3 moves (rank 0-2)
        - top4: Percentage in top 4 moves (rank 0-3)
        - top5: Percentage in top 5 moves (rank 0-4)

    Examples:
        >>> moves = [
        ...     {"best_rank": 0, "is_book_move": True},   # Excluded (book move)
        ...     {"best_rank": 0, "is_book_move": False},  # Counted
        ...     {"best_rank": 1, "is_book_move": False},  # Counted
        ...     {"best_rank": 5, "is_book_move": False}   # Counted
        ... ]
        >>> calculate_topn_match_rates(moves)
        {'top1': 0.333, 'top2': 0.667, 'top3': 0.667, 'top5': 0.667}
    """
    if not move_evals:
        return {"top1": 0.0, "top2": 0.0, "top3": 0.0, "top4": 0.0, "top5": 0.0}

    # Filter out opening book moves (single source of truth from analyze_game)
    # This prevents duplication and field name inconsistencies
    filtered_moves = [m for m in move_evals if not m.get("is_book_move", False)]

    # If all moves were in book, return zeros
    if not filtered_moves:
        return {"top1": 0.0, "top2": 0.0, "top3": 0.0, "top4": 0.0, "top5": 0.0}

    total = len(filtered_moves)

    # Count moves in each Top-N category
    top1_count = sum(1 for m in filtered_moves if m.get("best_rank", 999) == 0)
    top2_count = sum(1 for m in filtered_moves if m.get("best_rank", 999) <= 1)
    top3_count = sum(1 for m in filtered_moves if m.get("best_rank", 999) <= 2)
    top4_count = sum(1 for m in filtered_moves if m.get("best_rank", 999) <= 3)
    top5_count = sum(1 for m in filtered_moves if m.get("best_rank", 999) <= 4)

    return {
        "top1": top1_count / total,
        "top2": top2_count / total,
        "top3": top3_count / total,
        "top4": top4_count / total,
        "top5": top5_count / total,
    }


def calculate_final_match_rate(top3: float, top5: float, top4: float | None = None) -> float:
    """
    Calculate final match rate approximating Chess.com's Precision metric.

    This formula was determined through validation with real Chess.com data
    from player Blaine-Carroll (10 games, 94.2-99.7% precision range).

    Formula (updated 2025-11-19): 0.05 * TOP3 + 0.15 * TOP4 + 0.80 * TOP5
    Previous formula: 0.2 * TOP3 + 0.8 * TOP5

    The new 3-parameter weighted combination:
    - Top-5 (80%): Captures "reasonable move" quality (dominant factor)
    - Top-4 (15%): Adds intermediate precision granularity
    - Top-3 (5%): Fine-tunes for high-accuracy play

    Validation results (2025-11-19):
    - New formula: 96.01% average match rate (+0.20% vs old formula)
    - Only 0.51% below Pure Top-5 (96.52%)
    - More robust using 3 parameters instead of 2

    Known limitations:
    - Games with < 10 moves have unreliable results (sample size too small)
    - Depth 14 analysis may differ from Chess.com's depth (possibly 18-20)

    Args:
        top3: Top-3 match rate (0.0-1.0)
        top5: Top-5 match rate (0.0-1.0)
        top4: Top-4 match rate (0.0-1.0), optional (uses top3 if not provided for backwards compatibility)

    Returns:
        Final match rate (0.0-1.0) approximating Chess.com precision

    Examples:
        >>> calculate_final_match_rate(0.846, 0.962, 0.923)  # With top4
        0.9601
        >>> calculate_final_match_rate(0.911, 0.927)  # Backwards compatible
        0.9234

    See Also:
        - docs/MATCH_RATE_VALIDATION_2025-11-18.md: Full validation report
        - calculate_topn_match_rates(): Calculates top3, top4, and top5 inputs
    """
    # Use new 3-parameter formula if top4 is provided
    if top4 is not None:
        return 0.05 * top3 + 0.15 * top4 + 0.80 * top5
    # Backwards compatibility: use old 2-parameter formula
    return 0.2 * top3 + 0.8 * top5
