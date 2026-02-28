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


def check(args):
    """Check if a Chess.com player exists and get game count."""
    try:
        import requests

        username = args.username.strip().lower()
        # Check player profile exists
        resp = requests.get(
            f"https://api.chess.com/pub/player/{username}",
            headers={"User-Agent": "ChessAnalyzerQML/1.0"},
            timeout=10,
        )

        if resp.status_code == 404:
            emit({"type": "result", "exists": False, "username": username})
            return

        if resp.status_code != 200:
            emit({"type": "error", "message": f"Chess.com API error: HTTP {resp.status_code}"})
            sys.exit(1)

        # Get archives to count games
        archives_resp = requests.get(
            f"https://api.chess.com/pub/player/{username}/games/archives",
            headers={"User-Agent": "ChessAnalyzerQML/1.0"},
            timeout=10,
        )

        games_available = 0
        months = 0
        if archives_resp.status_code == 200:
            archives = archives_resp.json().get("archives", [])
            months = len(archives)

            # Count games from the last 6 months (or fewer if less available)
            recent = archives[-6:] if len(archives) >= 6 else archives
            for url in recent:
                try:
                    month_resp = requests.get(
                        url,
                        headers={"User-Agent": "ChessAnalyzerQML/1.0"},
                        timeout=15,
                    )
                    if month_resp.status_code == 200:
                        games_available += len(month_resp.json().get("games", []))
                except Exception:
                    pass

        emit({
            "type": "result",
            "exists": True,
            "username": username,
            "games_available": games_available,
            "months": min(months, 6),
        })

    except Exception as e:
        emit({"type": "error", "message": str(e)})
        sys.exit(1)


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


def _parse_historical(agg, key: str) -> list:
    """Extract a timeline array from aggregate historical_data JSON."""
    try:
        data = agg.historical_data
        if data is None:
            return []
        if isinstance(data, str):
            data = json.loads(data)
        return data.get(key, [])
    except Exception:
        return []


