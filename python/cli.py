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
        emit({"type": "status", "message": f"Fetching games for {args.username}..."})

        from services.analysis_service import AnalysisService

        service = AnalysisService(
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

        emit({
            "type": "status",
            "message": f"Pipeline: {stats.get('new_analyses', 0)} analyzed, "
                       f"{stats.get('failed_analyses', 0)} failed"
        })

        # Build result from saved JSON
        result = _build_result(args.username)
        emit(result)

    except Exception as e:
        emit({"type": "error", "message": f"{e}\n{traceback.format_exc()}"})
        sys.exit(1)


def _build_result(username: str) -> dict:
    """Build result dict from stored player JSON."""
    from storage import load_player

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

    data = load_player(username)
    if not data:
        return empty

    aggregates = data.get("aggregates", {})
    agg = aggregates.get("All")
    if not agg:
        return empty

    # Helper to safely get from agg dict
    def g(key, default=None):
        v = agg.get(key)
        return v if v is not None else default

    suspicion_score = g("suspicion_score", 0)

    # Recompute suspicion signals
    signals = []
    confidence = "low"
    try:
        from analysis.suspicion import calculate_suspicion_score
        susp = calculate_suspicion_score(
            anomaly_score_mean=g("anomaly_score_mean"),
            opening_to_middle_transition=g("opening_to_middle_transition"),
            collapse_rate=g("collapse_rate"),
            phase_consistency_middle=g("phase_consistency_middle"),
            robust_acpl=g("robust_acpl"),
            match_rate_mean=g("top5_match_rate_mean"),
            blunder_rate=g("blunder_rate_mean"),
            top2_match_rate=g("top2_match_rate_mean"),
            pressure_degradation=g("pressure_degradation"),
            tilt_rate=g("tilt_rate"),
            opening_to_middle_improvement=g("opening_to_middle_improvement"),
            variance_drop=g("variance_drop"),
            post_pause_improvement=g("post_pause_improvement"),
            cwmr_delta=g("cwmr_delta_mean"),
            cpa=g("cpa_mean"),
            sensitivity=g("sensitivity_mean"),
            ubma=g("ubma_mean"),
            difficulty_variance_ratio=g("variance_ratio_mean"),
            critical_accuracy_boost=g("critical_accuracy_boost_mean"),
            oscillation_score=g("oscillation_score_mean"),
            mismatch_rate=g("mismatch_rate_mean"),
            effort_ratio=g("effort_ratio_mean"),
        )
        signals = susp.get("signals", [])
        confidence = susp.get("confidence", "low")
    except Exception:
        pass

    # Derive psychological profile
    psych_profile = _derive_psychological_profile(agg)

    # Historical timelines
    acpl_timeline = g("acpl_timeline", [])
    match_rate_timeline = g("match_rate_timeline", [])

    # Date range from historical data
    first_date = ""
    last_date = ""
    if acpl_timeline:
        first_date = acpl_timeline[0].get("game_date", "") if acpl_timeline else ""
        last_date = acpl_timeline[-1].get("game_date", "") if acpl_timeline else ""

    return {
        "type": "result",
        "username": username,

        # Core
        "suspicion_score": suspicion_score,
        "risk_level": _risk_level(suspicion_score),
        "acpl_mean": round(g("acpl_mean", 0), 2),
        "top1_match_rate": round(g("top1_match_rate_mean", 0) * 100, 1),
        "games_count": g("games_count", 0),
        "blunder_rate": round(g("blunder_rate_mean", 0) * 100, 1),

        # Signals
        "signals": signals,
        "confidence": confidence,

        # ACPL statistics
        "acpl_median": round(g("acpl_median", 0), 2),
        "acpl_std": round(g("acpl_std", 0), 2),
        "acpl_min": round(g("acpl_min", 0), 2),
        "acpl_max": round(g("acpl_max", 0), 2),
        "acpl_p25": round(g("acpl_p25", 0), 2),
        "acpl_p75": round(g("acpl_p75", 0), 2),
        "robust_acpl": round(g("robust_acpl", 0), 2),

        # Match rates
        "top2_match_rate": round(g("top2_match_rate_mean", 0) * 100, 1),
        "top3_match_rate": round(g("top3_match_rate_mean", 0) * 100, 1),

        # Rank distribution
        "rank_0_pct": round(g("rank_0_mean", 0) * 100, 1),
        "rank_1_pct": round(g("rank_1_mean", 0) * 100, 1),
        "rank_2_pct": round(g("rank_2_mean", 0) * 100, 1),
        "rank_3plus_pct": round(g("rank_3plus_mean", 0) * 100, 1),

        # Phases
        "phase_acpl_opening": round(g("phase_consistency_opening", 0), 1),
        "phase_acpl_middle": round(g("phase_consistency_middle", 0), 1),
        "phase_acpl_endgame": round(g("phase_consistency_endgame", 0), 1),
        "opening_to_middle_transition": round(g("opening_to_middle_transition", 0), 1),
        "middle_to_endgame_transition": round(g("middle_to_endgame_transition", 0), 1),
        "collapse_rate": round(g("collapse_rate", 0) * 100, 1),

        # Psychological
        "psychological_profile": psych_profile,
        "tilt_rate": round(g("tilt_rate", 0), 2),
        "recovery_rate": round(g("recovery_rate", 0), 1),
        "pressure_degradation": round(g("pressure_degradation", 0), 1),
        "closing_acpl": round(g("closing_acpl", 0), 2),

        # Temporal
        "time_complexity_correlation": round(g("time_complexity_correlation", 0), 3),
        "anomaly_score": round(g("anomaly_score_mean", 0), 1),

        # Precision bursts
        "precision_burst_mean": round(g("precision_burst_mean", 0), 2),
        "longest_burst_mean": round(g("longest_burst_mean", 0), 1),
        "precision_rate": round(g("precision_rate_mean", 0) * 100, 1),

        # Phase 1B
        "opening_to_middle_improvement": round(g("opening_to_middle_improvement", 0), 1),
        "variance_drop": round(g("variance_drop", 0), 2),
        "post_pause_improvement": round(g("post_pause_improvement", 0), 1),

        # Additional stats
        "blunder_rate_std": round(g("blunder_rate_std", 0), 3),
        "move_count_median": round(g("move_count_median", 0), 1),

        # Historical timelines
        "acpl_timeline": acpl_timeline,
        "match_rate_timeline": match_rate_timeline,

        # Meta
        "move_count_mean": round(g("move_count_mean", 0), 1),
        "first_game_date": first_date,
        "last_game_date": last_date,
    }


def _derive_psychological_profile(agg) -> str:
    """Derive psychological profile label from aggregate fields."""
    def g(key, default=0):
        if isinstance(agg, dict):
            v = agg.get(key)
            return v if v is not None else default
        v = getattr(agg, key, None)
        return v if v is not None else default

    recovery = g("recovery_rate")
    closing = g("closing_acpl")
    pressure = g("pressure_degradation")
    tilt = g("tilt_rate")

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


def _risk_level(score: float) -> str:
    """Convert suspicion score to risk level string."""
    if score >= 180:
        return "VERY HIGH"
    elif score >= 130:
        return "HIGH"
    elif score >= 80:
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
