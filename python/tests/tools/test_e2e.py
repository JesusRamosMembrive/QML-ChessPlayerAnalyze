"""End-to-end tests that don't require Stockfish.

These test phase classification and opening book inspection
using real PGN files.
"""

from pathlib import Path

from tools.analyzers import inspect_opening_book, inspect_phase_classification

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_PGN = (FIXTURE_DIR / "sample_game.pgn").read_text(encoding="utf-8")


class TestPhaseClassificationE2E:
    def test_all_moves_classified(self):
        result = inspect_phase_classification(SAMPLE_PGN)
        # The sample game has 40 moves per side = 80 half-moves total
        assert len(result["moves"]) > 30

    def test_phases_present(self):
        result = inspect_phase_classification(SAMPLE_PGN)
        phases_found = {m["phase"] for m in result["moves"]}
        assert "opening" in phases_found
        assert "middlegame" in phases_found

    def test_endgame_with_low_threshold(self):
        result = inspect_phase_classification(SAMPLE_PGN, endgame_pieces=20)
        phases_found = {m["phase"] for m in result["moves"]}
        assert "endgame" in phases_found

    def test_mismatch_detection(self):
        result = inspect_phase_classification(SAMPLE_PGN, endgame_pieces=24)
        mismatches = [m for m in result["moves"] if m["phase_mismatch"]]
        assert isinstance(mismatches, list)


class TestOpeningBookE2E:
    def test_fallback_mode(self):
        result = inspect_opening_book(SAMPLE_PGN)
        if not result["book_file_exists"]:
            assert result["detection_method"] == "fallback"
            assert result["out_of_book_index"] == 10
