"""
Game phase analysis for chess performance.

Analyzes performance across different game phases (opening, middlegame, endgame)
and detects phase transitions and collapses.
"""


from utils import get_logger, iterate_moves_with_board, parse_pgn

logger = get_logger(__name__)


def calculate_phase_metrics(
    pgn_text: str, move_evals: list[dict], opening_moves: int = 15, endgame_pieces: int = 12
) -> dict:
    """
    Calculate metrics broken down by game phase (opening, middlegame, endgame).

    Phases are defined as:
    - Opening: First N moves (default: 15)
    - Endgame: Positions with ≤ M pieces on board (default: 12)
    - Middlegame: Everything else

    Args:
        pgn_text: Full PGN text (needed to count pieces per move)
        move_evals: List of move evaluations from analyze_game()
        opening_moves: Number of moves to consider as opening (default: 15)
        endgame_pieces: Max pieces to consider endgame (default: 6)

    Returns:
        Dict with phase breakdown (NO None values):
        {
            "opening": {
                "move_count": int,
                "acpl": float,
                "blunder_count": int,
                "blunder_rate": float,
                "match_rate": float
            },
            "middlegame": { ... },
            "endgame": { ... }
        }

    Raises:
        AssertionError: If move_evals is missing (should be validated upstream)
    """
    # Data validation - fail fast
    assert move_evals, "move_evals required - should be validated in analyze_single_game()"
    assert pgn_text, "pgn_text required - should be validated in analyze_single_game()"

    logger.info(f"Phase analysis starting: {len(move_evals)} move evaluations")

    # Parse PGN using utility function
    game = parse_pgn(pgn_text)
    if game is None:
        return {"opening": None, "middlegame": None, "endgame": None}

    # Classify each move by phase using utility function
    opening_evals = []
    middlegame_evals = []
    endgame_evals = []

    for move_num, _move, board in iterate_moves_with_board(pgn_text):
        # Get corresponding move_eval
        if move_num - 1 < len(move_evals):
            move_eval = move_evals[move_num - 1]
        else:
            break

        # Determine phase (board is already AFTER the move)
        piece_count = len(board.piece_map())

        if move_num <= opening_moves:
            # Opening phase
            opening_evals.append(move_eval)
        elif piece_count <= endgame_pieces:
            # Endgame phase
            endgame_evals.append(move_eval)
        else:
            # Middlegame phase
            middlegame_evals.append(move_eval)

    # Calculate metrics for each phase
    def calc_phase_stats(phase_name: str, phase_evals: list[dict]) -> dict:
        """Calculate stats for a game phase, returning defaults if no data."""
        if not phase_evals:
            logger.debug(f"No moves in {phase_name} phase - returning defaults")
            # Return default values instead of None
            return {
                "move_count": 0,
                "acpl": 0.0,
                "blunder_count": 0,
                "blunder_rate": 0.0,
                "match_rate": 0.0,
                "top3_match_rate": 0.0,
                "top4_match_rate": 0.0,
                "top5_match_rate": 0.0,
                "final_match_rate": 0.0,
            }

        # ACPL calculation (capped at 1500)
        # FIXED: Handle None cp_loss values
        cp_losses = [min(m["cp_loss"], 1500) for m in phase_evals if m.get("cp_loss") is not None]
        acpl = sum(cp_losses) / len(cp_losses) if cp_losses else 0.0

        # Blunder calculation (>100cp loss)
        # FIXED: Handle None cp_loss values
        blunders = [m for m in phase_evals if m.get("cp_loss") is not None and m["cp_loss"] > 100]
        blunder_count = len(blunders)

        # Calculate blunder rate based on valid moves only
        valid_moves = [m for m in phase_evals if m.get("cp_loss") is not None]
        blunder_rate = blunder_count / len(valid_moves) if valid_moves else 0.0

        # Match rate calculations (top-1, top-3, top-4, top-5, final)
        top1_matches = [m for m in phase_evals if m["best_rank"] == 0]
        top3_matches = [m for m in phase_evals if m["best_rank"] <= 2]
        top4_matches = [m for m in phase_evals if m["best_rank"] <= 3]
        top5_matches = [m for m in phase_evals if m["best_rank"] <= 4]

        match_rate = len(top1_matches) / len(phase_evals) if phase_evals else 0.0
        top3_rate = len(top3_matches) / len(phase_evals) if phase_evals else 0.0
        top4_rate = len(top4_matches) / len(phase_evals) if phase_evals else 0.0
        top5_rate = len(top5_matches) / len(phase_evals) if phase_evals else 0.0

        # Calculate final match rate using validated formula
        # Formula: 0.05 * TOP3 + 0.15 * TOP4 + 0.80 * TOP5
        final_match_rate = 0.05 * top3_rate + 0.15 * top4_rate + 0.80 * top5_rate

        logger.debug(
            f"{phase_name}: {len(phase_evals)} moves, "
            f"ACPL={acpl:.2f}, blunders={blunder_count}, "
            f"top1={match_rate*100:.1f}%, final={final_match_rate*100:.1f}%"
        )

        return {
            "move_count": len(phase_evals),
            "acpl": round(acpl, 2),
            "blunder_count": blunder_count,
            "blunder_rate": round(blunder_rate, 4),
            "match_rate": round(match_rate, 4),  # Top-1 (legacy)
            "top3_match_rate": round(top3_rate, 4),
            "top4_match_rate": round(top4_rate, 4),
            "top5_match_rate": round(top5_rate, 4),
            "final_match_rate": round(final_match_rate, 4),  # Chess.com approximation
        }

    result = {
        "opening": calc_phase_stats("opening", opening_evals),
        "middlegame": calc_phase_stats("middlegame", middlegame_evals),
        "endgame": calc_phase_stats("endgame", endgame_evals),
    }

    logger.info(
        f"Phase analysis complete: opening={result['opening']['move_count']} moves, "
        f"middle={result['middlegame']['move_count']}, end={result['endgame']['move_count']}"
    )

    return result


