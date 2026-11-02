"""Catalogue: storage_root, media_asset, media_file, job (ADR-0002, EPIC 2/3).

Revision ID: 0002_catalog
Revises: 0001_baseline
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_catalog"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TZ, server_default=sa.func.now(), nullable=False),
    ]


def _state(name: str) -> sa.Column:
    return sa.Column(name, sa.String(32), nullable=False)


def upgrade() -> None:
    op.create_table(
        "storage_root",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("volume_id", sa.String(64), nullable=True),
        _state("availability"),
        sa.Column("last_scan_at", TZ, nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_storage_root"),
        sa.UniqueConstraint("host", "path", name="uq_storage_root_host_path"),
    )

    op.create_table(
        "media_asset",
        sa.Column("id", sa.Uuid(), nullable=False),
        _state("asset_type"),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("sort_at", TZ, nullable=False),
        sa.Column("captured_at", TZ, nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column("camera_make", sa.String(200), nullable=True),
        sa.Column("camera_model", sa.String(200), nullable=True),
        sa.Column("lens_model", sa.String(200), nullable=True),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        _state("availability"),
        sa.Column("thumbnail_sha256", sa.String(64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_media_asset"),
    )
    op.create_index("ix_media_asset_sort", "media_asset", ["sort_at", "id"])

    op.create_table(
        "media_file",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("storage_root_id", sa.Uuid(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        _state("role"),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mtime", TZ, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        _state("availability"),
        _state("backup_state"),
        sa.Column("last_seen_at", TZ, nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_media_file"),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["media_asset.id"],
            name="fk_media_file_asset_id_media_asset",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["storage_root_id"],
            ["storage_root.id"],
            name="fk_media_file_storage_root_id_storage_root",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("storage_root_id", "relative_path", name="uq_media_file_root_path"),
    )
    op.create_index("ix_media_file_asset_id", "media_file", ["asset_id"])
    op.create_index("ix_media_file_storage_root_id", "media_file", ["storage_root_id"])
    op.create_index("ix_media_file_sha256", "media_file", ["sha256"])

    op.create_table(
        "job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        _state("status"),
        sa.Column("host", sa.String(255), nullable=True),
        sa.Column("storage_root_id", sa.Uuid(), nullable=True),
        sa.Column("params", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("progress_done", sa.Integer(), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("worker_id", sa.String(255), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.String(200), nullable=True),
        sa.Column("started_at", TZ, nullable=True),
        sa.Column("heartbeat_at", TZ, nullable=True),
        sa.Column("finished_at", TZ, nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_job"),
        sa.ForeignKeyConstraint(
            ["storage_root_id"],
            ["storage_root.id"],
            name="fk_job_storage_root_id_storage_root",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_job_status_host", "job", ["status", "host"])
    op.create_index("ix_job_storage_root_id", "job", ["storage_root_id"])


def downgrade() -> None:
    op.drop_table("job")
    op.drop_table("media_file")
    op.drop_table("media_asset")
    op.drop_table("storage_root")
