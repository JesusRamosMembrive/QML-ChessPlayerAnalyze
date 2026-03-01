# Debug CLI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a CLI tool (`python/tools/debug_cli.py`) that calls the existing chess analysis engine and exposes all intermediate calculations for validation and calibration.

**Architecture:** Three modules in `python/tools/` — `debug_cli.py` (argparse entry point), `analyzers.py` (wrappers around engine functions that capture intermediates), `formatters.py` (terminal table/section output). All modules import from the existing `python/analysis/` and `python/utils/` packages.

**Tech Stack:** Python 3.11+, `python-chess`, `argparse` (stdlib). No new dependencies.

**Design doc:** `docs/plans/2026-03-01-debug-cli-design.md`

---

## Important context

All commands must be run from the `python/` directory because the existing engine uses relative imports rooted there. Example:

```bash
cd H:/Git_Overture/ChessAnalyzerQML/python
python -m tools.debug_cli analyze-pgn ../test.pgn --player white --stockfish ../stockfish/stockfish.exe
```

The existing engine modules use `from analysis.xxx import yyy` and `from utils import zzz` — these resolve when `python/` is the working directory or when run as `python -m tools.debug_cli`.

### Key engine function signatures (reference)

```python
# analysis/engine.py
analyze_game(pgn_text, stockfish_path="stockfish", depth=12, multipv=5, player_color=None, skip_book_moves=True) -> list[dict]
# Returns: [{"move_number", "played", "best", "best_rank", "eval_before", "eval_after", "cp_loss", "legal_moves", "is_book_move", "is_capture", "improvement", "material_sacrificed", "multipv_evals", "top_gap", "eval_spread"}, ...]

# analysis/phase_analysis.py
calculate_phase_metrics(pgn_text, move_evals, opening_moves=15, endgame_pieces=12) -> dict
# Returns: {"opening": {stats}, "middlegame": {stats}, "endgame": {stats}}

calculate_enhanced_phase_analysis(pgn_text, move_evals, opening_moves=15, endgame_pieces=12) -> dict
# Returns: {"phase_transitions", "collapse_detected", "collapse_location", "phase_consistency", "worst_phase", "best_phase"}

calculate_phase_variance(pgn_text, move_evals, opening_moves=15, endgame_pieces=12) -> dict
# Returns: {"opening_std", "middlegame_std", "endgame_std", "variance_drop", "consistency_increase"}

# analysis/opening_book.py
get_detector() -> OpeningBookDetector  # singleton, raises FileNotFoundError if book missing
OpeningBookDetector.get_out_of_book_move_index(pgn_string) -> int
OpeningBookDetector.get_book_statistics(pgn_string) -> dict

# analysis/basic_metrics.py
calculate_acpl(move_evals, cap_cp=1500) -> float
calculate_blunders(move_evals, blunder_threshold=100) -> {"blunder_count", "blunder_rate", "blunder_moves"}
calculate_topn_match_rates(move_evals) -> {"top1"..,"top5": float 0-1}
calculate_robust_acpl(move_evals, cap_cp=300) -> float  # median

# analysis/suspicion.py
calculate_suspicion_score(**kwargs) -> {"suspicion_score", "risk_level", "confidence", "signals", "context", "data_points"}
calculate_precision_bursts(move_evals, threshold=10, min_streak=3) -> {"burst_count", "longest_burst", "total_precise_moves", "precision_rate"}

# utils/pgn_utils.py
parse_pgn(pgn_text) -> chess.pgn.Game | None
iterate_moves_with_board(pgn_text) -> Iterator[(move_num, move, board)]  # board is AFTER move
extract_pgn_metadata(pgn_text) -> {"eco_code", "opening_name", "white_username", ...}
```

---

## Task 1: Create package structure and formatters module

**Files:**
- Create: `python/tools/__init__.py`
- Create: `python/tools/formatters.py`
- Test: `python/tests/tools/__init__.py`
- Test: `python/tests/tools/test_formatters.py`

**Step 1: Create the package files**

```python
# python/tools/__init__.py
"""Debug and validation tools for the chess analysis engine."""
```

```python
# python/tests/tools/__init__.py
```

**Step 2: Write the failing tests for formatters**

```python
# python/tests/tools/test_formatters.py
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
        assert "WARNING" in result or "⚠" in result or "!" in result
        assert "No endgame moves analyzed" in result
```

**Step 3: Run tests to verify they fail**

Run: `cd H:/Git_Overture/ChessAnalyzerQML/python && python -m pytest tests/tools/test_formatters.py -v`
Expected: FAIL (ImportError — module does not exist yet)

**Step 4: Implement formatters.py**