def calculate_phase_variance(
    pgn_text: str, move_evals: list[dict], opening_moves: int = 15, endgame_pieces: int = 12
) -> dict:
    """
    Calculate variance (consistency) across game phases.

    PHASE 1B: Detects if player becomes MORE consistent in middlegame (engine indicator).
    Humans tend to have similar variance across phases, engines become mechanical.

    Args:
        pgn_text: Full PGN text
        move_evals: List of move evaluations
        opening_moves: Moves to consider as opening (default: 15)
        endgame_pieces: Max pieces for endgame (default: 12)

    Returns:
        Dict with variance analysis:
        {
            "opening_std": float,        # Std dev of cp_loss in opening
            "middlegame_std": float,     # Std dev in middlegame
            "endgame_std": float,        # Std dev in endgame
            "variance_drop": float,      # opening_std - middlegame_std (positive = more consistent)
            "consistency_increase": bool # True if variance drops significantly (>20cp)
        }
    """
    if not move_evals or not pgn_text:
        return {
            "opening_std": None,
            "middlegame_std": None,
            "endgame_std": None,
            "variance_drop": None,
            "consistency_increase": False,
        }

    # Parse PGN to classify moves by phase
    game = parse_pgn(pgn_text)
    if game is None:
        return {
            "opening_std": None,
            "middlegame_std": None,
            "endgame_std": None,
            "variance_drop": None,
            "consistency_increase": False,
        }

    board = game.board()

    # Collect cp_losses per phase
    phase_losses = {"opening": [], "middlegame": [], "endgame": []}

    for move_num, move in enumerate(game.mainline_moves(), start=1):
        if move_num - 1 < len(move_evals):
            move_eval = move_evals[move_num - 1]
        else:
            break

        # Determine phase
        piece_count = len(board.piece_map())

        if move_num <= opening_moves:
            phase = "opening"
        elif piece_count <= endgame_pieces:
            phase = "endgame"
        else:
            phase = "middlegame"

        # Cap cp_loss at 1500 for variance calculation
        # FIXED: Handle None cp_loss values
        cp_loss_raw = move_eval.get("cp_loss")
        if cp_loss_raw is not None:
            cp_loss = min(cp_loss_raw, 1500)
            phase_losses[phase].append(cp_loss)

        board.push(move)

    # Calculate standard deviation for each phase
    def calc_std(losses: list[float]) -> float | None:
        """Calculate standard deviation, return None if insufficient data."""
        if len(losses) < 2:
            return None

        mean = sum(losses) / len(losses)
        variance = sum((x - mean) ** 2 for x in losses) / len(losses)
        return variance**0.5

    opening_std = calc_std(phase_losses["opening"])
    middlegame_std = calc_std(phase_losses["middlegame"])
    endgame_std = calc_std(phase_losses["endgame"])

    # Calculate variance drop (ENGINE INDICATOR)
    # Positive value = became more consistent in middlegame
    variance_drop = None
    consistency_increase = False

    if opening_std is not None and middlegame_std is not None:
        variance_drop = round(opening_std - middlegame_std, 2)

        # Significant consistency increase = >20cp drop in std
        consistency_increase = variance_drop > 20

        logger.info(
            f"Variance analysis: opening_std={opening_std:.2f}, "
            f"middlegame_std={middlegame_std:.2f}, drop={variance_drop:.2f}"
        )

    return {
        "opening_std": round(opening_std, 2) if opening_std else None,
        "middlegame_std": round(middlegame_std, 2) if middlegame_std else None,
        "endgame_std": round(endgame_std, 2) if endgame_std else None,
        "variance_drop": variance_drop,
        "consistency_increase": consistency_increase,
    }


