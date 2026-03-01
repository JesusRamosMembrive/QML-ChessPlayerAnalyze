"""Tests for analysis wrapper functions."""

from unittest.mock import patch
from tools.analyzers import inspect_phase_classification, inspect_opening_book, analyze_pgn_transparent

# Minimal valid PGN for testing (no Stockfish needed)
SAMPLE_PGN = """[Event "Test"]
[Site "?"]
[Date "2024.01.01"]
[White "Player1"]
[Black "Player2"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6
8. c3 O-O 9. h3 Nb8 10. d4 Nbd7 11. Nbd2 Bb7 12. Bc2 Re8 13. Nf1 Bf8
14. Ng3 g6 15. Bg5 h6 16. Bd2 Bg7 17. a4 c5 18. d5 c4 19. b4 Nh5
20. Nxh5 gxh5 21. Qxh5 Qf6 22. g4 Nf8 23. Bh6 Qg6 24. Qxg6 fxg6
25. Bxg7 Kxg7 1-0"""


class TestInspectPhaseClassification:
    def test_returns_move_classifications(self):
        result = inspect_phase_classification(SAMPLE_PGN, opening_moves=15, endgame_pieces=12)
        assert "moves" in result
        assert len(result["moves"]) > 0
        first = result["moves"][0]
        assert "move_number" in first
        assert "piece_count" in first
        assert "phase" in first
        assert "reason" in first

    def test_phase_assignment(self):
        result = inspect_phase_classification(SAMPLE_PGN, opening_moves=15, endgame_pieces=12)
        moves = result["moves"]
        assert moves[0]["phase"] == "opening"
        move_15 = [m for m in moves if m["move_number"] == 15][0]
        assert move_15["phase"] == "opening"
        move_16 = [m for m in moves if m["move_number"] == 16][0]
        assert move_16["phase"] in ("middlegame", "endgame")

    def test_summary(self):
        result = inspect_phase_classification(SAMPLE_PGN, opening_moves=15, endgame_pieces=12)
        assert "summary" in result
        summary = result["summary"]
        assert "opening" in summary
        assert "middlegame" in summary
        assert "endgame" in summary

    def test_thresholds_in_result(self):
        result = inspect_phase_classification(SAMPLE_PGN, opening_moves=15, endgame_pieces=12)
        assert result["thresholds"]["opening_moves"] == 15
        assert result["thresholds"]["endgame_pieces"] == 12


class TestInspectOpeningBook:
    def test_returns_book_info(self):
        result = inspect_opening_book(SAMPLE_PGN)
        assert "book_file_exists" in result
        assert "detection_method" in result
        assert "out_of_book_index" in result

    def test_fallback_detection(self):
        result = inspect_opening_book(SAMPLE_PGN)
        if not result["book_file_exists"]:
            assert result["detection_method"] == "fallback"
            assert result["out_of_book_index"] == 10


# Helper to create mock move evaluations
def _make_move_eval(move_num, cp_loss=10, best_rank=0, is_book=False):
    return {
        "move_number": move_num,
        "played": "e4",
        "best": "e4",
        "best_rank": best_rank,
        "eval_before": 30,
        "eval_after": 30 - cp_loss,
        "cp_loss": cp_loss,
        "legal_moves": 20,
        "is_book_move": is_book,
        "is_capture": False,
        "improvement": -cp_loss,
        "material_sacrificed": 0,
        "multipv_evals": [30, 25, 20, 15, 10],
        "top_gap": 5,
        "eval_spread": 20,
    }

MOCK_MOVE_EVALS = [_make_move_eval(i, cp_loss=10 + i, best_rank=0 if i % 3 == 0 else 2)
                   for i in range(1, 26)]


class TestAnalyzePgnTransparent:
    @patch("tools.analyzers.analyze_game")
    def test_returns_all_sections(self, mock_analyze):
        mock_analyze.return_value = MOCK_MOVE_EVALS
        result = analyze_pgn_transparent(
            SAMPLE_PGN,
            player_color="white",
            stockfish_path="stockfish",
            depth=12,
        )
        assert "move_evals" in result
        assert "phase_classification" in result
        assert "opening_book" in result
        assert "metrics" in result
        assert "warnings" in result

    @patch("tools.analyzers.analyze_game")
    def test_metrics_calculated(self, mock_analyze):
        mock_analyze.return_value = MOCK_MOVE_EVALS
        result = analyze_pgn_transparent(
            SAMPLE_PGN,
            player_color="white",
            stockfish_path="stockfish",
            depth=12,
        )
        metrics = result["metrics"]
        assert "acpl" in metrics
        assert "robust_acpl" in metrics
        assert "match_rates" in metrics
        assert "blunders" in metrics
        assert "phase_breakdown" in metrics

    @patch("tools.analyzers.analyze_game")
    def test_warnings_generated(self, mock_analyze):
        book_evals = [_make_move_eval(i, is_book=True) for i in range(1, 26)]
        mock_analyze.return_value = book_evals
        result = analyze_pgn_transparent(
            SAMPLE_PGN,
            player_color="white",
            stockfish_path="stockfish",
            depth=12,
        )
        assert len(result["warnings"]) > 0
