"""Organise: tags, albums, storage-root exclusions and trigram search indexes (MVP-1/2).

Revision ID: 0003_organise
Revises: 0002_catalog
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_organise"
down_revision: str | None = "0002_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TZ, server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.add_column(
        "storage_root",
        sa.Column(
            "exclude_patterns",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    op.create_table(
        "tag",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_key", sa.String(100), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tag")),
        sa.UniqueConstraint("name_key", name=op.f("uq_tag_name_key")),
    )
    op.create_table(
        "asset_tag",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["media_asset.id"],
            name=op.f("fk_asset_tag_asset_id_media_asset"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tag.id"], name=op.f("fk_asset_tag_tag_id_tag"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("asset_id", "tag_id", name=op.f("pk_asset_tag")),
    )
    op.create_index(op.f("ix_asset_tag_tag_id"), "asset_tag", ["tag_id"])

    op.create_table(
        "album",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_asset_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.String(200), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["cover_asset_id"],
            ["media_asset.id"],
            name=op.f("fk_album_cover_asset_id_media_asset"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_album")),
    )
    op.create_table(
        "album_asset",
        sa.Column("album_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("added_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["album_id"], ["album.id"], name=op.f("fk_album_asset_album_id_album"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["media_asset.id"],
            name=op.f("fk_album_asset_asset_id_media_asset"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("album_id", "asset_id", name=op.f("pk_album_asset")),
    )
    op.create_index(op.f("ix_album_asset_asset_id"), "album_asset", ["asset_id"])

    # pg_trgm is enabled by 0001_baseline.
    op.create_index(
        "ix_media_asset_display_name_trgm",
        "media_asset",
        ["display_name"],
        postgresql_using="gin",
        postgresql_ops={"display_name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_media_file_relative_path_trgm",
        "media_file",
        ["relative_path"],
        postgresql_using="gin",
        postgresql_ops={"relative_path": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_media_file_relative_path_trgm", table_name="media_file")
    op.drop_index("ix_media_asset_display_name_trgm", table_name="media_asset")
    op.drop_index(op.f("ix_album_asset_asset_id"), table_name="album_asset")
    op.drop_table("album_asset")
    op.drop_table("album")
    op.drop_index(op.f("ix_asset_tag_tag_id"), table_name="asset_tag")
    op.drop_table("asset_tag")
    op.drop_table("tag")
    op.drop_column("storage_root", "exclude_patterns")