def _build_result_from_aggregates(session, username: str) -> dict | None:
    """Try to build result from PlayerAggregate table."""
    try:
        from repositories import AggregateRepository
        aggregate_repo = AggregateRepository(session)
        aggregates = aggregate_repo.get_all_by_username(username)

        if not aggregates:
            return None

        agg = aggregates[0]

        # Recompute suspicion signals from aggregate fields
        signals = []
        confidence = "low"
        try:
            from analysis.suspicion import calculate_suspicion_score
            susp = calculate_suspicion_score(
                anomaly_score_mean=agg.anomaly_score_mean,
                opening_to_middle_transition=agg.opening_to_middle_transition,
                collapse_rate=agg.collapse_rate,
                phase_consistency_middle=agg.phase_consistency_middle,
                robust_acpl=agg.robust_acpl,
                match_rate_mean=agg.top5_match_rate_mean,
                blunder_rate=agg.blunder_rate_mean,
                top2_match_rate=agg.top2_match_rate_mean,
                pressure_degradation=agg.pressure_degradation,
                tilt_rate=agg.tilt_rate,
                opening_to_middle_improvement=getattr(agg, 'opening_to_middle_improvement', None),
                variance_drop=getattr(agg, 'variance_drop', None),
                post_pause_improvement=getattr(agg, 'post_pause_improvement', None),
            )
            signals = susp.get("signals", [])
            confidence = susp.get("confidence", "low")
        except Exception:
            pass

        # Derive psychological profile from aggregate fields
        psych_profile = _derive_psychological_profile(agg)

        # Format date range
        first_date = ""
        last_date = ""
        if agg.first_game_date:
            first_date = agg.first_game_date.strftime("%b %Y")
        if agg.last_game_date:
            last_date = agg.last_game_date.strftime("%b %Y")

        return {
            "type": "result",
            "username": username,

            # Core (backward compat)
            "suspicion_score": agg.suspicion_score or 0,
            "risk_level": _risk_level(agg.suspicion_score or 0),
            "acpl_mean": round(agg.acpl_mean or 0, 2),
            "top1_match_rate": round((agg.top1_match_rate_mean or 0) * 100, 1),
            "games_count": agg.games_count or 0,
            "blunder_rate": round((agg.blunder_rate_mean or 0) * 100, 1),

            # Signals
            "signals": signals,
            "confidence": confidence,

            # ACPL statistics
            "acpl_median": round(agg.acpl_median or 0, 2),
            "acpl_std": round(agg.acpl_std or 0, 2),
            "acpl_min": round(agg.acpl_min or 0, 2),
            "acpl_max": round(agg.acpl_max or 0, 2),
            "acpl_p25": round(agg.acpl_p25 or 0, 2),
            "acpl_p75": round(agg.acpl_p75 or 0, 2),
            "robust_acpl": round(agg.robust_acpl or 0, 2),

            # Match rates
            "top2_match_rate": round((agg.top2_match_rate_mean or 0) * 100, 1),
            "top3_match_rate": round((agg.top3_match_rate_mean or 0) * 100, 1),

            # Rank distribution
            "rank_0_pct": round((agg.rank_0_mean or 0) * 100, 1),
            "rank_1_pct": round((agg.rank_1_mean or 0) * 100, 1),
            "rank_2_pct": round((agg.rank_2_mean or 0) * 100, 1),
            "rank_3plus_pct": round((agg.rank_3plus_mean or 0) * 100, 1),

            # Phases
            "phase_acpl_opening": round(agg.phase_consistency_opening or 0, 1),
            "phase_acpl_middle": round(agg.phase_consistency_middle or 0, 1),
            "phase_acpl_endgame": round(agg.phase_consistency_endgame or 0, 1),
            "opening_to_middle_transition": round(agg.opening_to_middle_transition or 0, 1),
            "middle_to_endgame_transition": round(agg.middle_to_endgame_transition or 0, 1),
            "collapse_rate": round((agg.collapse_rate or 0) * 100, 1),

            # Psychological
            "psychological_profile": psych_profile,
            "tilt_rate": round(agg.tilt_rate or 0, 2),
            "recovery_rate": round((agg.recovery_rate or 0) * 100, 1),
            "pressure_degradation": round(agg.pressure_degradation or 0, 1),
            "closing_acpl": round(agg.closing_acpl or 0, 2),

            # Temporal
            "time_complexity_correlation": round(agg.time_complexity_correlation or 0, 3),
            "anomaly_score": round(agg.anomaly_score_mean or 0, 1),

            # Precision bursts
            "precision_burst_mean": round(agg.precision_burst_mean or 0, 2),
            "longest_burst_mean": round(agg.longest_burst_mean or 0, 1),
            "precision_rate": round((agg.precision_rate_mean or 0) * 100, 1),

            # Phase 1B — advanced suspicion signals
            "opening_to_middle_improvement": round(getattr(agg, 'opening_to_middle_improvement', None) or 0, 1),
            "variance_drop": round(getattr(agg, 'variance_drop', None) or 0, 2),
            "post_pause_improvement": round(getattr(agg, 'post_pause_improvement', None) or 0, 1),

            # Additional stats
            "blunder_rate_std": round(agg.blunder_rate_std or 0, 3),
            "move_count_median": round(agg.move_count_median or 0, 1),

            # Historical timelines
            "acpl_timeline": _parse_historical(agg, "acpl_timeline"),
            "match_rate_timeline": _parse_historical(agg, "match_rate_timeline"),

            # Meta
            "move_count_mean": round(agg.move_count_mean or 0, 1),
            "first_game_date": first_date,
            "last_game_date": last_date,
        }
    except Exception as e:
        emit({"type": "status", "message": f"Aggregate read failed: {e}"})
        return None


