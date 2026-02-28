#!/usr/bin/env python3
"""
CLI entry point for ChessAnalyzerQML.

Designed to be launched by QProcess from C++.
All output is JSON lines to stdout for structured communication.

Protocol:
  {"type": "status", "message": "..."}
  {"type": "progress", "analyzed": N, "total": M, "message": "..."}
  {"type": "result", "username": "...", "suspicion_score": N, ...}
  {"type": "error", "message": "..."}
"""

import argparse
import json
import sys
import traceback
from pathlib import Path

# Add python/ directory to path so imports work
sys.path.insert(0, str(Path(__file__).parent))

# Force UTF-8 stdout on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Redirect all logging to stderr so it doesn't pollute JSON stdout
import logging
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)


def emit(data: dict):
    """Write a JSON line to stdout and flush immediately."""
    print(json.dumps(data, ensure_ascii=False), flush=True)


def analyze(args):
    """Run the analysis pipeline for a player."""
    try:
        emit({"type": "status", "message": "Initializing database..."})

        from database import create_tables, get_session
        create_tables()
        session = get_session()

        emit({"type": "status", "message": f"Fetching games for {args.username}..."})

        from services.analysis_service import AnalysisService

        service = AnalysisService(
            session=session,
            stockfish_path=args.stockfish,
            depth=args.depth,
        )

        # Track progress
        def on_progress(progress_data):
            analyzed = progress_data.get("games_analyzed", 0)
            total = progress_data.get("games_requested", 0)
            emit({
                "type": "progress",
                "analyzed": analyzed,
                "total": total,
                "message": f"Game {analyzed}/{total} analyzed",
            })

        # Run the full pipeline
        stats = service.analyze_player(
            username=args.username,
            game_count=args.games,
            workers=args.workers,
            months=6,
            progress_callback=on_progress,
        )

        emit({"type": "status", "message": "Reading results..."})

        # Emit pipeline stats as debug info
        emit({
            "type": "status",
            "message": f"Pipeline: {stats.get('new_analyses', 0)} analyzed, "
                       f"{stats.get('failed_analyses', 0)} failed, "
                       f"aggregates_updated={stats.get('aggregates_updated', False)}"
        })

        # Try reading aggregates
        result = _build_result_from_aggregates(session, args.username)

        # If aggregates gave us nothing, try reading analyses directly
        if result is None or result.get("games_count", 0) == 0:
            result = _build_result_from_analyses(session, args.username, stats)

        emit(result)
        session.close()

    except Exception as e:
        emit({"type": "error", "message": f"{e}\n{traceback.format_exc()}"})
        sys.exit(1)


def _build_result_from_aggregates(session, username: str) -> dict | None:
    """Try to build result from PlayerAggregate table."""
    try:
        from repositories import AggregateRepository
        aggregate_repo = AggregateRepository(session)
        aggregates = aggregate_repo.get_all_by_username(username)

        if not aggregates:
            return None

        agg = aggregates[0]
        return {
            "type": "result",
            "username": username,
            "suspicion_score": agg.suspicion_score or 0,
            "risk_level": _risk_level(agg.suspicion_score or 0),
            "acpl_mean": round(agg.acpl_mean or 0, 2),
            "top1_match_rate": round((agg.top1_match_rate_mean or 0) * 100, 1),
            "games_count": agg.games_count or 0,
            "blunder_rate": round((agg.blunder_rate_mean or 0) * 100, 1),
        }
    except Exception as e:
        emit({"type": "status", "message": f"Aggregate read failed: {e}"})
        return None


def _build_result_from_analyses(session, username: str, stats: dict) -> dict:
    """Fallback: build result directly from GameAnalysis rows."""
    try:
        from repositories import AnalysisRepository
        repo = AnalysisRepository(session)
        analyses = repo.get_by_username(username)

        if not analyses:
            return {
                "type": "result",
                "username": username,
                "suspicion_score": 0,
                "risk_level": "UNKNOWN",
                "acpl_mean": 0,
                "top1_match_rate": 0,
                "games_count": 0,
                "blunder_rate": 0,
            }

        # Compute basic stats from individual analyses
        acpls = [a.acpl for a in analyses if a.acpl is not None]
        top1s = [a.top1_match_rate for a in analyses if a.top1_match_rate is not None]
        blunders = [a.blunder_rate for a in analyses if a.blunder_rate is not None]

        acpl_mean = sum(acpls) / len(acpls) if acpls else 0
        top1_mean = sum(top1s) / len(top1s) if top1s else 0
        blunder_mean = sum(blunders) / len(blunders) if blunders else 0

        # Try computing suspicion score from the analyses
        suspicion_score = 0
        risk_level = "LOW"
        try:
            from analysis.suspicion import calculate_suspicion_score
            # Collect all move_evals for suspicion scoring
            all_move_evals = []
            for a in analyses:
                if a.move_evals:
                    import json as _json
                    evals = _json.loads(a.move_evals) if isinstance(a.move_evals, str) else a.move_evals
                    all_move_evals.extend(evals)

            if all_move_evals:
                susp = calculate_suspicion_score(all_move_evals)
                suspicion_score = susp.get("score", 0)
                risk_level = susp.get("risk_level", _risk_level(suspicion_score))
        except Exception:
            pass

        return {
            "type": "result",
            "username": username,
            "suspicion_score": round(suspicion_score, 1),
            "risk_level": risk_level,
            "acpl_mean": round(acpl_mean, 2),
            "top1_match_rate": round(top1_mean * 100, 1),
            "games_count": len(analyses),
            "blunder_rate": round(blunder_mean * 100, 1),
        }
    except Exception as e:
        return {
            "type": "result",
            "username": username,
            "suspicion_score": 0,
            "risk_level": "ERROR",
            "acpl_mean": 0,
            "top1_match_rate": 0,
            "games_count": 0,
            "blunder_rate": 0,
        }


def _risk_level(score: float) -> str:
    """Convert suspicion score to risk level string."""
    if score >= 150:
        return "VERY HIGH"
    elif score >= 100:
        return "HIGH"
    elif score >= 60:
        return "MODERATE"
    else:
        return "LOW"


def _find_stockfish() -> str:
    """Auto-detect Stockfish path relative to project root."""
    project_root = Path(__file__).parent.parent
    candidates = [
        project_root / "stockfish" / "stockfish-windows-x86-64-avx2.exe",
        project_root / "stockfish" / "stockfish.exe",
        project_root / "stockfish" / "stockfish",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return "stockfish"  # fallback to PATH


def main():
    parser = argparse.ArgumentParser(description="Chess Player Analyzer CLI")
    subparsers = parser.add_subparsers(dest="command")

    default_sf = _find_stockfish()

    # analyze subcommand
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a chess player")
    analyze_parser.add_argument("--username", required=True, help="Chess.com username")
    analyze_parser.add_argument("--games", type=int, default=50, help="Number of games")
    analyze_parser.add_argument("--depth", type=int, default=12, help="Stockfish depth")
    analyze_parser.add_argument("--workers", type=int, default=4, help="Parallel workers")
    analyze_parser.add_argument("--stockfish", default=default_sf, help="Stockfish path")

    args = parser.parse_args()

    if args.command == "analyze":
        analyze(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
