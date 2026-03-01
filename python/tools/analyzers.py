"""Analysis wrappers that expose intermediate calculation state.

These functions call the same engine modules used by the main pipeline
but capture and return the intermediate values that are normally hidden.
"""

from pathlib import Path

import chess

from utils import iterate_moves_with_board, parse_pgn, extract_pgn_metadata
from analysis.engine import analyze_game
from analysis.basic_metrics import (
    calculate_acpl,
    calculate_blunders,
    calculate_robust_acpl,
    calculate_topn_match_rates,
)
from analysis.phase_analysis import (
    calculate_phase_metrics,
    calculate_enhanced_phase_analysis,
    calculate_phase_variance,
)
from analysis.suspicion import calculate_precision_bursts


def inspect_phase_classification(
    pgn_text: str,
    opening_moves: int = 15,
    endgame_pieces: int = 12,
) -> dict:
    """Classify each move into a game phase and show WHY.

    This mirrors the logic in phase_analysis.calculate_phase_metrics
    and calculate_enhanced_phase_analysis but exposes every intermediate
    value so the user can see exactly how phases are assigned.

    Note on a known inconsistency:
      - calculate_phase_metrics uses iterate_moves_with_board which
        yields the board AFTER the move, so piece_count is post-move.
      - calculate_enhanced_phase_analysis and calculate_phase_variance
        call len(board.piece_map()) BEFORE board.push(move), so
        piece_count is pre-move.
      This function shows BOTH values to help diagnose the discrepancy.
    """
    game = parse_pgn(pgn_text)
    if game is None:
        return {"error": "Could not parse PGN", "moves": [], "summary": {}, "thresholds": {}}

    board = game.board()
    moves_info = []
    phase_counts = {"opening": 0, "middlegame": 0, "endgame": 0}

    for move_num, move in enumerate(game.mainline_moves(), start=1):
        pieces_before = len(board.piece_map())
        is_capture = board.is_capture(move)
        san = board.san(move)
        board.push(move)
        pieces_after = len(board.piece_map())

        # Phase using SAME logic as calculate_phase_metrics (post-move pieces)
        if move_num <= opening_moves:
            phase = "opening"
            reason = f"move_num {move_num} <= {opening_moves}"
        elif pieces_after <= endgame_pieces:
            phase = "endgame"
            reason = f"pieces_after={pieces_after} <= {endgame_pieces}"
        else:
            phase = "middlegame"
            reason = f"move_num {move_num} > {opening_moves} AND pieces_after={pieces_after} > {endgame_pieces}"

        # What calculate_enhanced_phase_analysis would say (pre-move pieces)
        if move_num <= opening_moves:
            alt_phase = "opening"
        elif pieces_before <= endgame_pieces:
            alt_phase = "endgame"
        else:
            alt_phase = "middlegame"

        phase_mismatch = phase != alt_phase
        phase_counts[phase] += 1

        moves_info.append({
            "move_number": move_num,
            "san": san,
            "piece_count": pieces_after,
            "pieces_before": pieces_before,
            "is_capture": is_capture,
            "phase": phase,
            "alt_phase": alt_phase,
            "phase_mismatch": phase_mismatch,
            "reason": reason,
        })

    return {
        "moves": moves_info,
        "summary": phase_counts,
        "thresholds": {
            "opening_moves": opening_moves,
            "endgame_pieces": endgame_pieces,
        },
    }


def inspect_opening_book(pgn_text: str) -> dict:
    """Inspect opening book detection for a PGN.

    Returns which detection method is used (polyglot or fallback)
    and which moves are classified as book moves.
    """
    from analysis.opening_book import OPENING_BOOK_PATH, get_detector

    book_path = OPENING_BOOK_PATH
    book_exists = book_path.exists()

    detection_method = "unknown"
    out_of_book_index = 0
    book_stats = None
    error_msg = None

    try:
        detector = get_detector()
        out_of_book_index = detector.get_out_of_book_move_index(pgn_text)
        book_stats = detector.get_book_statistics(pgn_text)
        detection_method = "polyglot"
    except Exception as e:
        detection_method = "fallback"
        out_of_book_index = 10
        error_msg = str(e)

    return {
        "book_file_path": str(book_path),
        "book_file_exists": book_exists,
        "detection_method": detection_method,
        "out_of_book_index": out_of_book_index,
        "book_stats": book_stats,
        "error": error_msg,
    }


