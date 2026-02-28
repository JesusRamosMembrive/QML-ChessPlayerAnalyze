"""
Database models and connection for Chess Player Analyzer V2.

Simple schema: 3 tables
- Game: Raw game data (PGN, metadata)
- GameAnalysis: Stockfish analysis results
- PlayerAggregate: Cached aggregate statistics
"""

from datetime import datetime
from pathlib import Path

from sqlmodel import JSON, Column, Field, Session, SQLModel, create_engine, select

# ============================================================================
# TABLE 1: Game (Raw Data)
# ============================================================================


class Game(SQLModel, table=True):
    """Raw game data from Chess.com API."""

    id: int | None = Field(default=None, primary_key=True)

    # Identifiers
    username: str = Field(index=True)  # Player being analyzed
    url: str | None = Field(default=None, unique=True, index=True)  # Chess.com game URL (unique)

    # Game metadata
    pgn: str  # Full PGN text
    date: datetime = Field(index=True)

    # Players & ratings
    white_username: str
    black_username: str
    white_elo: int | None = None
    black_elo: int | None = None

    # Time control
    time_control_seconds: int | None = None  # e.g., 300 for 5min
    time_control_category: str | None = None  # Bullet/Blitz/Rapid

    # Opening
    eco_code: str | None = None  # e.g., "C50"
    opening_name: str | None = None  # e.g., "Italian Game"

    # Result
    result: str | None = None  # "1-0", "0-1", "1/2-1/2"

    # Move times (JSON array)
    move_times: str | None = Field(default=None, sa_column=Column(JSON))

    # Clock times - remaining time on clock after each move (JSON array)
    # Used for accurate time pressure detection (Signal 9, 16)
    clock_times: str | None = Field(default=None, sa_column=Column(JSON))

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# TABLE 2: GameAnalysis (Stockfish Results)
# ============================================================================


class GameAnalysis(SQLModel, table=True):
    """Analysis results from Stockfish for a single game."""

    id: int | None = Field(default=None, primary_key=True)

    # Foreign key
    game_id: int = Field(foreign_key="game.id", index=True)

    # Redundant for fast queries (denormalized)
    username: str = Field(index=True)

    # Basic metrics
    acpl: float  # Average centipawn loss
    move_count: int

    # Top-N match rates (percentage of moves in top N engine choices)
    top1_match_rate: float  # Exact match with best move
    top2_match_rate: float  # Move in top 2 choices (Chess.com alignment)
    top3_match_rate: float  # Move in top 3 choices
    top4_match_rate: float  # Move in top 4 choices
    top5_match_rate: float  # Move in top 5 choices

    # Blunder metrics
    blunder_count: int = Field(default=0)  # Moves with loss >100cp
    blunder_rate: float = Field(default=0.0)  # blunder_count / move_count

    # Detailed move evaluations (JSON array)
    move_evals: str = Field(sa_column=Column(JSON))
    # Structure: [{"move_number": 1, "played": "e4", "best": "e4", "cp_loss": 0, ...}, ...]

    # Phase breakdown (JSON object) - Phase 3A
    phase_breakdown: str | None = Field(default=None, sa_column=Column(JSON))
    # Structure: {
    #   "opening": {"move_count": 15, "acpl": 25.5, "blunder_count": 1, "blunder_rate": 0.067},
    #   "middlegame": {...},
    #   "endgame": {...}
    # }

    # Time pressure analysis (JSON object) - Phase 3C
    time_analysis: str | None = Field(default=None, sa_column=Column(JSON))
    # Structure: {
    #   "mean_move_time": 15.5,
    #   "time_std": 12.3,
    #   "fast_moves": 5,
    #   "slow_moves": 3,
    #   "endgame_time_pressure": true,
    #   "clutch_acpl": 45.2,
    #   "regular_acpl": 38.5,
    #   "time_trouble_detected": true
    # }

    # Tier 2 Metrics (Phase 4)
    precision_bursts: str | None = Field(default=None, sa_column=Column(JSON))
    # Structure: {
    #   "burst_count": 2,
    #   "longest_burst": 5,
    #   "total_precise_moves": 15,
    #   "precision_rate": 0.35
    # }

    time_complexity: str | None = Field(default=None, sa_column=Column(JSON))
    # Structure: {
    #   "correlation": 0.7,
    #   "avg_time_simple": 5.2,
    #   "avg_time_medium": 12.5,
    #   "avg_time_complex": 25.8,
    #   "anomaly_score": 0
    # }

    # Enhanced Phase Analysis (Phase 4 Extension)
    enhanced_phase: str | None = Field(default=None, sa_column=Column(JSON))
    # Structure: {
    #   "phase_transitions": {"opening_to_middle": 25.5, "middle_to_endgame": 45.2},
    #   "collapse_detected": true,
    #   "collapse_location": "opening_to_middle",
    #   "phase_consistency": {"opening": 85.3, "middlegame": 72.1, "endgame": 65.8},
    #   "worst_phase": "endgame",
    #   "best_phase": "opening"
    # }

    # Psychological Momentum Analysis (Phase 5A)
    psychological_momentum: str | None = Field(default=None, sa_column=Column(JSON))
    # Structure: {
    #   "tilt_episodes": 0,
    #   "recovery_count": 2,
    #   "recovery_rate": 75.0,
    #   "closing_acpl": 42.5,
    #   "pressure_acpl": 65.3,
    #   "pressure_degradation": 15.2,
    #   "psychological_profile": "RESILIENT_CLOSER"
    # }

    # Difficulty Metrics (Position Difficulty & Advanced Cheat Detection)
    difficulty_metrics: str | None = Field(default=None, sa_column=Column(JSON))
    # Structure: {
    #   "avg_sharpness": 42.5,
    #   "cwmr": 0.35, "cwmr_delta": 0.12,
    #   "cpa": 0.25, "critical_positions": 8,
    #   "sensitivity": 0.22, "ubma": 0.40, "unique_positions": 5,
    #   "variance_ratio": 1.1, "critical_accuracy_boost": -0.05,
    #   "oscillation_score": 12.3,
    #   "mismatch_rate": 0.08, "effort_ratio": 1.3
    # }

    # Analysis metadata
    stockfish_depth: int = Field(default=12)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# TABLE 3: PlayerAggregate (Cached Statistics)
