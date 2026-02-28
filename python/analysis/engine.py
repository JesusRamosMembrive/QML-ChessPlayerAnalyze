"""
Stockfish chess engine wrapper for move-by-move game analysis.

Core engine functionality for analyzing chess games using Stockfish.
"""

import chess
import chess.engine

from analysis.opening_book import get_detector
from utils import get_mainline_moves, parse_pgn


def calculate_material_balance(board: chess.Board) -> int:
    """
    Calculate material balance in centipawns (white POV).

    Piece values:
    - Pawn: 100
    - Knight: 320
    - Bishop: 330
    - Rook: 500
    - Queen: 900
    - King: 0 (not counted)

    Returns:
        Material balance (positive = white advantage, negative = black advantage)
    """
    piece_values = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 0,
    }

    material = 0
    for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
        # White pieces (positive)
        material += len(board.pieces(piece_type, chess.WHITE)) * piece_values[piece_type]
        # Black pieces (negative)
        material -= len(board.pieces(piece_type, chess.BLACK)) * piece_values[piece_type]

    return material


def analyze_game(
    pgn_text: str,
    stockfish_path: str = "stockfish",
    depth: int = 12,
    multipv: int = 5,  # Changed: 1 → 5 for better move detection
    player_color: str | None = None,
    skip_book_moves: bool = True,
) -> list[dict]:
    """
    Analyze a game move-by-move using Stockfish.

    Args:
        pgn_text: Full PGN text of the game
        stockfish_path: Path to Stockfish binary (default: "stockfish" from PATH)
        depth: Analysis depth (default: 12)
        multipv: Number of principal variations to calculate (default: 5)
        player_color: Color of the player to analyze ('white' or 'black').
                      If None, analyzes ALL moves (both players).
        skip_book_moves: If True, skip analyzing the first 10 moves (opening theory)

    Returns:
        List of move evaluations, one per move:
        [
            {
                "move_number": 1,
                "played": "e4",  # move played (SAN notation)
                "best": "e4",    # best move according to engine
                "best_rank": 0,  # 0 = best, 1 = 2nd best, etc.
                "eval_before": 15,  # evaluation before move (centipawns, white POV)
                "eval_after": 15,   # evaluation after move
                "cp_loss": 0,       # centipawns lost vs best move
                "legal_moves": 20,  # number of legal moves in position
                "is_book_move": False,  # True if skipped as book move
            },
            ...
        ]
    """
    print(f"Loading PGN and initializing Stockfish (depth={depth}, multipv={multipv})...")

    # Parse PGN using utility function
    game = parse_pgn(pgn_text)
    if game is None:
        raise ValueError("Invalid PGN: Could not parse PGN text")

    # Validate that the game has moves using utility function
    mainline_moves = get_mainline_moves(pgn_text)
    if len(mainline_moves) == 0:
        raise ValueError("Invalid PGN: Game has no moves")

    board = game.board()

    # Start Stockfish engine
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)

    move_evaluations: list[dict] = []
    total_moves = len(mainline_moves)

    print(f"Analyzing {total_moves} moves...")

    # Detect opening book moves using Polyglot book
    out_of_book_index = None
    if skip_book_moves:
        try:
            detector = get_detector()
            out_of_book_index = detector.get_out_of_book_move_index(pgn_text)
            print(f"Opening book detection: First {out_of_book_index} moves are in book")
        except Exception as e:
            print(
                f"Warning: Could not load opening book ({e}), using fallback (skip first 10 moves)"
            )
            out_of_book_index = 10  # Fallback to simple heuristic

    for move_num, move in enumerate(game.mainline_moves(), start=1):
        # FIX #3: Skip book moves (opening theory)
        # Use Polyglot book detection if available, otherwise use simple heuristic
        if skip_book_moves and out_of_book_index is not None:
            is_book_move = move_num <= out_of_book_index
        else:
            is_book_move = False

        # FIX #1: Filter by player color
        # White moves are odd numbered (1, 3, 5...), black moves are even (2, 4, 6...)
        if player_color is not None:
            is_player_move = (player_color.lower() == "white" and move_num % 2 == 1) or (
                player_color.lower() == "black" and move_num % 2 == 0
            )
            if not is_player_move:
                # Skip this move (opponent's move)
                board.push(move)
                continue

        if move_num % 10 == 0:
            print(f"  Progress: {move_num}/{total_moves} moves analyzed")

        # Count legal moves in current position
        legal_moves_count = board.legal_moves.count()

        # Calculate material BEFORE the move
        material_before = calculate_material_balance(board)

        # Evaluate position BEFORE the move
        info_before = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)

        # Extract evaluation (white POV)
        score_before = info_before[0]["score"].white()

        # FIX #2 + #4: Handle mate scores correctly
        # Mate positions should NOT be included in ACPL calculation
        is_mate_position = score_before.is_mate()

        if is_mate_position:
            # Mate in N moves - mark as mate but don't use extreme values for cp_loss
            mate_in = score_before.mate()
            # Positive mate (white wins), negative mate (black wins)
            eval_before = 10000 * (1 if mate_in and mate_in > 0 else -1)
        else:
            eval_before = score_before.score() or 0

        # Get best move
        best_move = info_before[0]["pv"][0]
        best_move_san = board.san(best_move)

        # Push the actual move played
        played_move_san = board.san(move)

        # Detect if move is a capture
        is_capture = board.is_capture(move)

        board.push(move)

        # Calculate material AFTER the move
        material_after = calculate_material_balance(board)

        # Detect material sacrifice (lost material in the move)
        # Note: material_change = material_after - material_before
        # (Positive = white lost material, Negative = black lost material)
        # From player's perspective (will adjust for black later)
        # If player is white: material_change < 0 means lost material
        # If player is black: material_change > 0 means lost material (inverted)
        material_sacrificed = 0  # Will be calculated after player color adjustment

        # Evaluate position AFTER the move
        info_after = engine.analyse(board, chess.engine.Limit(depth=depth))
        score_after = info_after["score"].white()

        # FIX #2 + #4: Handle mate scores correctly (after move)
        is_mate_after = score_after.is_mate()

        if is_mate_after:
            mate_in = score_after.mate()
            eval_after = 10000 * (1 if mate_in and mate_in > 0 else -1)
        else:
            eval_after = score_after.score() or 0

        # FIX #5: Convert evaluations to player's perspective
        # Stockfish evaluations are always from white's POV
        # For black players, we need to invert the sign
        if player_color and player_color.lower() == "black":
            eval_before = -eval_before
            eval_after = -eval_after

        # Calculate material sacrificed from player's perspective
        # PROBLEM: Single-move analysis can't detect true sacrifices!
        #
        # Example sacrifice: Bxh7+ (bishop takes pawn on h7)
        #   Move 1 (player): Bxh7+ → GAINS +100 (captured pawn)
        #   Move 2 (opponent): Kxh7 → Player LOSES -330 (bishop captured)
        #   Net sacrifice: -230 cp
        #
        # But we only see Move 1, where player GAINS material!
        #
        # Solution: Look ahead 1 move (opponent's best response)
        # If opponent can recapture, calculate net material after recapture

        # Current position: board is AFTER player's move
        # Check if opponent has a recapture available
        material_after_opponent_response = material_after  # Default: no recapture

        if is_capture:
            # Player captured something - opponent might recapture
            # Analyze opponent's best move (1-ply lookahead)
            opponent_info = engine.analyse(board, chess.engine.Limit(depth=1))
            opponent_best_move = opponent_info["pv"][0] if opponent_info.get("pv") else None

            if opponent_best_move and board.is_capture(opponent_best_move):
                # Opponent's best move is a recapture
                # Simulate it to get material after recapture
                board.push(opponent_best_move)
                material_after_opponent_response = calculate_material_balance(board)
                board.pop()  # Undo the simulated move

        # Now calculate material change including opponent's response
        material_change_with_response = material_after_opponent_response - material_before

        if player_color:
            if player_color.lower() == "white":
                # White sacrifices when material balance goes down (lost pieces)
                material_sacrificed = abs(min(0, material_change_with_response))
            else:
                # Black sacrifices when material balance goes up (lost pieces to white)
                material_sacrificed = abs(max(0, material_change_with_response))
        else:
            material_sacrificed = 0

        # FIX #4: Calculate centipawn loss ONLY if not a mate position
        # Mate positions generate absurd cp_loss values and should be excluded
        if is_mate_position or is_mate_after:
            # Mark as mate position, exclude from ACPL
            cp_loss = None  # Will be filtered out in ACPL calculation
        else:
            # Normal position: calculate cp_loss from player's perspective
            # Player's position got worse if eval_after < eval_before
            cp_loss = max(0, eval_before - eval_after)

        # Calculate improvement (position got better after move)
        improvement = eval_after - eval_before if cp_loss is not None else 0

        # Detect BRILLIANT move: Sacrifice that leads to significant advantage
        # A brilliant move in chess is typically:
        # 1. A piece sacrifice (detected indirectly via evaluation drop then recovery)
        # 2. NOT the obvious top engine move (shows creativity)
        # 3. Leads to significant positional/tactical advantage
        #
        # Detection heuristic:
        # - If eval drops initially but then improves dramatically, it's likely a sacrifice
        # - For now, we use: NOT top move BUT still improves position significantly
        # - This captures "creative non-obvious moves that work brilliantly"
        # Note: is_brilliant_candidate logic will be implemented later

        # Determine best_rank (0 = best move, 1 = second best, etc.)
        # With multipv > 1, check which PV the played move matches
        best_rank = multipv  # Default: worse than all PVs (not in top 5)
        for idx, pv_info in enumerate(info_before):
            if pv_info["pv"][0] == move:
                best_rank = idx
                break

        move_evaluations.append(
            {
                "move_number": move_num,
                "played": played_move_san,
                "best": best_move_san,
                "best_rank": best_rank,
                "eval_before": eval_before,
                "eval_after": eval_after,
                "cp_loss": cp_loss,
                "legal_moves": legal_moves_count,
                "is_book_move": is_book_move,
                "is_capture": is_capture,
                "improvement": improvement,
                "material_sacrificed": material_sacrificed,
            }
        )

        # board is already in the new position (we pushed the move)

    engine.quit()
    print("✅ Analysis complete")

    return move_evaluations
