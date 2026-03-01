"""Chess analysis debugger CLI.

Usage:
    cd python/
    python -m tools.debug_cli analyze-pgn game.pgn --player white --stockfish path/to/stockfish
    python -m tools.debug_cli score results.json
    python -m tools.debug_cli inspect-game results.json --game 0
"""

import argparse
import csv
import json
import statistics
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
        description="Chess analysis engine debugger",
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
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"Exported full results to {out_path}")


def cmd_score(args) -> None:
    """Execute the score command."""
    result_path = Path(args.result_file)
    if not result_path.exists():
        print(f"Error: Result file not found: {result_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(result_path.read_text(encoding="utf-8"))
    aggregates = data.get("aggregates", {}).get("All", data.get("metrics", {}))

    from analysis.suspicion import calculate_suspicion_score

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
    print(format_metric("Total score", f"{result['suspicion_score']:.1f}", note="max 300"))
    print(format_metric("Risk level", result["risk_level"]))
    print(format_metric("Confidence", result["confidence"]))
    print(format_metric("Data points", result["data_points"]))
    print()

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

    if "move_evals" in data:
        move_evals = data["move_evals"]
        print(format_section_header("GAME DETAIL (debug export)"))
    else:
        games = data.get("games", [])
        if args.game >= len(games):
            print(f"Error: Game index {args.game} out of range (0-{len(games)-1})", file=sys.stderr)
            sys.exit(1)
        game = games[args.game]
        analysis = game.get("analysis", {})
        move_evals = analysis.get("move_evals", [])

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

            out_file = output_dir / pgn_path.with_suffix(".json").name
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, default=str)

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


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "analyze-pgn": cmd_analyze_pgn,
        "analyze-batch": cmd_analyze_batch,
        "compare": cmd_compare,
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
