# Chess Analysis Debugger CLI — Design Document

**Date:** 2026-03-01
**Status:** Approved

## Problem

The chess analysis engine (`python/`) produces unreliable results. Known issues include:

- Tilt/recovery fields never populate (wrong field names)
- Recovery rate units mismatch (percentage vs 0-1)
- Move-time alignment bug (hardcoded 10-move skip)
- Phase classification offset between functions
- Inconsistent endgame piece thresholds (12 vs 6)
- Inconsistent suspicion risk thresholds (60/100/150 vs 80/130/180)
- Pressure degradation units mismatch
- Missing opening book file (silent fallback)
- No tests anywhere

A debugging tool is needed to validate calculations step-by-step and calibrate thresholds using known cheater/legitimate player PGNs.

## Solution

A CLI tool at `python/tools/debug_cli.py` that imports the existing engine modules directly and exposes intermediate calculation state that is normally hidden.

## Design Decisions

- **CLI, not GUI** — fastest to build, sufficient for validation/calibration at 5-10 player scale
- **Shares the engine** — imports `python/analysis/` and `python/services/calculators/` directly, so bugs in the engine are reproduced faithfully
- **Local PGN input** — does not use Chess.com fetching; works with downloaded PGN files
- **No new dependencies** — uses only what the project already has
- **Transparency over convenience** — shows parameters, thresholds, and classification reasoning, not just results

## Commands

### 1. `analyze-pgn` (primary command)

Analyzes a single PGN file with full transparency.

```bash
python python/tools/debug_cli.py analyze-pgn game.pgn --player white --depth 16 --stockfish /path/to/stockfish
```

Output sections:
- **Phase classification** — shows thresholds, piece counts per move, phase assignment reason
- **Opening book detection** — shows whether book file exists, fallback behavior, which moves are book
- **Move-by-move analysis** — table: move#, played, best, cp_loss, rank, phase, eval_before, eval_after, is_book
- **Metrics summary** — ACPL, robust ACPL, match rates, blunders, phase breakdown
- **Warnings** — automatic detection of suspicious situations (0 endgame moves, book fallback, misalignment)

Options: `--export csv` to write results to file.

### 2. `analyze-batch`

Analyzes all PGNs in a directory with a label.

```bash
python python/tools/debug_cli.py analyze-batch ./pgns/cheaters/ --label cheater --depth 16 --stockfish ...
```

Saves per-game JSON results to output directory. Shows summary table (one row per game).

### 3. `compare`

Compares two labeled populations.

```bash
python python/tools/debug_cli.py compare ./results/cheater/ ./results/legit/
```

Per metric: mean, median, std dev for each group. Normalized separability score. Suggests most discriminant signals.

### 4. `inspect-game`

Drill-down into a specific game from batch results.

```bash
python python/tools/debug_cli.py inspect-game result.json --game 3
```

Full move-by-move detail including phase, time data, precision bursts, tilt episodes. Highlights problematic moves.

### 5. `score`

Detailed suspicion score breakdown.

```bash
python python/tools/debug_cli.py score result.json
```

Shows all 21 signals: raw value, points assigned, threshold, max possible points.

## Architecture

```
python/tools/
    __init__.py
    debug_cli.py          # Entry point, argparse, command dispatch
    formatters.py         # Terminal table/section formatting
    analyzers.py          # Wrappers that call engine functions and capture intermediates
```

### Data flow

```
debug_cli.py
  -> analyzers.py
       -> analysis.engine.analyze_game()
       -> analysis.phase_analysis.calculate_phase_metrics()
       -> analysis.opening_book.OpeningBookDetector
       -> analysis.suspicion.calculate_suspicion_score()
       -> services.calculators.calculate_all()
```

### How intermediate data is captured

`analyzers.py` does not reimplement engine functions. It:

1. Runs the opening book detector separately to show book vs non-book classification
2. Iterates the PGN counting pieces to show phase classification with thresholds
3. Runs `analyze_game()` and formats full results
4. Generates warnings by cross-referencing intermediate state

## Future extensibility

- `analyze-batch` + `compare` enable future large-scale calibration when bigger datasets become available
- CSV export allows visualization in external tools (Jupyter, matplotlib, Excel)
- Commands can be expanded as new debugging needs arise