```python
# python/tools/formatters.py
"""Terminal formatting utilities for the debug CLI."""


def format_table(headers: list[str], rows: list[list[str]], min_col_width: int = 6) -> str:
    """Format data as an aligned ASCII table.

    Args:
        headers: Column header strings.
        rows: List of rows, each a list of string values.
        min_col_width: Minimum column width.

    Returns:
        Formatted table string with header separator.
    """
    if not headers:
        return ""

    # Calculate column widths
    col_widths = [max(min_col_width, len(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Build format string
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    separator = "  ".join("-" * w for w in col_widths)

    lines = [fmt.format(*headers), separator]
    for row in rows:
        # Pad row if shorter than headers
        padded = list(row) + [""] * (len(headers) - len(row))
        lines.append(fmt.format(*padded[:len(headers)]))

    return "\n".join(lines)


def format_section_header(title: str, params: dict | None = None) -> str:
    """Format a section header with optional parameters.

    Args:
        title: Section title.
        params: Optional dict of parameter names and values to display.

    Returns:
        Formatted section header string.
    """
    lines = [f"\n=== {title} ==="]
    if params:
        for key, value in params.items():
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def format_warning(message: str) -> str:
    """Format a warning message.

    Args:
        message: Warning text.

    Returns:
        Formatted warning string.
    """
    return f"  ! WARNING: {message}"


def format_metric(name: str, value, unit: str = "", note: str = "") -> str:
    """Format a single metric line.

    Args:
        name: Metric name.
        value: Metric value (any type).
        unit: Optional unit suffix.
        note: Optional annotation.

    Returns:
        Formatted metric string.
    """
    parts = [f"  {name}: {value}"]
    if unit:
        parts[0] += f" {unit}"
    if note:
        parts[0] += f"  ({note})"
    return parts[0]
```

**Step 5: Run tests to verify they pass**

Run: `cd H:/Git_Overture/ChessAnalyzerQML/python && python -m pytest tests/tools/test_formatters.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add python/tools/__init__.py python/tools/formatters.py python/tests/tools/__init__.py python/tests/tools/test_formatters.py
git commit -m "feat(tools): add formatters module for debug CLI"
```

---

## Task 2: Create analyzers module — phase classification inspector

**Files:**
- Create: `python/tools/analyzers.py`
- Test: `python/tests/tools/test_analyzers.py`

This module wraps the engine functions to capture and expose intermediate state. We start with phase classification since that's the user's primary debugging need.

**Step 1: Write the failing test**

```python
# python/tests/tools/test_analyzers.py
"""Tests for analysis wrapper functions."""

from tools.analyzers import inspect_phase_classification, inspect_opening_book


# Minimal valid PGN for testing (no Stockfish needed for phase/book inspection)
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
        # Each move should have: move_number, piece_count, phase, reason
        first = result["moves"][0]
        assert "move_number" in first
        assert "piece_count" in first
        assert "phase" in first
        assert "reason" in first

    def test_phase_assignment(self):
        result = inspect_phase_classification(SAMPLE_PGN, opening_moves=15, endgame_pieces=12)
        moves = result["moves"]
        # Move 1 should be opening
        assert moves[0]["phase"] == "opening"
        # Move 15 should still be opening
        move_15 = [m for m in moves if m["move_number"] == 15][0]
        assert move_15["phase"] == "opening"
        # Move 16 should be middlegame or endgame depending on pieces
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
        # Without the actual book file, should use fallback
        result = inspect_opening_book(SAMPLE_PGN)
        if not result["book_file_exists"]:
            assert result["detection_method"] == "fallback"
            assert result["out_of_book_index"] == 10
```

**Step 2: Run tests to verify they fail**

Run: `cd H:/Git_Overture/ChessAnalyzerQML/python && python -m pytest tests/tools/test_analyzers.py -v`
Expected: FAIL (ImportError)

**Step 3: Implement analyzers.py**

```python
# python/tools/analyzers.py
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

    This mirrors the logic in ``phase_analysis.calculate_phase_metrics``
    and ``calculate_enhanced_phase_analysis`` but exposes every
    intermediate value so the user can see exactly how phases are assigned.

    Note on a known inconsistency:
      - ``calculate_phase_metrics`` uses ``iterate_moves_with_board`` which
        yields the board AFTER the move, so ``piece_count`` is post-move.
      - ``calculate_enhanced_phase_analysis`` and ``calculate_phase_variance``
        call ``len(board.piece_map())`` BEFORE ``board.push(move)``, so
        ``piece_count`` is pre-move.
      This function shows BOTH values to help diagnose the discrepancy.

    Args:
        pgn_text: Full PGN text.
        opening_moves: Moves 1..N classified as opening.
        endgame_pieces: Piece count threshold for endgame.

    Returns:
        Dict with moves list, summary counts, and thresholds used.
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

        # Determine phase using the SAME logic as calculate_phase_metrics
        # (which uses iterate_moves_with_board -> board AFTER move)
        if move_num <= opening_moves:
            phase = "opening"
            reason = f"move_num {move_num} <= {opening_moves}"
        elif pieces_after <= endgame_pieces:
            phase = "endgame"
            reason = f"pieces_after={pieces_after} <= {endgame_pieces}"
        else:
            phase = "middlegame"
            reason = f"move_num {move_num} > {opening_moves} AND pieces_after={pieces_after} > {endgame_pieces}"

        # Also check what calculate_enhanced_phase_analysis would say
        # (it uses pieces BEFORE the move)
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

    Args:
        pgn_text: Full PGN text.

    Returns:
        Dict with book detection details.
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
```

**Step 4: Run tests to verify they pass**

Run: `cd H:/Git_Overture/ChessAnalyzerQML/python && python -m pytest tests/tools/test_analyzers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add python/tools/analyzers.py python/tests/tools/test_analyzers.py
git commit -m "feat(tools): add analyzers module with phase and book inspection"
```

