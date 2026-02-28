"""
JobRepository - Data access layer for AnalysisJob model.

Centralizes all database operations for the AnalysisJob table.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Session, select

if TYPE_CHECKING:
    from api.models import AnalysisJob


class JobRepository:
    """
    Repository for AnalysisJob database operations.

    Provides CRUD operations and domain-specific queries for AnalysisJob entities.
    All database interactions for AnalysisJob should go through this repository.
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

    def create(self, job: "AnalysisJob") -> "AnalysisJob":
        """
        Create a new analysis job in the database.

        Args:
            job: AnalysisJob object to create

        Returns:
            Created job with ID assigned
        """
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get_by_id(self, job_id: int) -> Optional["AnalysisJob"]:
        """
        Get job by ID.

        Args:
            job_id: Job primary key

        Returns:
            AnalysisJob if found, None otherwise
        """
        from api.models import AnalysisJob

        return self.session.get(AnalysisJob, job_id)

    def get_all(self, limit: int | None = None) -> list["AnalysisJob"]:
        """
        Get all analysis jobs.

        Args:
            limit: Optional limit on number of results

        Returns:
            List of all jobs (or up to limit)
        """
        from api.models import AnalysisJob

        statement = select(AnalysisJob)
        if limit:
            statement = statement.limit(limit)
        return list(self.session.exec(statement).all())

    def update(self, job: "AnalysisJob") -> "AnalysisJob":
        """
        Update existing job.

        Args:
            job: AnalysisJob object with updated fields

        Returns:
            Updated job
        """
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def delete(self, job: "AnalysisJob") -> bool:
        """
        Delete a job.

        Args:
            job: AnalysisJob object to delete

        Returns:
            True if deleted successfully
        """
        self.session.delete(job)
        self.session.commit()
        return True

    def delete_by_id(self, job_id: int) -> bool:
        """
        Delete job by ID.

        Args:
            job_id: Job primary key

        Returns:
            True if deleted, False if not found
        """
        job = self.get_by_id(job_id)
        if job:
            return self.delete(job)
        return False

    # ============================================================
    # DOMAIN-SPECIFIC QUERIES
    # ============================================================

    def get_by_username(self, username: str) -> Optional["AnalysisJob"]:
        """
        Find job by username.

        Since username is unique, returns at most one job.
        Used throughout JobService to check job status and update progress.

        Args:
            username: Chess.com username (case-insensitive)

        Returns:
            AnalysisJob if found, None otherwise
        """
        from api.models import AnalysisJob

        statement = select(AnalysisJob).where(AnalysisJob.username == username)
        return self.session.exec(statement).first()

    def exists_by_username(self, username: str) -> bool:
        """
        Check if job exists for username.

        Args:
            username: Chess.com username

        Returns:
            True if job exists, False otherwise
        """
        return self.get_by_username(username) is not None

    def delete_by_username(self, username: str) -> bool:
        """
        Delete job by username.

        Used when clearing old jobs before starting a new one.

        Args:
            username: Chess.com username

        Returns:
            True if deleted, False if not found
        """
        job = self.get_by_username(username)
        if job:
            return self.delete(job)
        return False

    def get_active_jobs(self, statuses: list[str] | None = None) -> list["AnalysisJob"]:
        """
        Get all jobs with specific statuses.

        Default returns jobs with "pending" or "running" status.
        Used for monitoring active jobs.

        Args:
            statuses: List of status values to filter by (default: ["pending", "running"])

        Returns:
            List of jobs matching the statuses
        """
        from api.models import AnalysisJob

        if statuses is None:
            statuses = ["pending", "running"]

        statement = select(AnalysisJob).where(AnalysisJob.status.in_(statuses))
        return list(self.session.exec(statement).all())

    def delete_old_jobs(self, cutoff_date: datetime, statuses: list[str] | None = None) -> int:
        """
        Delete jobs older than cutoff_date with specific statuses.

        Used for cleanup of completed/failed/cancelled jobs.

        Args:
            cutoff_date: Delete jobs finished before this date
            statuses: List of statuses to delete (default: ["completed", "failed", "cancelled"])

        Returns:
            Number of jobs deleted
        """
        from api.models import AnalysisJob

        if statuses is None:
            statuses = ["completed", "failed", "cancelled"]

        statement = select(AnalysisJob).where(
            AnalysisJob.status.in_(statuses), AnalysisJob.finished_at < cutoff_date
        )
        old_jobs = self.session.exec(statement).all()

        count = len(old_jobs)
        for job in old_jobs:
            self.session.delete(job)

        self.session.commit()
        return count

    def get_all_jobs(self, status: str | None = None) -> list["AnalysisJob"]:
        """
        Get all jobs, optionally filtered by status.

        Used for listing jobs in API endpoints.

        Args:
            status: Optional status filter ("pending", "running", "completed", "failed", "cancelled")

        Returns:
            List of jobs matching filter
        """
        from api.models import AnalysisJob

        statement = select(AnalysisJob)

        if status:
            statement = statement.where(AnalysisJob.status == status)

        return list(self.session.exec(statement).all())

    def count_jobs(self, status: str | None = None) -> int:
        """
        Count jobs, optionally filtered by status.

        Args:
            status: Optional status filter

        Returns:
            Number of jobs matching filter
        """
        jobs = self.get_all_jobs(status=status)
        return len(jobs)
