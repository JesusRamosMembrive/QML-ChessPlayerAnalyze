"""Tests for analysis wrapper functions."""

from tools.analyzers import inspect_phase_classification, inspect_opening_book

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
