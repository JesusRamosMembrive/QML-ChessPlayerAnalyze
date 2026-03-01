"""Analysis wrappers that expose intermediate calculation state.

These functions call the same engine modules used by the main pipeline
but capture and return the intermediate values that are normally hidden.
"""

from pathlib import Path

import chess

from utils import iterate_moves_with_board, parse_pgn, extract_pgn_metadata


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
