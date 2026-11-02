"""Baseline: empty schema plus extensions FotoMind relies on.

The catalogue schema (storage_root, media_asset, media_file, ...) is added in the next
migration, following PRD §8 and docs/adr/0002-storage-model.md.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pg_trgm ships with PostgreSQL contrib; used for metadata/fuzzy search while pgvector
    # remains unavailable on the Pi (ADR-0006). Creating it may require the DB owner role.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
