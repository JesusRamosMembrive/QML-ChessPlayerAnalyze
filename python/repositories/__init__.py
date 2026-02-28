"""
Repository layer for database operations.

Repositories centralize all database queries and provide a clean interface
for the service layer to interact with the database.

Pattern: Repository Pattern
- Separates business logic from data access logic
- Makes testing easier (mock repositories instead of database)
- Centralizes query optimization
- Provides domain-specific query methods
"""

from repositories.aggregate_repository import AggregateRepository
from repositories.analysis_repository import AnalysisRepository
from repositories.game_repository import GameRepository
from repositories.job_repository import JobRepository

__all__ = [
    "GameRepository",
    "AnalysisRepository",
    "AggregateRepository",
    "JobRepository",
]