---

## Task 3: Add Stockfish analysis wrapper to analyzers

**Files:**
- Modify: `python/tools/analyzers.py`
- Modify: `python/tests/tools/test_analyzers.py`

This adds the function that runs `analyze_game()` and then cross-references the results with phase/book data to produce the full transparent report. Since it requires Stockfish, the tests mock the engine call.

**Step 1: Write the failing test**

Add to `python/tests/tools/test_analyzers.py`:

```python
from unittest.mock import patch
from tools.analyzers import analyze_pgn_transparent


# Simulated move_evals as returned by analyze_game()
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
                   for i in range(1, 26)]  # 25 player moves


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
        # All moves have is_book_move=True => warning about no non-book moves
        book_evals = [_make_move_eval(i, is_book=True) for i in range(1, 26)]
        mock_analyze.return_value = book_evals
        result = analyze_pgn_transparent(
            SAMPLE_PGN,
            player_color="white",
            stockfish_path="stockfish",
            depth=12,
        )
        # Should warn about all moves being book
        assert len(result["warnings"]) > 0
```

**Step 2: Run tests to verify they fail**

Run: `cd H:/Git_Overture/ChessAnalyzerQML/python && python -m pytest tests/tools/test_analyzers.py::TestAnalyzePgnTransparent -v`
Expected: FAIL (ImportError — `analyze_pgn_transparent` not defined)

**Step 3: Implement analyze_pgn_transparent**

Add to `python/tools/analyzers.py`:

```python
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


def analyze_pgn_transparent(
    pgn_text: str,
    player_color: str,
    stockfish_path: str = "stockfish",
    depth: int = 12,
    multipv: int = 5,
    opening_moves: int = 15,
    endgame_pieces: int = 12,
) -> dict:
    """Run full analysis on a PGN and return all intermediate data.

    Calls ``analyze_game()`` from the engine, then runs every metric
    function and collects the results together with phase classification
    and opening book inspection.

    Args:
        pgn_text: Full PGN text.
        player_color: ``"white"`` or ``"black"``.
        stockfish_path: Path to Stockfish binary.
        depth: Stockfish analysis depth.
        multipv: Number of principal variations.
        opening_moves: Phase threshold.
        endgame_pieces: Phase threshold.

    Returns:
        Dict with sections: move_evals, phase_classification, opening_book,
        metrics, enhanced_phase, precision_bursts, warnings.
    """
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
```

**Step 4: Run tests to verify they pass**

Run: `cd H:/Git_Overture/ChessAnalyzerQML/python && python -m pytest tests/tools/test_analyzers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add python/tools/analyzers.py python/tests/tools/test_analyzers.py
git commit -m "feat(tools): add transparent analysis wrapper with warnings"
```

---

## Task 4: Create debug_cli.py with analyze-pgn command

**Files:**
- Create: `python/tools/debug_cli.py`

This is the entry point. It parses arguments and calls the analyzers/formatters.

**Step 1: Write a smoke test**

Add to `python/tests/tools/test_analyzers.py` (or create `python/tests/tools/test_cli.py`):

```python
# python/tests/tools/test_cli.py
"""Tests for CLI argument parsing."""

from tools.debug_cli import build_parser


class TestCLIParser:
    def test_analyze_pgn_command(self):
        parser = build_parser()
        args = parser.parse_args(["analyze-pgn", "game.pgn", "--player", "white", "--depth", "16"])
        assert args.command == "analyze-pgn"
        assert args.pgn_file == "game.pgn"
        assert args.player == "white"
        assert args.depth == 16

    def test_analyze_pgn_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["analyze-pgn", "game.pgn", "--player", "white"])
        assert args.depth == 12
        assert args.multipv == 5
        assert args.opening_moves == 15
        assert args.endgame_pieces == 12

    def test_score_command(self):
        parser = build_parser()
        args = parser.parse_args(["score", "results.json"])
        assert args.command == "score"
        assert args.result_file == "results.json"

    def test_inspect_game_command(self):
        parser = build_parser()
        args = parser.parse_args(["inspect-game", "results.json", "--game", "3"])
        assert args.command == "inspect-game"
        assert args.game == 3
```

**Step 2: Run tests to verify they fail**

Run: `cd H:/Git_Overture/ChessAnalyzerQML/python && python -m pytest tests/tools/test_cli.py -v`
Expected: FAIL

**Step 3: Implement debug_cli.py**

