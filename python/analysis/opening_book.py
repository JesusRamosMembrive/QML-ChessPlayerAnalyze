"""
Opening book detection module.

This module provides functionality to detect which moves in a game are from
opening theory (book moves) vs moves played out of book. This is critical for
accurate match rate calculations, as book moves don't reflect a player's
actual chess strength.
"""

from pathlib import Path

import chess
import chess.polyglot

from utils import get_mainline_moves, parse_pgn

# Path to the opening book file
OPENING_BOOK_PATH = (
    Path(__file__).parent.parent.parent / "data" / "opening_books" / "lichess_book.bin"
)


class OpeningBookDetector:
    """
    Detects opening book moves using Polyglot opening book format.

    The Polyglot format is a binary format that stores positions and their
    recommended moves. We use it to identify which moves in a game are from
    established opening theory.
    """

    def __init__(self, book_path: Path | None = None):
        """
        Initialize the opening book detector.

        Args:
            book_path: Path to the Polyglot book file (.bin). If None, uses default.
        """
        self.book_path = book_path or OPENING_BOOK_PATH

        if not self.book_path.exists():
            raise FileNotFoundError(
                f"Opening book not found at {self.book_path}. "
                "Please download a Polyglot opening book."
            )

    def get_out_of_book_move_index(self, pgn_string: str) -> int:
        """
        Find the first move index that is out of book.

        Args:
            pgn_string: PGN string of the game

        Returns:
            Index of the first out-of-book move (0-based).
            Returns 0 if the very first move is out of book.
            Returns total move count if all moves are in book.

        Example:
            >>> detector = OpeningBookDetector()
            >>> pgn = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. h3 ..."
            >>> detector.get_out_of_book_move_index(pgn)
            6  # Move 4. h3 is out of book (index 6 for white's 4th move)
        """
        # Parse the PGN using utility function
        game = parse_pgn(pgn_string)
        if not game:
            return 0

        board = game.board()
        move_index = 0

        # Iterate through moves and check if they're in the book
        mainline_moves = get_mainline_moves(pgn_string)
        with chess.polyglot.open_reader(self.book_path) as reader:
            for move in mainline_moves:
                # Check if current position has book moves
                try:
                    entries = list(reader.find_all(board))
                    if not entries:
                        # No book moves for this position - we're out of book
                        return move_index

                    # Check if the actual move played is in the book
                    book_moves = [entry.move for entry in entries]
                    if move not in book_moves:
                        # Move played is not in the book
                        return move_index

                except Exception:
                    # Error reading book - assume out of book
                    return move_index

                # Move was in book, continue
                board.push(move)
                move_index += 1

        # All moves were in book
        return move_index

    def filter_out_of_book_moves(self, move_evals: list[dict], pgn_string: str) -> list[dict]:
        """
        Filter move evaluations to only include out-of-book moves.

        This is the key function for calculating accurate match rates.
        We exclude opening book moves because they don't reflect the player's
        chess strength - they're memorized theory.

        Args:
            move_evals: List of move evaluation dicts (from basic_metrics)
            pgn_string: PGN string of the game

        Returns:
            Filtered list containing only out-of-book move evaluations

        Example:
            >>> move_evals = [
            ...     {"move_num": 1, "best_rank": 0, ...},  # e4 - in book
            ...     {"move_num": 2, "best_rank": 0, ...},  # e5 - in book
            ...     {"move_num": 3, "best_rank": 1, ...},  # Nf3 - in book
            ...     {"move_num": 4, "best_rank": 0, ...},  # out of book
            ...     {"move_num": 5, "best_rank": 2, ...},  # out of book
            ... ]
            >>> filtered = detector.filter_out_of_book_moves(move_evals, pgn)
            >>> len(filtered)
            2  # Only moves 4 and 5
        """
        out_of_book_index = self.get_out_of_book_move_index(pgn_string)

        # Filter moves: only keep moves with index >= out_of_book_index
        filtered_moves = [
            move_eval
            for move_eval in move_evals
            if move_eval.get("move_number", 0) >= out_of_book_index
        ]

        return filtered_moves

    def get_book_statistics(self, pgn_string: str) -> dict:
        """
        Get statistics about book vs out-of-book moves.

        Args:
            pgn_string: PGN string of the game

        Returns:
            Dict with statistics:
            - total_moves: Total moves in the game
            - book_moves: Number of moves in opening book
            - out_of_book_moves: Number of moves out of book
            - out_of_book_start_index: Index where out of book starts
            - percentage_in_book: Percentage of moves in book
        """
        # Get total moves using utility function
        mainline_moves = get_mainline_moves(pgn_string)
        total_moves = len(mainline_moves)

        if total_moves == 0:
            return {
                "total_moves": 0,
                "book_moves": 0,
                "out_of_book_moves": 0,
                "out_of_book_start_index": 0,
                "percentage_in_book": 0.0,
            }
        out_of_book_index = self.get_out_of_book_move_index(pgn_string)
        book_moves = out_of_book_index
        out_of_book_moves = total_moves - book_moves

        return {
            "total_moves": total_moves,
            "book_moves": book_moves,
            "out_of_book_moves": out_of_book_moves,
            "out_of_book_start_index": out_of_book_index,
            "percentage_in_book": (book_moves / total_moves * 100) if total_moves > 0 else 0.0,
        }


# Global instance for easy access
_detector_instance: OpeningBookDetector | None = None


def get_detector() -> OpeningBookDetector:
    """
    Get or create the global opening book detector instance.

    Returns:
        OpeningBookDetector instance
    """
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = OpeningBookDetector()
    return _detector_instance
