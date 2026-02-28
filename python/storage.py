"""
JSON file persistence for player data.

Stores one JSON file per player at data/players/{username}.json.
"""

import json
import types
from datetime import datetime
from pathlib import Path


def _data_dir() -> Path:
    """Return (and create) the data/players directory."""
    d = Path(__file__).parent.parent / "data" / "players"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _player_path(username: str) -> Path:
    return _data_dir() / f"{username.lower()}.json"


def _parse_date(val) -> datetime | None:
    """Convert an ISO string or datetime to datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def load_player(username: str) -> dict | None:
    """Load player data from JSON file, or None if not found."""
    path = _player_path(username)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_player(data: dict) -> Path:
    """Save player data dict to JSON file. Returns the path written."""
    username = data["username"]
    path = _player_path(username)

    def _default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=_default)
    return path


def build_calculator_items(games: list[dict], username: str) -> list[dict]:
    """
    Wrap game dicts into the {analysis: ns, game: ns} format that calculators expect.

    Calculators access fields via attribute access (.acpl, .date, etc.).
    We use SimpleNamespace to provide that interface over plain dicts.
    """
    items = []
    for g in games:
        analysis_data = g.get("analysis")
        if not analysis_data:
            continue

        # Build analysis namespace
        analysis_ns = types.SimpleNamespace(
            acpl=analysis_data.get("acpl"),
            move_count=analysis_data.get("move_count", 0),
            top1_match_rate=analysis_data.get("top1_match_rate"),
            top2_match_rate=analysis_data.get("top2_match_rate"),
            top3_match_rate=analysis_data.get("top3_match_rate"),
            top4_match_rate=analysis_data.get("top4_match_rate"),
            top5_match_rate=analysis_data.get("top5_match_rate"),
            blunder_count=analysis_data.get("blunder_count", 0),
            blunder_rate=analysis_data.get("blunder_rate", 0.0),
            move_evals=analysis_data.get("move_evals"),
            phase_breakdown=analysis_data.get("phase_breakdown"),
            precision_bursts=analysis_data.get("precision_bursts"),
            time_complexity=analysis_data.get("time_complexity"),
            enhanced_phase=analysis_data.get("enhanced_phase"),
            psychological_momentum=analysis_data.get("psychological_momentum"),
            difficulty_metrics=analysis_data.get("difficulty_metrics"),
            stockfish_depth=analysis_data.get("stockfish_depth"),
        )

        # Build game namespace
        game_ns = types.SimpleNamespace(
            id=g.get("url", "unknown"),
            url=g.get("url"),
            pgn=g.get("pgn", ""),
            date=_parse_date(g.get("date")),
            username=username,
            white_username=g.get("white_username", ""),
            black_username=g.get("black_username", ""),
            white_elo=g.get("white_elo"),
            black_elo=g.get("black_elo"),
            result=g.get("result"),
            time_control_category=g.get("time_control_category", "Unknown"),
            move_times=g.get("move_times"),
            clock_times=g.get("clock_times"),
        )

        items.append({"analysis": analysis_ns, "game": game_ns})
    return items


def categorize_time_control(seconds: int | None) -> str:
    """Categorize time control into Bullet/Blitz/Rapid."""
    if seconds is None:
        return "Unknown"
    if seconds < 180:
        return "Bullet"
    elif seconds <= 600:
        return "Blitz"
    else:
        return "Rapid"