# ============================================================================


class PlayerAggregate(SQLModel, table=True):
    """Aggregate statistics per player and time control."""

    # Composite primary key
    username: str = Field(primary_key=True)
    time_control_category: str = Field(primary_key=True)  # "Bullet", "Blitz", "Rapid", "All"
    window_id: int = Field(primary_key=True, default=0)  # 0 = full analysis, 1+ = window analysis

    # Window metadata (only for window analyses, window_id > 0)
    window_start_game: int | None = None  # Start game index in player's history
    window_end_game: int | None = None  # End game index in player's history
    window_detection_method: str | None = None  # "elo_slope", "win_streaks", "performance_bursts"

    # Volume
    games_count: int = Field(default=0)

    # ACPL statistics
    acpl_mean: float
    acpl_median: float
    acpl_std: float
    acpl_min: float
    acpl_max: float
    acpl_p25: float | None = None  # 25th percentile
    acpl_p75: float | None = None  # 75th percentile

    # Top-N match rate statistics (alignment with Chess.com)
    top1_match_rate_mean: float  # Exact engine match
    top1_match_rate_std: float
    top1_match_rate_min: float
    top1_match_rate_max: float
    top2_match_rate_mean: float  # Top 2 choices (Chess.com alignment)
    top2_match_rate_std: float
    top2_match_rate_min: float
    top2_match_rate_max: float
    top3_match_rate_mean: float  # Top 3 choices
    top3_match_rate_std: float
    top3_match_rate_min: float
    top3_match_rate_max: float
    top4_match_rate_mean: float | None = None  # Top 4 choices
    top4_match_rate_std: float | None = None
    top4_match_rate_min: float | None = None
    top4_match_rate_max: float | None = None
    top5_match_rate_mean: float  # Top 5 choices
    top5_match_rate_std: float
    top5_match_rate_min: float
    top5_match_rate_max: float

    # Blunder statistics
    blunder_rate_mean: float
    blunder_rate_std: float

    # Move statistics
    move_count_mean: float
    move_count_median: float

    # Tier 1 Metrics (Phase 3.5)
    robust_acpl: float | None = None  # Robust ACPL (median, capped at 300)
    rank_0_mean: float | None = None  # % of moves matching best move
    rank_1_mean: float | None = None  # % of moves matching 2nd best
    rank_2_mean: float | None = None  # % of moves matching 3rd best
    rank_3plus_mean: float | None = None  # % of moves worse than 3rd best

    # Tier 2 Metrics (Phase 4)
    precision_burst_mean: float | None = None  # Average precision bursts per game
    longest_burst_mean: float | None = None  # Average longest burst length
    precision_rate_mean: float | None = None  # Average precision rate (0-1)
    time_complexity_correlation: float | None = None  # Average correlation (-1 to 1)
    anomaly_score_mean: float | None = None  # Average anomaly score (0-100)

    # Enhanced Phase Metrics (Phase 4 Extension)
    opening_to_middle_transition: float | None = None  # Average ACPL increase
    middle_to_endgame_transition: float | None = None  # Average ACPL increase
    collapse_rate: float | None = None  # % of games with collapse detected
    phase_consistency_opening: float | None = None  # Average consistency score (0-100)
    phase_consistency_middle: float | None = None  # Average consistency score (0-100)
    phase_consistency_endgame: float | None = None  # Average consistency score (0-100)

    # Composite Suspicion Score (Phase 4 Complete)
    suspicion_score: float | None = None  # Combined score 0-100 (higher = more suspicious)

    # Psychological Metrics (Phase 5A)
    tilt_rate: float | None = None  # Average tilt episodes per game
    recovery_rate: float | None = None  # Average recovery rate (0-100%)
    closing_acpl: float | None = None  # Average ACPL in closing phase (winning positions)
    pressure_degradation: float | None = None  # Average ACPL degradation under time pressure (%)

    # Phase 1B: Advanced Temporal Detection Metrics (Signal 11, 12, 13)
    opening_to_middle_improvement: float | None = None  # Average ACPL improvement opening→middle (Signal 11)
    variance_drop: float | None = None  # Average std dev drop opening→middle (Signal 12)
    post_pause_improvement: float | None = None  # Average ACPL improvement after pauses (Signal 13)

    # Difficulty Metrics (Position Difficulty & Advanced Cheat Detection)
    cwmr_mean: float | None = None  # Average CWMR (0-1)
    cwmr_delta_mean: float | None = None  # Average CWMR delta (raw - weighted)
    cpa_mean: float | None = None  # Average Critical Position Accuracy (0-1)
    sensitivity_mean: float | None = None  # Average Difficulty Sensitivity
    ubma_mean: float | None = None  # Average Unique Best Move Accuracy (0-1)
    variance_ratio_mean: float | None = None  # Average variance ratio (easy/hard)
    critical_accuracy_boost_mean: float | None = None  # Average critical moment accuracy boost
    oscillation_score_mean: float | None = None  # Average oscillation pattern score
    mismatch_rate_mean: float | None = None  # Average effort-quality mismatch rate
    effort_ratio_mean: float | None = None  # Average effort ratio (time on correct hard / avg)
    avg_sharpness_mean: float | None = None  # Average position sharpness across games

    # Phase 1C: Temporal Window Analysis (Signals 14, 15)
    window_analysis: str | None = Field(default=None, sa_column=Column(JSON))
    # Structure: {
    #   "elo_slope": {
    #     "max_slope": 22.6,
    #     "max_slope_window": [131, 150],
    #     "suspicious_windows": [[131, 150]],
    #     "total_windows_scanned": 7
    #   },
    #   "win_streaks": {
    #     "max_win_rate": 1.0,
    #     "max_win_rate_window": [131, 150],
    #     "suspicious_windows": [[131, 150]]
    #   },
    #   "performance_bursts": {
    #     "max_signals": 4,
    #     "strongest_burst_window": [131, 150],
    #     "suspicious_windows": [[131, 150]]
    #   },
    #   "games_filtered": 130,  # Games NOT analyzed (filtered out)
    #   "games_analyzed": 20    # Games analyzed with Stockfish
    # }

    # Historical Timeline Data (Phase 3 - Frontend Charts)
    historical_data: str | None = Field(default=None, sa_column=Column(JSON))
    # Structure: {
    #   "acpl_timeline": [{"game_date": "2025-08-15", "acpl": 45.2, "game_url": "..."}],
    #   "match_rate_timeline": [{"game_date": "2025-08-15", "top1": 35.5, "top3": 62.1, "game_url": "..."}],
    #   "games_count": 50
    # }

    # Date range
    first_game_date: datetime
    last_game_date: datetime

    # Metadata
    last_updated: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Database Connection
