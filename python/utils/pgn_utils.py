"""
PGN parsing utilities for chess game analysis.

Centralized utilities for parsing PGN strings and iterating through game moves.
Implements DRY principle by consolidating common PGN operations.
"""

import io
from collections.abc import Iterator
from datetime import datetime

import chess
import chess.pgn

from utils.datetime_utils import now_naive


def parse_pgn(pgn_text: str) -> chess.pgn.Game | None:
    """
    Parse a PGN string into a chess.pgn.Game object.

    Args:
        pgn_text: PGN string to parse

    Returns:
        Parsed Game object, or None if parsing fails

    Example:
        >>> game = parse_pgn("1. e4 e5 2. Nf3 Nc6")
        >>> game is not None
        True
    """
    try:
        return chess.pgn.read_game(io.StringIO(pgn_text))
    except Exception:
        return None


def count_moves(pgn_text: str) -> int:
    """
    Count the total number of moves in a PGN string.

    Args:
        pgn_text: PGN string to analyze

    Returns:
        Total number of moves (both players combined)

    Example:
        >>> count_moves("1. e4 e5 2. Nf3 Nc6")
        4
    """
    game = parse_pgn(pgn_text)
    if not game:
        return 0

    try:
        # Count moves using node traversal
        move_count = 0
        node = game
        while node.variations:
            node = node.variations[0]
            move_count += 1
        return move_count
    except Exception:
        return 0


def iterate_moves_with_board(
    pgn_text: str,
) -> Iterator[tuple[int, chess.Move, chess.Board]]:
    """
    Iterate through game moves with board state at each position.

    Yields tuples of (move_number, move, board_after_move) for each move.
    Move numbers start at 1 (first move of the game).

    Args:
        pgn_text: PGN string to iterate

    Yields:
        Tuples of (move_number, move, board) where:
        - move_number: 1-indexed move number
        - move: chess.Move object
        - board: Board state AFTER the move is played

    Example:
        >>> pgn = "1. e4 e5 2. Nf3 Nc6"
        >>> for move_num, move, board in iterate_moves_with_board(pgn):
        ...     print(f"Move {move_num}: {move}")
        Move 1: e2e4
        Move 2: e7e5
        Move 3: g1f3
        Move 4: b8c6
    """
    game = parse_pgn(pgn_text)
    if not game:
        return

    board = game.board()

    for move_num, move in enumerate(game.mainline_moves(), start=1):
        board.push(move)
        yield move_num, move, board.copy()


def get_mainline_moves(pgn_text: str) -> list[chess.Move]:
    """
    Extract all mainline moves from a PGN string.

    Args:
        pgn_text: PGN string to parse

    Returns:
        List of chess.Move objects in the mainline

    Example:
        >>> moves = get_mainline_moves("1. e4 e5 2. Nf3")
        >>> len(moves)
        3
    """
    game = parse_pgn(pgn_text)
    if not game:
        return []

    try:
        return list(game.mainline_moves())
    except Exception:
        return []


def get_board_at_move(pgn_text: str, move_number: int) -> chess.Board | None:
    """
    Get the board state after a specific move number.

    Args:
        pgn_text: PGN string to parse
        move_number: 1-indexed move number (1 = first move)

    Returns:
        Board state after the specified move, or None if move doesn't exist

    Example:
        >>> board = get_board_at_move("1. e4 e5 2. Nf3", 2)
        >>> board is not None
        True
    """
    game = parse_pgn(pgn_text)
    if not game:
        return None

    board = game.board()

    try:
        for current_move_num, move in enumerate(game.mainline_moves(), start=1):
            board.push(move)
            if current_move_num == move_number:
                return board.copy()
        return None
    except Exception:
        return None


def validate_pgn(pgn_text: str) -> bool:
    """
    Check if a PGN string is valid and parseable.

    Args:
        pgn_text: PGN string to validate

    Returns:
        True if PGN is valid and has at least one move, False otherwise

    Example:
        >>> validate_pgn("1. e4 e5")
        True
        >>> validate_pgn("invalid pgn")
        False
    """
    game = parse_pgn(pgn_text)
    if not game:
        return False

    try:
        # Check that game has at least one move
        moves = list(game.mainline_moves())
        return len(moves) > 0
    except Exception:
        return False


def extract_pgn_metadata(pgn_text: str) -> dict:
    """
    Extract metadata from PGN headers.

    Args:
        pgn_text: Full PGN text

    Returns:
        Dict with:
        - eco_code: ECO code (e.g., "C50")
        - opening_name: Opening name (e.g., "Italian Game")
        - white_username: White player username
        - black_username: Black player username
        - white_elo: White player ELO (if available)
        - black_elo: Black player ELO (if available)
        - result: Game result ("1-0", "0-1", "1/2-1/2")
        - date: Game date as datetime
        - time_control_seconds: Time control in seconds (e.g., 300)
        - url: Chess.com game URL (if available)
    """
    # Use our parse_pgn utility instead of direct chess.pgn.read_game
    game = parse_pgn(pgn_text)

    if game is None:
        return {}

    headers = game.headers

    # Extract date
    date_str = headers.get("Date", "????.??.??")
    time_str = headers.get("UTCTime", "00:00:00")
    try:
        if "?" not in date_str:
            date = datetime.strptime(f"{date_str} {time_str}", "%Y.%m.%d %H:%M:%S")
        else:
            date = now_naive()
    except ValueError:
        date = now_naive()

    # Extract time control in seconds
    # Format can be "600" (10 min) or "120+1" (2 min + 1 sec increment)
    # Chess.com formula: Total Time = base_time + (40 × increment)
    # This follows FIDE's 40-move assumption for time calculation
    time_control_str = headers.get("TimeControl", "")
    time_control_seconds = None
    if time_control_str:
        try:
            # Handle formats: "600", "120+1", "180+2", etc.
            parts = time_control_str.split('+')
            base_time_str = parts[0].strip()

            if base_time_str.isdigit():
                base_time = int(base_time_str)
                increment = 0

                # Parse increment if present
                if len(parts) > 1 and parts[1].strip().isdigit():
                    increment = int(parts[1].strip())

                # Apply Chess.com formula: total = base + (40 × increment)
                time_control_seconds = base_time + (40 * increment)
        except (ValueError, IndexError):
            pass  # Keep as None if parsing fails

    # Extract ELO ratings
    white_elo = None
    black_elo = None
    try:
        white_elo = int(headers.get("WhiteElo", 0)) or None
        black_elo = int(headers.get("BlackElo", 0)) or None
    except (ValueError, TypeError):
        pass

    # Extract ECO code and opening name
    eco_code = headers.get("ECO")
    opening_name = None

    # Try to get opening name from ECOUrl or Opening header
    eco_url = headers.get("ECOUrl", "")
    if eco_url and "/openings/" in eco_url:
        # Extract opening name from URL
        opening_part = eco_url.split("/openings/")[-1]
        opening_name = opening_part.replace("-", " ").title()

    # Fallback to Opening header if available
    if not opening_name:
        opening_name = headers.get("Opening")

    return {
        "eco_code": eco_code,
        "opening_name": opening_name,
        "white_username": headers.get("White", ""),
        "black_username": headers.get("Black", ""),
        "white_elo": white_elo,
        "black_elo": black_elo,
        "result": headers.get("Result", "*"),
        "date": date,
        "time_control_seconds": time_control_seconds,
        "url": headers.get("Link"),
    }
