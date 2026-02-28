"""
AnalysisRepository - Data access layer for GameAnalysis model.

Centralizes all database operations for the GameAnalysis table.
"""

from sqlmodel import Session, delete, func, select

from database import GameAnalysis


class AnalysisRepository:
    """
    Repository for GameAnalysis database operations.

    Provides CRUD operations and domain-specific queries for GameAnalysis entities.
    All database interactions for GameAnalysis should go through this repository.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLModel database session
        """
        self.session = session

    # ============================================================
    # BASIC CRUD OPERATIONS
    # ============================================================

    def create(self, analysis: GameAnalysis) -> GameAnalysis:
        """
        Create a new game analysis in the database.

        Args:
            analysis: GameAnalysis object to create

        Returns:
            Created analysis with ID assigned
        """
        self.session.add(analysis)
        self.session.commit()
        self.session.refresh(analysis)
        return analysis

    def get_by_id(self, analysis_id: int) -> GameAnalysis | None:
        """
        Get analysis by ID.

        Args:
            analysis_id: Analysis primary key

        Returns:
            GameAnalysis if found, None otherwise
        """
        return self.session.get(GameAnalysis, analysis_id)

    def get_all(self, limit: int | None = None) -> list[GameAnalysis]:
        """
        Get all analyses.

        Args:
            limit: Optional limit on number of results

        Returns:
            List of all analyses (or up to limit)
        """
        statement = select(GameAnalysis)
        if limit:
            statement = statement.limit(limit)
        return list(self.session.exec(statement).all())

    def update(self, analysis: GameAnalysis) -> GameAnalysis:
        """
        Update existing analysis.

        Args:
            analysis: GameAnalysis object with updated fields

        Returns:
            Updated analysis
        """
        self.session.add(analysis)
        self.session.commit()
        self.session.refresh(analysis)
        return analysis

    def delete(self, analysis: GameAnalysis) -> bool:
        """
        Delete an analysis.

        Args:
            analysis: GameAnalysis object to delete

        Returns:
            True if deleted successfully
        """
        self.session.delete(analysis)
        self.session.commit()
        return True

    def delete_by_id(self, analysis_id: int) -> bool:
        """
        Delete analysis by ID.

        Args:
            analysis_id: Analysis primary key

        Returns:
            True if deleted, False if not found
        """
        analysis = self.get_by_id(analysis_id)
        if analysis:
            return self.delete(analysis)
        return False

    # ============================================================
    # DOMAIN-SPECIFIC QUERIES
    # ============================================================

    def get_by_username(self, username: str) -> list[GameAnalysis]:
        """
        Get all analyses for a player.

        Used for statistics calculation and player overview.

        Args:
            username: Player username

        Returns:
            List of analyses for this player
        """
        statement = select(GameAnalysis).where(GameAnalysis.username == username)
        return list(self.session.exec(statement).all())

    def get_by_game_id(self, game_id: int) -> GameAnalysis | None:
        """
        Get analysis for a specific game.

        Args:
            game_id: Game ID (foreign key)

        Returns:
            GameAnalysis if found, None otherwise
        """
        statement = select(GameAnalysis).where(GameAnalysis.game_id == game_id)
        return self.session.exec(statement).first()

    def exists_for_game(self, game_id: int) -> bool:
        """
        Check if analysis exists for a game.

        Used to avoid re-analyzing games.

        Args:
            game_id: Game ID

        Returns:
            True if analysis exists, False otherwise
        """
        return self.get_by_game_id(game_id) is not None

    def count_by_username(self, username: str) -> int:
        """
        Count analyses for a player.

        Args:
            username: Player username

        Returns:
            Number of analyses for this player
        """
        statement = select(func.count(GameAnalysis.id)).where(GameAnalysis.username == username)
        return self.session.exec(statement).first() or 0

    def delete_by_game_id(self, game_id: int) -> bool:
        """
        Delete analysis for a specific game.

        Used when deleting games (cascade deletion).

        Args:
            game_id: Game ID

        Returns:
            True if deleted, False if not found
        """
        statement = delete(GameAnalysis).where(GameAnalysis.game_id == game_id)
        result = self.session.exec(statement)
        self.session.commit()
        return result.rowcount > 0

    def delete_all_by_username(self, username: str) -> int:
        """
        Delete all analyses for a player.

        Used when removing player data.

        Args:
            username: Player username (must be lowercase)

        Returns:
            Number of analyses deleted
        """
        statement = delete(GameAnalysis).where(GameAnalysis.username == username)
        result = self.session.exec(statement)
        self.session.commit()
        return result.rowcount

    def batch_create(self, analyses: list[GameAnalysis]) -> list[GameAnalysis]:
        """
        Create multiple analyses in a single transaction.

        More efficient than creating one by one.
        Used after parallel game analysis.

        Args:
            analyses: List of GameAnalysis objects to create

        Returns:
            List of created analyses with IDs assigned
        """
        for analysis in analyses:
            self.session.add(analysis)
        self.session.commit()

        for analysis in analyses:
            self.session.refresh(analysis)

        return analyses

    def get_statistics_by_username(self, username: str) -> dict:
        """
        Get quick statistics for a player's analyses.

        Useful for dashboards and overviews.

        Args:
            username: Player username

        Returns:
            Dict with count, avg ACPL, avg Top-N match rates, etc.
        """
        statement = select(
            func.count(GameAnalysis.id),
            func.avg(GameAnalysis.acpl),
            func.avg(GameAnalysis.top1_match_rate),
            func.avg(GameAnalysis.top2_match_rate),
            func.avg(GameAnalysis.top3_match_rate),
            func.avg(GameAnalysis.blunder_rate),
        ).where(GameAnalysis.username == username)

        result = self.session.exec(statement).first()

        if not result or result[0] == 0:
            return {
                "count": 0,
                "avg_acpl": None,
                "avg_top1_match_rate": None,
                "avg_top2_match_rate": None,
                "avg_top3_match_rate": None,
                "avg_blunder_rate": None,
            }

        return {
            "count": result[0],
            "avg_acpl": float(result[1]) if result[1] else None,
            "avg_top1_match_rate": float(result[2]) if result[2] else None,
            "avg_top2_match_rate": float(result[3]) if result[3] else None,
            "avg_top3_match_rate": float(result[4]) if result[4] else None,
            "avg_blunder_rate": float(result[5]) if result[5] else None,
        }

    def get_latest_by_username(self, username: str, limit: int = 10) -> list[GameAnalysis]:
        """
        Get most recent analyses for a player.

        Args:
            username: Player username
            limit: Number of recent analyses to return (default: 10)

        Returns:
            List of recent analyses, newest first
        """
        statement = (
            select(GameAnalysis)
            .where(GameAnalysis.username == username)
            .order_by(GameAnalysis.analyzed_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(statement).all())