# ============================================================================


def get_database_path() -> Path:
    """Get the path to the SQLite database file."""
    db_dir = Path(__file__).parent.parent / "data"
    db_dir.mkdir(exist_ok=True)
    return db_dir / "chess_analyzer.db"


def get_engine():
    """Create and return the database engine."""
    db_path = get_database_path()
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url, echo=False)
    return engine


def migrate_database(engine):
    """
    Migrate existing database by adding missing columns.

    Uses PRAGMA table_info to detect missing columns and ALTER TABLE ADD COLUMN
    to add them. Safe to call multiple times (idempotent).
    """
    import sqlite3

    db_path = get_database_path()
    if not db_path.exists():
        return  # No database to migrate

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()

        # Define expected columns per table: (column_name, sql_type, default)
        migrations = {
            "gameanalysis": [
                ("difficulty_metrics", "TEXT", None),
            ],
            "playeraggregate": [
                ("cwmr_mean", "FLOAT", None),
                ("cwmr_delta_mean", "FLOAT", None),
                ("cpa_mean", "FLOAT", None),
                ("sensitivity_mean", "FLOAT", None),
                ("ubma_mean", "FLOAT", None),
                ("variance_ratio_mean", "FLOAT", None),
                ("critical_accuracy_boost_mean", "FLOAT", None),
                ("oscillation_score_mean", "FLOAT", None),
                ("mismatch_rate_mean", "FLOAT", None),
                ("effort_ratio_mean", "FLOAT", None),
                ("avg_sharpness_mean", "FLOAT", None),
            ],
        }

        for table, columns in migrations.items():
            # Get existing columns
            cursor.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cursor.fetchall()}

            if not existing:
                continue  # Table doesn't exist yet, create_all will handle it

            for col_name, col_type, default in columns:
                if col_name not in existing:
                    default_clause = f" DEFAULT {default}" if default is not None else ""
                    sql = f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}{default_clause}"
                    cursor.execute(sql)
                    print(f"  Migration: added {table}.{col_name} ({col_type})")

        conn.commit()
    finally:
        conn.close()


