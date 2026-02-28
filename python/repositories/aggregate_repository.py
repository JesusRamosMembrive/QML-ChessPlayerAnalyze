"""
AggregateRepository - Data access layer for PlayerAggregate model.

Centralizes all database operations for the PlayerAggregate table.
"""

from sqlmodel import Session, delete, func, select

from database import PlayerAggregate


class AggregateRepository:
    """
    Repository for PlayerAggregate database operations.

    Provides CRUD operations and domain-specific queries for PlayerAggregate entities.
    All database interactions for PlayerAggregate should go through this repository.
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

    def create(self, aggregate: PlayerAggregate) -> PlayerAggregate:
        """
        Create a new player aggregate in the database.

        Args:
            aggregate: PlayerAggregate object to create

        Returns:
            Created aggregate with ID assigned
        """
        self.session.add(aggregate)
        self.session.commit()
        self.session.refresh(aggregate)
        return aggregate

    def get_by_id(self, aggregate_id: int) -> PlayerAggregate | None:
        """
        Get aggregate by ID.

        Args:
            aggregate_id: Aggregate primary key

        Returns:
            PlayerAggregate if found, None otherwise
        """
        return self.session.get(PlayerAggregate, aggregate_id)

    def get_all(self, limit: int | None = None) -> list[PlayerAggregate]:
        """
        Get all aggregates.

        Args:
            limit: Optional limit on number of results

        Returns:
            List of all aggregates (or up to limit)
        """
        statement = select(PlayerAggregate)
        if limit:
            statement = statement.limit(limit)
        return list(self.session.exec(statement).all())

    def update(self, aggregate: PlayerAggregate) -> PlayerAggregate:
        """
        Update existing aggregate.

        Args:
            aggregate: PlayerAggregate object with updated fields

        Returns:
            Updated aggregate
        """
        self.session.add(aggregate)
        self.session.commit()
        self.session.refresh(aggregate)
        return aggregate

    def delete(self, aggregate: PlayerAggregate) -> bool:
        """
        Delete an aggregate.

        Args:
            aggregate: PlayerAggregate object to delete

        Returns:
            True if deleted successfully
        """
        self.session.delete(aggregate)
        self.session.commit()
        return True

    def delete_by_id(self, aggregate_id: int) -> bool:
        """
        Delete aggregate by ID.

        Args:
            aggregate_id: Aggregate primary key

        Returns:
            True if deleted, False if not found
        """
        aggregate = self.get_by_id(aggregate_id)
        if aggregate:
            return self.delete(aggregate)
        return False

    # ============================================================
    # DOMAIN-SPECIFIC QUERIES
    # ============================================================

    def get_by_username_and_time_control(
        self, username: str, time_control: str, window_id: int = 0
    ) -> PlayerAggregate | None:
        """
        Get aggregate for specific player, time control, and window.

        This is the most common query pattern for aggregates.

        Args:
            username: Player username
            time_control: Time control category (e.g., "All", "Blitz", "Rapid")
            window_id: Window ID (0 = full analysis, 1+ = window analysis)

        Returns:
            PlayerAggregate if found, None otherwise
        """
        statement = select(PlayerAggregate).where(
            PlayerAggregate.username == username,
            PlayerAggregate.time_control_category == time_control,
            PlayerAggregate.window_id == window_id,
        )
        return self.session.exec(statement).first()

    def get_all_windows_by_username_and_time_control(
        self, username: str, time_control: str
    ) -> list[PlayerAggregate]:
        """
        Get all window analyses for a player and time control.

        Args:
            username: Player username
            time_control: Time control category

        Returns:
            List of aggregates for all windows, ordered by window_id
        """
        statement = (
            select(PlayerAggregate)
            .where(
                PlayerAggregate.username == username,
                PlayerAggregate.time_control_category == time_control,
            )
            .order_by(PlayerAggregate.window_id)
        )
        return list(self.session.exec(statement).all())

    def get_all_by_username(self, username: str) -> list[PlayerAggregate]:
        """
        Get all aggregates for a player (all time controls).

        Args:
            username: Player username

        Returns:
            List of aggregates for this player
        """
        statement = select(PlayerAggregate).where(PlayerAggregate.username == username)
        return list(self.session.exec(statement).all())

    def get_latest_by_username(self, username: str) -> PlayerAggregate | None:
        """
        Get the most recent aggregate for a player (by games_count).

        Useful as a fallback when "All" time control is not available.

        Args:
            username: Player username

        Returns:
            Most recent aggregate (highest games_count)
        """
        statement = (
            select(PlayerAggregate)
            .where(PlayerAggregate.username == username)
            .order_by(PlayerAggregate.games_count.desc())
        )
        return self.session.exec(statement).first()

    def get_all_ordered(
        self,
        order_by: str = "last_updated",
        time_control: str | None = None,
    ) -> list[PlayerAggregate]:
        """
        Get all aggregates ordered by a field.

        Used for player listings.

        Args:
            order_by: Field to order by ("last_updated", "games_count", "suspicion_score")
            time_control: Optional filter by time control

        Returns:
            List of aggregates ordered by specified field
        """
        statement = select(PlayerAggregate)

        if time_control:
            statement = statement.where(PlayerAggregate.time_control_category == time_control)

        # Order by specified field (descending)
        if order_by == "last_updated":
            statement = statement.order_by(PlayerAggregate.last_updated.desc())
        elif order_by == "games_count":
            statement = statement.order_by(PlayerAggregate.games_count.desc())
        elif order_by == "suspicion_score":
            statement = statement.order_by(PlayerAggregate.suspicion_score.desc())
        else:
            # Default: username ascending, time_control ascending
            statement = statement.order_by(
                PlayerAggregate.username,
                PlayerAggregate.time_control_category,
            )

        return list(self.session.exec(statement).all())

    def upsert(
        self, username: str, time_control: str, aggregate_data: dict, window_id: int = 0
    ) -> PlayerAggregate:
        """
        Create or update aggregate (upsert operation).

        If aggregate exists for this username+time_control+window_id, update it.
        Otherwise, create a new one.

        Args:
            username: Player username
            time_control: Time control category
            aggregate_data: Dict with aggregate fields (acpl_mean, etc.)
            window_id: Window ID (0 = full analysis, 1+ = window analysis)

        Returns:
            Created or updated aggregate
        """
        # Try to find existing
        existing = self.get_by_username_and_time_control(username, time_control, window_id)

        if existing:
            # Update existing
            for key, value in aggregate_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            return self.update(existing)
        else:
            # Create new
            aggregate = PlayerAggregate(
                username=username,
                time_control_category=time_control,
                window_id=window_id,
                **aggregate_data,
            )
            return self.create(aggregate)

    def delete_all_by_username(self, username: str) -> int:
        """
        Delete all aggregates for a player.

        Used when removing player data.

        Args:
            username: Player username (must be lowercase)

        Returns:
            Number of aggregates deleted
        """
        statement = delete(PlayerAggregate).where(PlayerAggregate.username == username)
        result = self.session.exec(statement)
        self.session.commit()
        return result.rowcount

    def count_players(self) -> int:
        """
        Count number of unique players in database.

        Returns:
            Number of distinct usernames
        """
        statement = select(func.count(func.distinct(PlayerAggregate.username)))
        return self.session.exec(statement).first() or 0

    def get_high_suspicion_players(
        self, threshold: float = 60.0, limit: int = 10
    ) -> list[PlayerAggregate]:
        """
        Get players with high suspicion scores.

        Args:
            threshold: Minimum suspicion score (default: 60.0 = VERY HIGH)
            limit: Maximum number of results (default: 10)

        Returns:
            List of high-suspicion aggregates, ordered by score descending
        """
        statement = (
            select(PlayerAggregate)
            .where(
                PlayerAggregate.suspicion_score >= threshold,
                PlayerAggregate.time_control_category == "All",  # Only "All" category
            )
            .order_by(PlayerAggregate.suspicion_score.desc())
            .limit(limit)
        )
        return list(self.session.exec(statement).all())

    def batch_create(self, aggregates: list[PlayerAggregate]) -> list[PlayerAggregate]:
        """
        Create multiple aggregates in a single transaction.

        Args:
            aggregates: List of PlayerAggregate objects to create

        Returns:
            List of created aggregates with IDs assigned
        """
        for aggregate in aggregates:
            self.session.add(aggregate)
        self.session.commit()

        for aggregate in aggregates:
            self.session.refresh(aggregate)

        return aggregates
