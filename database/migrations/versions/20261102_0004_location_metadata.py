"""Location and editable metadata: GPS, title/description, user edits, place-name tags.

Revision ID: 0004_location_metadata
Revises: 0003_organise
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_location_metadata"
down_revision: str | None = "0003_organise"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("media_asset", sa.Column("title", sa.String(300), nullable=True))
    op.add_column("media_asset", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("media_asset", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("media_asset", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("media_asset", sa.Column("location_source", sa.String(16), nullable=True))
    op.add_column("media_asset", sa.Column("place_name", sa.String(200), nullable=True))
    op.add_column(
        "media_asset",
        sa.Column(
            "edited_fields",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "media_asset",
        sa.Column(
            "file_values",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "media_asset",
        sa.Column("extractor_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(
        "ix_media_asset_located",
        "media_asset",
        ["latitude", "longitude"],
        postgresql_where=sa.text("latitude IS NOT NULL"),
    )

    op.add_column("tag", sa.Column("place_status", sa.String(16), nullable=True))
    op.add_column("tag", sa.Column("place_label", sa.String(200), nullable=True))
    op.add_column("tag", sa.Column("place_kind", sa.String(16), nullable=True))
    op.add_column("tag", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("tag", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    for column in ("longitude", "latitude", "place_kind", "place_label", "place_status"):
        op.drop_column("tag", column)
    op.drop_index("ix_media_asset_located", table_name="media_asset")
    for column in (
        "extractor_version",
        "file_values",
        "edited_fields",
        "place_name",
        "location_source",
        "longitude",
        "latitude",
        "description",
        "title",
    ):
        op.drop_column("media_asset", column)
