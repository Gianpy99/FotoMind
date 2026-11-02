"""PostgreSQL persistence (SQLAlchemy 2). Alembic migrations in database/migrations are the
source of truth for the schema; models must be registered on ``Base.metadata``."""

from fotomind.infrastructure.db.base import Base

__all__ = ["Base"]