def _derive_psychological_profile(agg) -> str:
    """Derive psychological profile label from aggregate fields."""
    recovery = agg.recovery_rate or 0
    closing = agg.closing_acpl or 0
    pressure = agg.pressure_degradation or 0
    tilt = agg.tilt_rate or 0

    if tilt == 0 and recovery > 0.95 and pressure < 5:
        return "ENGINE_LIKE"
    is_resilient = recovery > 0.6
    is_fragile = recovery < 0.3
    good_closer = 0 < closing < 50
    poor_closer = closing > 80
    handles_pressure = pressure != 0 and pressure < 20
    struggles_pressure = pressure > 50

    if is_resilient and good_closer:
        return "RESILIENT_CLOSER"
    elif is_resilient and poor_closer:
        return "RESILIENT_SHAKY"
    elif is_fragile and good_closer:
        return "FRAGILE_CLOSER"
    elif is_fragile and poor_closer:
        return "FRAGILE_CRUMBLER"
    elif handles_pressure:
        return "PRESSURE_FIGHTER"
    elif struggles_pressure:
        return "PRESSURE_VULNERABLE"
    return "NORMAL_HUMAN"


def _build_result_from_analyses(session, username: str, stats: dict) -> dict:
    """Fallback: build result directly from GameAnalysis rows."""
    empty = {
        "type": "result",
        "username": username,
        "suspicion_score": 0, "risk_level": "UNKNOWN",
        "acpl_mean": 0, "top1_match_rate": 0,
        "games_count": 0, "blunder_rate": 0,
        "signals": [], "confidence": "low",
        "acpl_median": 0, "acpl_std": 0, "acpl_min": 0, "acpl_max": 0,
        "acpl_p25": 0, "acpl_p75": 0, "robust_acpl": 0,
        "top2_match_rate": 0, "top3_match_rate": 0,
        "rank_0_pct": 0, "rank_1_pct": 0, "rank_2_pct": 0, "rank_3plus_pct": 0,
        "phase_acpl_opening": 0, "phase_acpl_middle": 0, "phase_acpl_endgame": 0,
        "opening_to_middle_transition": 0, "middle_to_endgame_transition": 0,
        "collapse_rate": 0,
        "psychological_profile": "NORMAL_HUMAN",
        "tilt_rate": 0, "recovery_rate": 0, "pressure_degradation": 0, "closing_acpl": 0,
        "time_complexity_correlation": 0, "anomaly_score": 0,
        "precision_burst_mean": 0, "longest_burst_mean": 0, "precision_rate": 0,
        "opening_to_middle_improvement": 0, "variance_drop": 0, "post_pause_improvement": 0,
        "blunder_rate_std": 0, "move_count_median": 0,
        "acpl_timeline": [], "match_rate_timeline": [],
        "move_count_mean": 0, "first_game_date": "", "last_game_date": "",
    }
    try:
        from repositories import AnalysisRepository
        repo = AnalysisRepository(session)
        analyses = repo.get_by_username(username)

        if not analyses:
            return empty

        # Compute basic stats from individual analyses
        acpls = [a.acpl for a in analyses if a.acpl is not None]
        top1s = [a.top1_match_rate for a in analyses if a.top1_match_rate is not None]
        blunders = [a.blunder_rate for a in analyses if a.blunder_rate is not None]

        acpl_mean = sum(acpls) / len(acpls) if acpls else 0
        top1_mean = sum(top1s) / len(top1s) if top1s else 0
        blunder_mean = sum(blunders) / len(blunders) if blunders else 0

        result = dict(empty)
        result.update({
            "acpl_mean": round(acpl_mean, 2),
            "top1_match_rate": round(top1_mean * 100, 1),
            "games_count": len(analyses),
            "blunder_rate": round(blunder_mean * 100, 1),
            "risk_level": "LOW",
        })
        return result
    except Exception:
        return empty


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

    # check subcommand
    check_parser = subparsers.add_parser("check", help="Check if a player exists")
    check_parser.add_argument("--username", required=True, help="Chess.com username")

    # analyze subcommand
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a chess player")
    analyze_parser.add_argument("--username", required=True, help="Chess.com username")
    analyze_parser.add_argument("--games", type=int, default=50, help="Number of games")
    analyze_parser.add_argument("--depth", type=int, default=12, help="Stockfish depth")
    analyze_parser.add_argument("--workers", type=int, default=4, help="Parallel workers")
    analyze_parser.add_argument("--stockfish", default=default_sf, help="Stockfish path")

    args = parser.parse_args()

    if args.command == "check":
        check(args)
    elif args.command == "analyze":
        analyze(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
