"""
GameRepository - Data access layer for Game model.

Centralizes all database operations for the Game table.
"""

from sqlmodel import Session, func, select

from database import Game


class GameRepository:
    """
    Repository for Game database operations.

    Provides CRUD operations and domain-specific queries for Game entities.
    All database interactions for Game should go through this repository.
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

    def create(self, game: Game) -> Game:
        """
        Create a new game in the database.

        Args:
            game: Game object to create

        Returns:
            Created game with ID assigned
        """
        self.session.add(game)
        self.session.commit()
        self.session.refresh(game)
        return game

    def get_by_id(self, game_id: int) -> Game | None:
        """
        Get game by ID.

        Args:
            game_id: Game primary key

        Returns:
            Game if found, None otherwise
        """
        return self.session.get(Game, game_id)

    def get_all(self, limit: int | None = None) -> list[Game]:
        """
        Get all games.

        Args:
            limit: Optional limit on number of results

        Returns:
            List of all games (or up to limit)
        """
        statement = select(Game)
        if limit:
            statement = statement.limit(limit)
        return list(self.session.exec(statement).all())

    def update(self, game: Game) -> Game:
        """
        Update existing game.

        Args:
            game: Game object with updated fields

        Returns:
            Updated game
        """
        self.session.add(game)
        self.session.commit()
        self.session.refresh(game)
        return game

    def delete(self, game: Game) -> bool:
        """
        Delete a game.

        Args:
            game: Game object to delete

        Returns:
            True if deleted successfully
        """
        self.session.delete(game)
        self.session.commit()
        return True

    def delete_by_id(self, game_id: int) -> bool:
        """
        Delete game by ID.

        Args:
            game_id: Game primary key

        Returns:
            True if deleted, False if not found
        """
        game = self.get_by_id(game_id)
        if game:
            return self.delete(game)
        return False

    # ============================================================
    # DOMAIN-SPECIFIC QUERIES
    # ============================================================

    def get_by_url(self, url: str) -> Game | None:
        """
        Find game by Chess.com URL.

        Used for duplicate detection when fetching games.

        Args:
            url: Chess.com game URL

        Returns:
            Game if found, None otherwise
        """
        statement = select(Game).where(Game.url == url)
        return self.session.exec(statement).first()

    def exists(self, url: str) -> bool:
        """
        Check if game exists by URL.

        Args:
            url: Chess.com game URL

        Returns:
            True if game exists, False otherwise
        """
        return self.get_by_url(url) is not None

    def find_duplicate(
        self,
        url: str | None = None,
        username: str | None = None,
        date=None,
        white: str | None = None,
        black: str | None = None,
    ) -> Game | None:
        """
        Find duplicate game using multiple strategies.

        Tries to find by URL first (most reliable), then by combination of
        username, date, and player names.

        Args:
            url: Chess.com game URL
            username: Player username
            date: Game date
            white: White player username
            black: Black player username

        Returns:
            Game if found, None otherwise
        """
        # Try by URL first (most reliable)
        if url:
            existing = self.get_by_url(url)
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
            return self.session.exec(statement).first()

        return None

    def get_by_username(self, username: str) -> list[Game]:
        """
        Get all games where player is the primary username.

        This returns games where the username field matches.
        For games where player is white or black, use get_by_username_any_side().

        Args:
            username: Player username

        Returns:
            List of games for this player
        """
        statement = select(Game).where(Game.username == username)
        return list(self.session.exec(statement).all())

    def get_by_username_any_side(self, username: str) -> list[Game]:
        """
        Get all games where player is either white, black, or primary username.

        Used when deleting all player data.

        Args:
            username: Player username

        Returns:
            List of games where player participated
        """
        statement = select(Game).where(
            (Game.username == username)
            | (Game.white_username == username)
            | (Game.black_username == username)
        )
        return list(self.session.exec(statement).all())

    def count_by_username(self, username: str) -> int:
        """
        Count games for a player.

        Args:
            username: Player username

        Returns:
            Number of games for this player
        """
        statement = select(func.count(Game.id)).where(Game.username == username)
        return self.session.exec(statement).first() or 0

    def get_for_window_analysis(self, username: str) -> list[Game]:
        """
        Get games for lightweight window analysis (no Stockfish data needed).

        Only loads fields required for temporal window detection:
        - date, white_elo, black_elo, result, white_username, black_username

        This query is optimized for Phase 1 (window pre-screening) and does NOT
        load heavy fields like pgn_text, move_evals, or clock_times.

        Args:
            username: Player username

        Returns:
            List of games ordered by date (oldest to newest)
            NOTE: Analysis uses the LAST N games from this list (most recent)
        """
        statement = (
            select(Game)
            .where(Game.username == username)
            .order_by(Game.date.asc())  # Explicit ASC for clarity
            # SQLite doesn't support load_only well, but we keep minimal data structure
            # by not joining with GameAnalysis
        )
        return list(self.session.exec(statement).all())

    def get_distinct_usernames(self) -> list[str]:
        """
        Get list of all unique usernames in the database.

        Used for listing players.

        Returns:
            List of unique usernames
        """
        statement = select(func.distinct(Game.username))
        return list(self.session.exec(statement).all())

    def get_usernames_with_game_count(self) -> list[tuple[str, int]]:
        """
        Get all usernames with their game counts.

        Used for player overview pages.

        Returns:
            List of (username, game_count) tuples
        """
        statement = select(Game.username, func.count(Game.id)).group_by(Game.username)
        return list(self.session.exec(statement).all())

    def batch_create(self, games: list[Game]) -> list[Game]:
        """
        Create multiple games in a single transaction.

        More efficient than creating one by one.

        Args:
            games: List of Game objects to create

        Returns:
            List of created games with IDs assigned
        """
        for game in games:
            self.session.add(game)
        self.session.commit()

        for game in games:
            self.session.refresh(game)

        return games

    def delete_all_by_username(self, username: str) -> int:
        """
        Delete all games for a player.

        Used when removing player data.

        Args:
            username: Player username (must be lowercase)

        Returns:
            Number of games deleted
        """
        # Exact match for games
        statement = select(Game).where(
            (Game.username == username)
            | (Game.white_username == username)
            | (Game.black_username == username)
        )
        games = list(self.session.exec(statement).all())
        count = len(games)

        for game in games:
            self.session.delete(game)

        self.session.commit()
        return count
