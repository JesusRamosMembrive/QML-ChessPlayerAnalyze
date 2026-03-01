"""Tests for terminal formatting utilities."""

from tools.formatters import format_table, format_section_header, format_warning


class TestFormatTable:
    def test_basic_table(self):
        headers = ["Name", "Value"]
        rows = [["ACPL", "28.3"], ["Blunders", "3"]]
        result = format_table(headers, rows)
        assert "Name" in result
        assert "Value" in result
        assert "ACPL" in result
        assert "28.3" in result

    def test_empty_rows(self):
        result = format_table(["A", "B"], [])
        assert "A" in result  # headers still shown

    def test_alignment(self):
        headers = ["Col1", "Col2"]
        rows = [["short", "x"], ["very long value", "y"]]
        result = format_table(headers, rows)
        lines = result.strip().split("\n")
        # All lines should have same length (padded)
        lengths = [len(line.rstrip()) for line in lines if line.strip()]
        assert len(set(lengths)) <= 2  # header separator may differ


class TestFormatSectionHeader:
    def test_header_format(self):
        result = format_section_header("PHASE CLASSIFICATION")
        assert "PHASE CLASSIFICATION" in result
        assert "===" in result

    def test_with_params(self):
        result = format_section_header("PHASE CLASSIFICATION", {"opening_moves": 15, "endgame_pieces": 12})
        assert "opening_moves" in result
        assert "15" in result


class TestFormatWarning:
    def test_warning_format(self):
        result = format_warning("No endgame moves analyzed")
        assert "WARNING" in result or "!" in result
        assert "No endgame moves analyzed" in result