def create_tables():
    """Create all tables in the database."""
    engine = get_engine()
    migrate_database(engine)
    SQLModel.metadata.create_all(engine)
    return engine


def get_session() -> Session:
    """Get a database session."""
    engine = get_engine()
    return Session(engine)


# ============================================================================
# Helper Functions
# ============================================================================


def categorize_time_control(seconds: int | None) -> str:
    """Categorize time control into Bullet/Blitz/Rapid."""
    if seconds is None:
        return "Unknown"

    if seconds < 180:  # <3 minutes
        return "Bullet"
    elif seconds <= 600:  # 3-10 minutes
        return "Blitz"
    else:  # >10 minutes
        return "Rapid"


def game_exists(
    session: Session,
    url: str | None = None,
    username: str | None = None,
    date: datetime | None = None,
    white: str | None = None,
    black: str | None = None,
) -> Game | None:
    """
    Check if a game already exists in the database.

    Tries to find by URL first (if available), then by combination of other fields.

    Args:
        session: Database session
        url: Game URL (most reliable identifier)
        username: Player username
        date: Game date
        white: White player username
        black: Black player username

    Returns:
        Game object if found, None otherwise
    """
    # Try by URL first (most reliable)
    if url:
        statement = select(Game).where(Game.url == url)
        existing = session.exec(statement).first()
        if existing:
            return existing

    # Fallback: try by username + date + players
    if username and date and white and black:
        statement = select(Game).where(
            Game.username == username,
            Game.date == date,
            Game.white_username == white,
            Game.black_username == black,
        )
        return session.exec(statement).first()

    return None