def calculate_position_complexity(move_eval: dict) -> float:
    """
    Calculate position complexity for a single move.

    Uses multiple indicators:
    - Number of legal moves (more = more complex)
    - Evaluation spread from multipv (if available)
    - Normalized to 0-100 scale

    Args:
        move_eval: Single move evaluation dict with 'legal_moves' and optionally 'multipv_spread'

    Returns:
        Complexity score (0-100, higher = more complex)
    """
    # Base complexity from legal moves
    # Typical ranges: 20-40 legal moves
    # Map: 0-20 -> simple, 20-40 -> medium, 40+ -> complex
    legal_moves = move_eval.get("legal_moves", 30)  # default to medium

    # Normalize legal moves to 0-100 scale
    # Use sigmoid-like function: fewer options = simpler
    if legal_moves <= 5:
        complexity = 10  # Very simple (endgame)
    elif legal_moves <= 20:
        complexity = 20 + (legal_moves - 5) * 2  # 20-50
    elif legal_moves <= 40:
        complexity = 50 + (legal_moves - 20) * 1.5  # 50-80
    else:
        complexity = min(80 + (legal_moves - 40) * 0.5, 100)  # 80-100

    # Future: can add multipv spread if we store it
    # For now, legal moves is a good proxy

    return complexity


def calculate_enhanced_phase_analysis(
    pgn_text: str, move_evals: list[dict], opening_moves: int = 15, endgame_pieces: int = 12
) -> dict:
    """
    Enhanced phase analysis with transition patterns and collapse detection.

    Extends basic phase breakdown with:
    - Phase transition analysis (how performance changes between phases)
    - Collapse pattern detection (sudden drops in accuracy)
    - Phase consistency scoring (variance within each phase)

    Args:
        pgn_text: Full PGN text (needed to count pieces per move)
        move_evals: List of move evaluations from analyze_game()
        opening_moves: Number of moves to consider as opening (default: 15)
        endgame_pieces: Max pieces to consider endgame (default: 12)

    Returns:
        Dict with enhanced phase analysis:
        {
            "phase_transitions": {
                "opening_to_middle": float,  # ACPL change (+/-)
                "middle_to_endgame": float
            },
            "collapse_detected": bool,
            "collapse_location": str,  # "opening", "middlegame", "endgame", or None
            "phase_consistency": {
                "opening": float,  # 0-100, higher = more consistent
                "middlegame": float,
                "endgame": float
            },
            "worst_phase": str,  # "opening", "middlegame", or "endgame"
            "best_phase": str
        }
    """
    if not move_evals or not pgn_text:
        return {
            "phase_transitions": None,
            "collapse_detected": False,
            "collapse_location": None,
            "phase_consistency": None,
            "worst_phase": None,
            "best_phase": None,
        }

    # Parse PGN to get board state at each move
    game = parse_pgn(pgn_text)
    if game is None:
        return {
            "phase_transitions": None,
            "collapse_detected": False,
            "collapse_location": None,
            "phase_consistency": None,
            "worst_phase": None,
            "best_phase": None,
        }

    board = game.board()

    # Classify each move by phase and track cp_loss
    phase_data = {"opening": [], "middlegame": [], "endgame": []}

    for move_num, move in enumerate(game.mainline_moves(), start=1):
        # Get corresponding move_eval
        if move_num - 1 < len(move_evals):
            move_eval = move_evals[move_num - 1]
        else:
            break

        # Determine phase
        piece_count = len(board.piece_map())

        if move_num <= opening_moves:
            phase = "opening"
        elif piece_count <= endgame_pieces:
            phase = "endgame"
        else:
            phase = "middlegame"

        # FIXED: Handle None cp_loss values
        cp_loss = move_eval.get("cp_loss")
        if cp_loss is not None:
            phase_data[phase].append(cp_loss)

        # Advance board
        board.push(move)

    # Calculate ACPL for each phase
    phase_acpls = {}
    for phase, losses in phase_data.items():
        if losses:
            # FIXED: Filter out None values before min comparison
            valid_losses = [loss for loss in losses if loss is not None]
            capped_losses = [min(loss, 1500) for loss in valid_losses]
            phase_acpls[phase] = sum(capped_losses) / len(capped_losses)
        else:
            phase_acpls[phase] = None

    # 1. PHASE TRANSITIONS
    transitions = {}
    if phase_acpls["opening"] is not None and phase_acpls["middlegame"] is not None:
        transitions["opening_to_middle"] = round(
            phase_acpls["middlegame"] - phase_acpls["opening"], 2
        )
    else:
        transitions["opening_to_middle"] = None

    if phase_acpls["middlegame"] is not None and phase_acpls["endgame"] is not None:
        transitions["middle_to_endgame"] = round(
            phase_acpls["endgame"] - phase_acpls["middlegame"], 2
        )
    else:
        transitions["middle_to_endgame"] = None

    # 2. COLLAPSE DETECTION
    # A collapse is a transition increase > 50 ACPL
    collapse_detected = False
    collapse_location = None
    collapse_threshold = 50

    if transitions["opening_to_middle"] and transitions["opening_to_middle"] > collapse_threshold:
        collapse_detected = True
        collapse_location = "opening_to_middle"
    elif transitions["middle_to_endgame"] and transitions["middle_to_endgame"] > collapse_threshold:
        collapse_detected = True
        collapse_location = "middle_to_endgame"

    # 3. PHASE CONSISTENCY (using coefficient of variation)
    consistency = {}
    for phase, losses in phase_data.items():
        if len(losses) > 1:
            capped_losses = [min(loss, 1500) for loss in losses]
            mean = sum(capped_losses) / len(capped_losses)

            # Calculate standard deviation
            variance = sum((x - mean) ** 2 for x in capped_losses) / len(capped_losses)
            std_dev = variance**0.5

            # Coefficient of variation (CV)
            cv = (std_dev / mean) if mean > 0 else 0

            # Convert to consistency score (0-100)
            # Lower CV = higher consistency
            # CV > 2.0 is very inconsistent (score near 0)
            # CV < 0.5 is very consistent (score near 100)
            consistency_score = max(0, min(100, 100 * (1 - cv / 2.0)))
            consistency[phase] = round(consistency_score, 1)
        else:
            consistency[phase] = None

    # 4. BEST/WORST PHASE
    valid_phases = {k: v for k, v in phase_acpls.items() if v is not None}

    if valid_phases:
        # Lower ACPL is better
        worst_phase = max(valid_phases, key=valid_phases.get)  # Highest ACPL = worst
        best_phase = min(valid_phases, key=valid_phases.get)  # Lowest ACPL = best
    else:
        worst_phase = None
        best_phase = None

    return {
        "phase_transitions": transitions,
        "collapse_detected": collapse_detected,
        "collapse_location": collapse_location,
        "phase_consistency": consistency,
        "worst_phase": worst_phase,
        "best_phase": best_phase,
    }