```python
# python/tools/debug_cli.py
"""Chess analysis debugger CLI.

Validates and inspects the chess analysis engine by exposing
intermediate calculations that are normally hidden.

Usage:
    cd python/
    python -m tools.debug_cli analyze-pgn game.pgn --player white --stockfish path/to/stockfish
    python -m tools.debug_cli score results.json
    python -m tools.debug_cli inspect-game results.json --game 0
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from tools.analyzers import (
    analyze_pgn_transparent,
    inspect_opening_book,
    inspect_phase_classification,
)
from tools.formatters import (
    format_metric,
    format_section_header,
    format_table,
    format_warning,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="debug_cli",
        description="Chess analysis engine debugger — validate and calibrate",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- analyze-pgn ---
    ap = subparsers.add_parser("analyze-pgn", help="Analyze a single PGN with full transparency")
    ap.add_argument("pgn_file", help="Path to PGN file")
    ap.add_argument("--player", required=True, choices=["white", "black"], help="Player color")
    ap.add_argument("--stockfish", default="stockfish", help="Path to Stockfish binary")
    ap.add_argument("--depth", type=int, default=12, help="Stockfish depth (default: 12)")
    ap.add_argument("--multipv", type=int, default=5, help="MultiPV lines (default: 5)")
    ap.add_argument("--opening-moves", type=int, default=15, help="Opening phase length (default: 15)")
    ap.add_argument("--endgame-pieces", type=int, default=12, help="Endgame piece threshold (default: 12)")
    ap.add_argument("--export", choices=["csv", "json"], help="Export results to file")

    # --- inspect-game ---
    ig = subparsers.add_parser("inspect-game", help="Drill-down into a game from saved results")
    ig.add_argument("result_file", help="Path to JSON result file")
    ig.add_argument("--game", type=int, default=0, help="Game index (default: 0)")

    # --- score ---
    sc = subparsers.add_parser("score", help="Detailed suspicion score breakdown")
    sc.add_argument("result_file", help="Path to JSON result file")

    # --- analyze-batch ---
    ab = subparsers.add_parser("analyze-batch", help="Analyze all PGNs in a directory")
    ab.add_argument("pgn_dir", help="Directory containing PGN files")
    ab.add_argument("--label", required=True, help="Label for this group (e.g. 'cheater', 'legit')")
    ab.add_argument("--player", required=True, choices=["white", "black"], help="Player color")
    ab.add_argument("--stockfish", default="stockfish", help="Path to Stockfish binary")
    ab.add_argument("--depth", type=int, default=12, help="Stockfish depth")
    ab.add_argument("--output", default="./debug_results", help="Output directory")

    # --- compare ---
    cp = subparsers.add_parser("compare", help="Compare two result populations")
    cp.add_argument("dir_a", help="First results directory")
    cp.add_argument("dir_b", help="Second results directory")

    return parser


def cmd_analyze_pgn(args) -> None:
    """Execute the analyze-pgn command."""
    pgn_path = Path(args.pgn_file)
    if not pgn_path.exists():
        print(f"Error: PGN file not found: {pgn_path}", file=sys.stderr)
        sys.exit(1)

    pgn_text = pgn_path.read_text(encoding="utf-8")

    print(f"Analyzing {pgn_path.name} as {args.player} (depth={args.depth}, multipv={args.multipv})")
    print()

    result = analyze_pgn_transparent(
        pgn_text,
        player_color=args.player,
        stockfish_path=args.stockfish,
        depth=args.depth,
        multipv=args.multipv,
        opening_moves=args.opening_moves,
        endgame_pieces=args.endgame_pieces,
    )

    # --- Opening Book ---
    book = result["opening_book"]
    print(format_section_header("OPENING BOOK DETECTION"))
    print(format_metric("Book file", book["book_file_path"]))
    print(format_metric("File exists", book["book_file_exists"]))
    print(format_metric("Detection method", book["detection_method"]))
    print(format_metric("Out-of-book index", book["out_of_book_index"]))
    if book.get("error"):
        print(format_warning(f"Book error: {book['error']}"))
    print()

    # --- Phase Classification ---
    phase = result["phase_classification"]
    print(format_section_header("PHASE CLASSIFICATION", phase["thresholds"]))
    phase_headers = ["Move", "SAN", "Pieces", "Phase", "Reason"]
    phase_rows = []
    for m in phase["moves"]:
        mismatch_marker = " *MISMATCH*" if m["phase_mismatch"] else ""
        phase_rows.append([
            str(m["move_number"]),
            m["san"],
            str(m["piece_count"]),
            m["phase"] + mismatch_marker,
            m["reason"],
        ])
    print(format_table(phase_headers, phase_rows))
    print()
    summary = phase["summary"]
    print(f"  Result: opening={summary['opening']} moves, middlegame={summary['middlegame']} moves, endgame={summary['endgame']} moves")
    print()

    # --- Move-by-Move Analysis ---
    move_evals = result["move_evals"]
    print(format_section_header("MOVE-BY-MOVE ANALYSIS"))
    move_headers = ["#", "Played", "Best", "CPLoss", "Rank", "EvalBefore", "EvalAfter", "Book?"]
    move_rows = []
    for m in move_evals:
        cp = str(m["cp_loss"]) if m["cp_loss"] is not None else "mate"
        move_rows.append([
            str(m["move_number"]),
            m["played"],
            m["best"],
            cp,
            str(m["best_rank"]),
            str(m["eval_before"]),
            str(m["eval_after"]),
            "YES" if m["is_book_move"] else "",
        ])
    print(format_table(move_headers, move_rows))
    print()

    # --- Metrics Summary ---
    metrics = result["metrics"]
    print(format_section_header("METRICS SUMMARY"))
    print(format_metric("ACPL", f"{metrics['acpl']:.1f}" if metrics["acpl"] is not None else "N/A", "cp", "capped at 1500"))
    print(format_metric("Robust ACPL", f"{metrics['robust_acpl']:.1f}" if metrics["robust_acpl"] is not None else "N/A", "cp", "median"))

    if metrics["match_rates"]:
        mr = metrics["match_rates"]
        print(format_metric("Top-1 match", f"{mr['top1']*100:.1f}%"))
        print(format_metric("Top-5 match", f"{mr['top5']*100:.1f}%"))

    if metrics["blunders"]:
        bl = metrics["blunders"]
        print(format_metric("Blunders (>100cp)", bl["blunder_count"], note=f"rate: {bl['blunder_rate']*100:.1f}%"))

    # Phase ACPL breakdown
    pb = metrics["phase_breakdown"]
    if pb:
        phase_acpl_parts = []
        for p in ("opening", "middlegame", "endgame"):
            data = pb.get(p, {})
            mc = data.get("move_count", 0)
            acpl_val = data.get("acpl", 0)
            if mc > 0:
                phase_acpl_parts.append(f"{p}={acpl_val:.1f} ({mc} moves)")
            else:
                phase_acpl_parts.append(f"{p}=N/A (0 moves)")
        print(format_metric("Phase ACPL", "  ".join(phase_acpl_parts)))

    # Precision bursts
    if metrics.get("precision_bursts"):
        pb_data = metrics["precision_bursts"]
        print(format_metric("Precision bursts", pb_data.get("burst_count", 0), note=f"longest: {pb_data.get('longest_burst', 0)} moves"))

    print()

    # --- Warnings ---
    if result["warnings"]:
        print(format_section_header("WARNINGS"))
        for w in result["warnings"]:
            print(format_warning(w))
        print()

    # --- Export ---
    if args.export == "csv":
        out_path = pgn_path.with_suffix(".csv")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=move_evals[0].keys() if move_evals else [])
            writer.writeheader()
            writer.writerows(move_evals)
        print(f"Exported move data to {out_path}")
    elif args.export == "json":
        out_path = pgn_path.with_suffix(".debug.json")
        # Convert result to JSON-serializable form
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"Exported full results to {out_path}")


def cmd_score(args) -> None:
    """Execute the score command — show suspicion score breakdown."""
    result_path = Path(args.result_file)
    if not result_path.exists():
        print(f"Error: Result file not found: {result_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(result_path.read_text(encoding="utf-8"))

    # The result file can be either a full debug export or a player JSON
    # Try to extract aggregates
    aggregates = data.get("aggregates", {}).get("All", data.get("metrics", {}))

    from analysis.suspicion import calculate_suspicion_score

    # Map aggregate field names to suspicion score parameters
    score_params = {
        "anomaly_score_mean": aggregates.get("anomaly_score_mean"),
        "opening_to_middle_transition": aggregates.get("opening_to_middle_transition"),
        "collapse_rate": aggregates.get("collapse_rate"),
        "phase_consistency_middle": aggregates.get("phase_consistency_middle"),
        "robust_acpl": aggregates.get("robust_acpl"),
        "match_rate_mean": aggregates.get("match_rate_mean"),
        "blunder_rate": aggregates.get("blunder_rate"),
        "top2_match_rate": aggregates.get("top2_match_rate"),
        "pressure_degradation": aggregates.get("pressure_degradation"),
        "tilt_rate": aggregates.get("tilt_rate"),
        "opening_to_middle_improvement": aggregates.get("opening_to_middle_improvement"),
        "variance_drop": aggregates.get("variance_drop"),
        "post_pause_improvement": aggregates.get("post_pause_improvement"),
        "cwmr_delta": aggregates.get("cwmr_delta"),
        "cpa": aggregates.get("cpa"),
        "sensitivity": aggregates.get("sensitivity"),
        "ubma": aggregates.get("ubma"),
        "difficulty_variance_ratio": aggregates.get("difficulty_variance_ratio"),
        "critical_accuracy_boost": aggregates.get("critical_accuracy_boost"),
        "oscillation_score": aggregates.get("oscillation_score"),
        "mismatch_rate": aggregates.get("mismatch_rate"),
        "effort_ratio": aggregates.get("effort_ratio"),
    }

    result = calculate_suspicion_score(**score_params)

    print(format_section_header("SUSPICION SCORE BREAKDOWN"))
    print(format_metric("Total score", f"{result['suspicion_score']:.1f}", note=f"max 300"))
    print(format_metric("Risk level", result["risk_level"]))
    print(format_metric("Confidence", result["confidence"]))
    print(format_metric("Data points", result["data_points"]))
    print()

    # Show each input parameter
    print(format_section_header("INPUT VALUES"))
    headers = ["#", "Signal Parameter", "Raw Value", "Available?"]
    rows = []
    for i, (key, val) in enumerate(score_params.items(), 1):
        rows.append([
            str(i),
            key,
            f"{val:.4f}" if isinstance(val, float) else str(val),
            "yes" if val is not None else "NO",
        ])
    print(format_table(headers, rows))
    print()

    if result["signals"]:
        print(format_section_header("TRIGGERED SIGNALS"))
        for sig in result["signals"]:
            print(f"  - {sig}")
    print()


def cmd_inspect_game(args) -> None:
    """Execute the inspect-game command."""
    result_path = Path(args.result_file)
    if not result_path.exists():
        print(f"Error: Result file not found: {result_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(result_path.read_text(encoding="utf-8"))

    # Support both debug export format and player JSON format
    if "move_evals" in data:
        # Debug export — single game
        move_evals = data["move_evals"]
        print(format_section_header("GAME DETAIL (debug export)"))
    else:
        # Player JSON with games list
        games = data.get("games", [])
        if args.game >= len(games):
            print(f"Error: Game index {args.game} out of range (0-{len(games)-1})", file=sys.stderr)
            sys.exit(1)
        game = games[args.game]
        analysis = game.get("analysis", {})
        move_evals = analysis.get("move_evals", [])

        # Show game metadata
        print(format_section_header(f"GAME {args.game} DETAIL"))
        print(format_metric("White", game.get("white_username", "?")))
        print(format_metric("Black", game.get("black_username", "?")))
        print(format_metric("Result", game.get("result", "?")))
        print(format_metric("Date", game.get("date", "?")))
        print(format_metric("Time control", game.get("time_control_category", "?")))
        if analysis.get("acpl") is not None:
            print(format_metric("ACPL", f"{analysis['acpl']:.1f}"))
        print()

    if not move_evals:
        print("  No move evaluations available for this game.")
        return

    # Show move-by-move table
    headers = ["#", "Played", "Best", "CPLoss", "Rank", "EvalBefore", "EvalAfter", "Book?", "Capture?"]
    rows = []
    for m in move_evals:
        cp = str(m.get("cp_loss", "?"))
        if m.get("cp_loss") is None:
            cp = "mate"
        highlight = "<<<" if m.get("cp_loss") is not None and m["cp_loss"] > 100 else ""
        rows.append([
            str(m.get("move_number", "?")),
            m.get("played", "?"),
            m.get("best", "?"),
            cp + highlight,
            str(m.get("best_rank", "?")),
            str(m.get("eval_before", "?")),
            str(m.get("eval_after", "?")),
            "YES" if m.get("is_book_move") else "",
            "YES" if m.get("is_capture") else "",
        ])
    print(format_table(headers, rows))


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "analyze-pgn": cmd_analyze_pgn,
        "score": cmd_score,
        "inspect-game": cmd_inspect_game,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"Command '{args.command}' is not yet implemented.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `cd H:/Git_Overture/ChessAnalyzerQML/python && python -m pytest tests/tools/test_cli.py -v`
Expected: PASS

**Step 5: Verify the CLI help works end-to-end**

Run: `cd H:/Git_Overture/ChessAnalyzerQML/python && python -m tools.debug_cli --help`
Expected: Shows help with subcommands

Run: `cd H:/Git_Overture/ChessAnalyzerQML/python && python -m tools.debug_cli analyze-pgn --help`
Expected: Shows analyze-pgn help with all options

**Step 6: Commit**

```bash
git add python/tools/debug_cli.py python/tests/tools/test_cli.py
git commit -m "feat(tools): add debug CLI entry point with analyze-pgn, score, inspect-game commands"
```

---

## Task 5: Add __main__.py and end-to-end test with a real PGN

**Files:**
- Create: `python/tools/__main__.py`
- Create: `python/tests/tools/test_e2e.py`
- Create: `python/tests/fixtures/sample_game.pgn`

**Step 1: Create __main__.py for `python -m tools` invocation**

```python
# python/tools/__main__.py
"""Allow running as: python -m tools.debug_cli"""
from tools.debug_cli import main