def analyze_pgn_transparent(
    pgn_text: str,
    player_color: str,
    stockfish_path: str = "stockfish",
    depth: int = 12,
    multipv: int = 5,
    opening_moves: int = 15,
    endgame_pieces: int = 12,
) -> dict:
    """Run full analysis on a PGN and return all intermediate data."""
    # 1. Run Stockfish analysis
    move_evals = analyze_game(
        pgn_text,
        stockfish_path=stockfish_path,
        depth=depth,
        multipv=multipv,
        player_color=player_color,
        skip_book_moves=True,
    )

    # 2. Inspect phase classification
    phase_info = inspect_phase_classification(pgn_text, opening_moves, endgame_pieces)

    # 3. Inspect opening book
    book_info = inspect_opening_book(pgn_text)

    # 4. Calculate metrics
    non_book_evals = [m for m in move_evals if not m.get("is_book_move", False)]

    acpl = calculate_acpl(non_book_evals) if non_book_evals else None
    robust_acpl = calculate_robust_acpl(non_book_evals) if non_book_evals else None
    match_rates = calculate_topn_match_rates(non_book_evals) if non_book_evals else None
    blunders = calculate_blunders(non_book_evals) if non_book_evals else None
    phase_breakdown = calculate_phase_metrics(pgn_text, move_evals, opening_moves, endgame_pieces)
    enhanced_phase = calculate_enhanced_phase_analysis(pgn_text, move_evals, opening_moves, endgame_pieces)
    phase_variance = calculate_phase_variance(pgn_text, move_evals, opening_moves, endgame_pieces)
    precision = calculate_precision_bursts(non_book_evals) if non_book_evals else None

    # 5. Generate warnings
    warnings = _generate_warnings(move_evals, non_book_evals, phase_info, book_info, phase_breakdown)

    return {
        "move_evals": move_evals,
        "phase_classification": phase_info,
        "opening_book": book_info,
        "metrics": {
            "acpl": acpl,
            "robust_acpl": robust_acpl,
            "match_rates": match_rates,
            "blunders": blunders,
            "phase_breakdown": phase_breakdown,
            "enhanced_phase": enhanced_phase,
            "phase_variance": phase_variance,
            "precision_bursts": precision,
        },
        "warnings": warnings,
    }


def _generate_warnings(
    all_evals: list[dict],
    non_book_evals: list[dict],
    phase_info: dict,
    book_info: dict,
    phase_breakdown: dict,
) -> list[str]:
    """Generate diagnostic warnings from analysis results."""
    warnings = []

    # Warning: book fallback
    if not book_info.get("book_file_exists", True):
        warnings.append(
            f"Opening book file not found at {book_info.get('book_file_path', '?')}. "
            f"Using fallback: first {book_info.get('out_of_book_index', 10)} moves skipped as book."
        )

    # Warning: all moves are book
    if non_book_evals is not None and len(non_book_evals) == 0:
        warnings.append(
            "All analyzed moves are classified as book moves. No non-book analysis available."
        )

    # Warning: no endgame moves
    if phase_breakdown:
        eg = phase_breakdown.get("endgame", {})
        if eg and eg.get("move_count", 0) == 0:
            total = sum(
                phase_breakdown.get(p, {}).get("move_count", 0)
                for p in ("opening", "middlegame", "endgame")
            )
            warnings.append(
                f"No endgame moves detected ({total} total moves). "
                f"Endgame threshold: <= {phase_info.get('thresholds', {}).get('endgame_pieces', '?')} pieces."
            )

    # Warning: phase mismatch between functions
    mismatches = [m for m in phase_info.get("moves", []) if m.get("phase_mismatch")]
    if mismatches:
        warnings.append(
            f"{len(mismatches)} moves have different phase classification between "
            f"calculate_phase_metrics (post-move pieces) and calculate_enhanced_phase_analysis "
            f"(pre-move pieces). Affected moves: {[m['move_number'] for m in mismatches[:5]]}"
        )

    return warnings