def analysis_exists(session: Session, game_id: int) -> GameAnalysis | None:
    """
    Check if analysis already exists for a game.

    Args:
        session: Database session
        game_id: Game ID

    Returns:
        GameAnalysis object if found, None otherwise
    """
    statement = select(GameAnalysis).where(GameAnalysis.game_id == game_id)
    return session.exec(statement).first()


def save_game(session: Session, game_data: dict, skip_if_exists: bool = True) -> tuple[Game, bool]:
    """
    Save a game to the database.

    Args:
        session: Database session
        game_data: Dict with game information
        skip_if_exists: If True, return existing game instead of creating duplicate

    Returns:
        Tuple of (Game object, was_created: bool)
        was_created is True if new game was created, False if existing game returned
    """
    # Check if game already exists
    if skip_if_exists:
        existing = game_exists(
            session,
            url=game_data.get("url"),
            username=game_data["username"],
            date=game_data["date"],
            white=game_data.get("white_username"),
            black=game_data.get("black_username"),
        )

        if existing:
            return existing, False

    # Create new game
    game = Game(
        username=game_data["username"],
        url=game_data.get("url"),
        pgn=game_data["pgn"],
        date=game_data["date"],
        white_username=game_data.get("white_username", ""),
        black_username=game_data.get("black_username", ""),
        white_elo=game_data.get("white_elo"),
        black_elo=game_data.get("black_elo"),
        time_control_seconds=game_data.get("time_control_seconds"),
        time_control_category=categorize_time_control(game_data.get("time_control_seconds")),
        eco_code=game_data.get("eco_code"),
        opening_name=game_data.get("opening_name"),
        result=game_data.get("result"),
        move_times=game_data.get("move_times"),
    )

    session.add(game)
    session.commit()
    session.refresh(game)

    return game, True


# LEGACY FUNCTION REMOVED: save_game_analysis()
# Use AnalysisRepository.create() instead with top1/2/3_match_rate fields


def get_player_games(
    session: Session, username: str, time_control: str | None = None
) -> list[Game]:
    """
    Get all games for a player.

    Args:
        session: Database session
        username: Player username
        time_control: Optional filter by time control category

    Returns:
        List of Game objects
    """
    statement = select(Game).where(Game.username == username)

    if time_control:
        statement = statement.where(Game.time_control_category == time_control)

    statement = statement.order_by(Game.date)

    return session.exec(statement).all()


def get_player_analyses(session: Session, username: str) -> list[GameAnalysis]:
    """
    Get all analyses for a player.

    Args:
        session: Database session
        username: Player username

    Returns:
        List of GameAnalysis objects
    """
    statement = select(GameAnalysis).where(GameAnalysis.username == username)
    return session.exec(statement).all()


def get_player_aggregate(
    session: Session, username: str, time_control: str = "All", window_id: int = 0
) -> PlayerAggregate | None:
    """
    Get aggregate statistics for a player.

    Args:
        session: Database session
        username: Player username
        time_control: Time control category
        window_id: Window ID (0 = full analysis, 1+ = window analysis)

    Returns:
        PlayerAggregate object or None
    """
    statement = select(PlayerAggregate).where(
        PlayerAggregate.username == username,
        PlayerAggregate.time_control_category == time_control,
        PlayerAggregate.window_id == window_id,
    )
    return session.exec(statement).first()


def get_all_player_aggregates(
    session: Session, username: str, time_control: str = "All"
) -> list[PlayerAggregate]:
    """
    Get all aggregate statistics for a player (all windows).

    Args:
        session: Database session
        username: Player username
        time_control: Time control category

    Returns:
        List of PlayerAggregate objects
    """
    statement = (
        select(PlayerAggregate)
        .where(
            PlayerAggregate.username == username,
            PlayerAggregate.time_control_category == time_control,
        )
        .order_by(PlayerAggregate.window_id)
    )
    return list(session.exec(statement).all())


# ============================================================================
# Initialization
# ============================================================================

if __name__ == "__main__":
    """Initialize database and create tables."""
    print("Creating database tables...")
    engine = create_tables()
    db_path = get_database_path()
    print(f"✅ Database initialized at: {db_path}")
    print("   Tables created: Game, GameAnalysis, PlayerAggregate")