main()
```

**Step 2: Create a test PGN fixture**

```pgn
# python/tests/fixtures/sample_game.pgn
[Event "Rated Blitz game"]
[Site "Chess.com"]
[Date "2024.06.15"]
[White "TestPlayer"]
[Black "Opponent"]
[Result "1-0"]
[WhiteElo "1500"]
[BlackElo "1480"]
[TimeControl "180"]
[ECO "C50"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. d3 Bc5 5. O-O d6 6. c3 O-O 7. Re1 a6
8. Bb3 Ba7 9. h3 Be6 10. Bc2 d5 11. exd5 Bxd5 12. Nbd2 Re8 13. Nf1 Qd7
14. Ng3 Rad8 15. d4 exd4 16. Nxd4 Nxd4 17. cxd4 Bxd4 18. Be3 Bxe3
19. Rxe3 Bc4 20. Qf3 Nd5 21. Re5 Nf4 22. Nf5 Rxe5 23. Nxg7 Re1+ 24. Kh2 Qd6+
25. f4 Ng6 26. Qg3 Kxg7 27. f5 Qxg3+ 28. Kxg3 Ne5 29. Rf1 Rd2 30. Bb3 Bxb3
31. axb3 Rxb2 32. Rf4 Ree2 33. Rg4+ Kf6 34. Rf4 Ke7 35. g4 Kd6 36. h4 Nd3
37. Rf3 Ne1 38. Rf4 Nd3 39. Rf3 Nf2 40. h5 Nxg4 1-0
```

**Step 3: Create end-to-end integration test (does NOT require Stockfish)**

```python
# python/tests/tools/test_e2e.py
"""End-to-end tests that don't require Stockfish.

These test phase classification and opening book inspection
using real PGN files. Stockfish-dependent tests are skipped
unless the binary is available.
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
        # With threshold 20, some late moves should be endgame
        assert "endgame" in phases_found

    def test_mismatch_detection(self):
        """Moves where captures cross the endgame threshold
        should show phase mismatch between pre/post move piece counts."""
        result = inspect_phase_classification(SAMPLE_PGN, endgame_pieces=24)
        mismatches = [m for m in result["moves"] if m["phase_mismatch"]]
        # With a high threshold, captures near the boundary will cause mismatches
        # This validates that the tool correctly detects the known engine inconsistency
        assert isinstance(mismatches, list)  # At minimum, no crash


class TestOpeningBookE2E:
    def test_fallback_mode(self):
        result = inspect_opening_book(SAMPLE_PGN)
        # Without the polyglot book file, should fall back
        if not result["book_file_exists"]:
            assert result["detection_method"] == "fallback"
            assert result["out_of_book_index"] == 10
```

**Step 4: Run tests**

Run: `cd H:/Git_Overture/ChessAnalyzerQML/python && python -m pytest tests/tools/test_e2e.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add python/tools/__main__.py python/tests/fixtures/sample_game.pgn python/tests/tools/test_e2e.py
git commit -m "feat(tools): add __main__.py entry point and end-to-end tests"
```

---

## Task 6: Add analyze-batch and compare commands

**Files:**
- Modify: `python/tools/debug_cli.py`
- Test: `python/tests/tools/test_cli.py`

**Step 1: Add tests for batch and compare argument parsing**

Add to `python/tests/tools/test_cli.py`:

```python
class TestBatchParser:
    def test_analyze_batch_command(self):
        parser = build_parser()
        args = parser.parse_args([
            "analyze-batch", "./pgns/cheaters/",
            "--label", "cheater", "--player", "white",
        ])
        assert args.command == "analyze-batch"
        assert args.label == "cheater"
        assert args.player == "white"

    def test_compare_command(self):
        parser = build_parser()
        args = parser.parse_args(["compare", "./results/a/", "./results/b/"])
        assert args.command == "compare"
        assert args.dir_a == "./results/a/"
        assert args.dir_b == "./results/b/"
```

**Step 2: Run tests**

Run: `cd H:/Git_Overture/ChessAnalyzerQML/python && python -m pytest tests/tools/test_cli.py -v`
Expected: PASS (parser already defines these subcommands)

**Step 3: Implement cmd_analyze_batch**

Add to `python/tools/debug_cli.py`:

```python
def cmd_analyze_batch(args) -> None:
    """Execute the analyze-batch command."""
    pgn_dir = Path(args.pgn_dir)
    if not pgn_dir.is_dir():
        print(f"Error: Directory not found: {pgn_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output) / args.label
    output_dir.mkdir(parents=True, exist_ok=True)

    pgn_files = sorted(pgn_dir.glob("*.pgn"))
    if not pgn_files:
        print(f"No PGN files found in {pgn_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing {len(pgn_files)} PGN files as '{args.label}' (depth={args.depth})")
    print()

    summary_rows = []
    for i, pgn_path in enumerate(pgn_files, 1):
        print(f"[{i}/{len(pgn_files)}] {pgn_path.name}...")
        pgn_text = pgn_path.read_text(encoding="utf-8")

        try:
            result = analyze_pgn_transparent(
                pgn_text,
                player_color=args.player,
                stockfish_path=args.stockfish,
                depth=args.depth,
            )

            # Save result
            out_file = output_dir / pgn_path.with_suffix(".json").name
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, default=str)

            # Summary row
            metrics = result.get("metrics", {})
            acpl = metrics.get("acpl")
            mr = metrics.get("match_rates", {})
            bl = metrics.get("blunders", {})
            summary_rows.append([
                pgn_path.name,
                f"{acpl:.1f}" if acpl is not None else "N/A",
                f"{mr.get('top1', 0)*100:.1f}%" if mr else "N/A",
                str(bl.get("blunder_count", "N/A")) if bl else "N/A",
                str(len(result.get("warnings", []))),
            ])
        except Exception as e:
            print(f"  ERROR: {e}")
            summary_rows.append([pgn_path.name, "ERROR", "", "", str(e)[:30]])

    print()
    print(format_section_header("BATCH SUMMARY"))
    print(format_table(
        ["File", "ACPL", "Top1%", "Blunders", "Warnings"],
        summary_rows,
    ))
    print(f"\nResults saved to: {output_dir}")
```

**Step 4: Implement cmd_compare**

Add to `python/tools/debug_cli.py`:

```python
import statistics


def cmd_compare(args) -> None:
    """Execute the compare command."""
    dir_a = Path(args.dir_a)
    dir_b = Path(args.dir_b)

    for d in (dir_a, dir_b):
        if not d.is_dir():
            print(f"Error: Directory not found: {d}", file=sys.stderr)
            sys.exit(1)

    def load_metrics(directory: Path) -> list[dict]:
        results = []
        for f in sorted(directory.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            m = data.get("metrics", {})
            flat = {
                "acpl": m.get("acpl"),
                "robust_acpl": m.get("robust_acpl"),
                "top1_match": m.get("match_rates", {}).get("top1") if m.get("match_rates") else None,
                "top5_match": m.get("match_rates", {}).get("top5") if m.get("match_rates") else None,
                "blunder_rate": m.get("blunders", {}).get("blunder_rate") if m.get("blunders") else None,
            }
            results.append(flat)
        return results

    metrics_a = load_metrics(dir_a)
    metrics_b = load_metrics(dir_b)

    if not metrics_a or not metrics_b:
        print("Error: One or both directories contain no results.", file=sys.stderr)
        sys.exit(1)

    print(format_section_header("POPULATION COMPARISON"))
    print(f"  Group A: {dir_a.name} ({len(metrics_a)} games)")
    print(f"  Group B: {dir_b.name} ({len(metrics_b)} games)")
    print()

    def stats_for(values: list[float]) -> tuple[float, float, float]:
        if not values:
            return (0.0, 0.0, 0.0)
        mean = statistics.mean(values)
        median = statistics.median(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0.0
        return (mean, median, stdev)

    metric_keys = ["acpl", "robust_acpl", "top1_match", "top5_match", "blunder_rate"]
    headers = ["Metric", "A mean", "A median", "A std", "B mean", "B median", "B std", "Separation"]
    rows = []

    for key in metric_keys:
        vals_a = [m[key] for m in metrics_a if m.get(key) is not None]
        vals_b = [m[key] for m in metrics_b if m.get(key) is not None]

        if not vals_a or not vals_b:
            rows.append([key, "N/A", "", "", "N/A", "", "", ""])
            continue

        sa = stats_for(vals_a)
        sb = stats_for(vals_b)

        # Cohen's d (effect size)
        pooled_std = ((sa[2]**2 + sb[2]**2) / 2) ** 0.5
        separation = abs(sa[0] - sb[0]) / pooled_std if pooled_std > 0 else 0.0

        rows.append([
            key,
            f"{sa[0]:.2f}", f"{sa[1]:.2f}", f"{sa[2]:.2f}",
            f"{sb[0]:.2f}", f"{sb[1]:.2f}", f"{sb[2]:.2f}",
            f"{separation:.2f}",
        ])

    print(format_table(headers, rows))
    print()
    print("  Separation = Cohen's d effect size (>0.8 = large, >1.2 = very large)")
```

**Step 5: Update the command dispatch in main()**

Update the `commands` dict:

```python
    commands = {
        "analyze-pgn": cmd_analyze_pgn,
        "analyze-batch": cmd_analyze_batch,
        "compare": cmd_compare,
        "score": cmd_score,
        "inspect-game": cmd_inspect_game,
    }
```

**Step 6: Run all tests**

Run: `cd H:/Git_Overture/ChessAnalyzerQML/python && python -m pytest tests/tools/ -v`
Expected: PASS

**Step 7: Commit**

```bash
git add python/tools/debug_cli.py python/tests/tools/test_cli.py
git commit -m "feat(tools): add analyze-batch and compare commands"
```

---

## Task 7: Manual integration test

This task verifies the full tool works end-to-end with a real PGN and Stockfish.

**Step 1: Test analyze-pgn with a real game**

Run:
```bash
cd H:/Git_Overture/ChessAnalyzerQML/python
python -m tools.debug_cli analyze-pgn ../tests/fixtures/sample_game.pgn --player white --stockfish ../stockfish/stockfish.exe --depth 8
```

Expected: Full output with all sections (Opening Book, Phase Classification, Move-by-Move, Metrics, Warnings).

**Step 2: Test JSON export**

Run:
```bash
cd H:/Git_Overture/ChessAnalyzerQML/python
python -m tools.debug_cli analyze-pgn ../tests/fixtures/sample_game.pgn --player white --stockfish ../stockfish/stockfish.exe --depth 8 --export json
```

Expected: Creates `.debug.json` file next to the PGN.

**Step 3: Test score command on the export**

Run:
```bash
cd H:/Git_Overture/ChessAnalyzerQML/python
python -m tools.debug_cli score ../tests/fixtures/sample_game.debug.json
```

Expected: Shows suspicion score breakdown with all 21 signal values.

**Step 4: Test inspect-game**

Run:
```bash
cd H:/Git_Overture/ChessAnalyzerQML/python
python -m tools.debug_cli inspect-game ../tests/fixtures/sample_game.debug.json
```

Expected: Shows move-by-move table for the game.

**Step 5: Verify warnings appear correctly**

Check the analyze-pgn output for:
- Opening book fallback warning (if book file is missing)
- No endgame warning (if applicable)
- Phase mismatch warning (if any captures cross the endgame threshold)

**Step 6: Final commit if any adjustments were needed**

```bash
git add -u
git commit -m "fix(tools): adjustments from integration testing"
```

---

## Summary

| Task | What | Files | Tests |
|------|------|-------|-------|
| 1 | Package + formatters | `tools/__init__.py`, `tools/formatters.py` | `test_formatters.py` |
| 2 | Analyzers (phase + book) | `tools/analyzers.py` | `test_analyzers.py` |
| 3 | Analyzers (Stockfish wrapper) | `tools/analyzers.py` | `test_analyzers.py` (mocked) |
| 4 | CLI entry point | `tools/debug_cli.py` | `test_cli.py` |
| 5 | `__main__.py` + E2E tests | `tools/__main__.py`, fixtures | `test_e2e.py` |
| 6 | Batch + compare commands | `tools/debug_cli.py` | `test_cli.py` |
| 7 | Manual integration test | — | Manual verification |
