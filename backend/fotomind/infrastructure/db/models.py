"""ORM models (ADR-0002). Alembic migrations remain the source of truth for the schema.

Types are portable (generic Uuid/JSON) so unit tests can run on SQLite; PostgreSQL gets
JSONB through a variant.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fotomind.domain.enums import (
    AssetType,
    Availability,
    BackupState,
    JobStatus,
    MediaFileRole,
)
from fotomind.infrastructure.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

JsonDict = JSON().with_variant(JSONB(), "postgresql")


def _trigram_index(name: str, column: str) -> Index:
    # GIN trigram index for ILIKE '%term%' search on PostgreSQL (plain index elsewhere).
    return Index(name, column, postgresql_using="gin", postgresql_ops={column: "gin_trgm_ops"})


def _enum(cls: type[StrEnum]) -> Enum:
    # Stored as VARCHAR values (not native PG enums) so adding members needs no migration.
    return Enum(
        cls,
        native_enum=False,
        create_constraint=False,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


class StorageRoot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A folder on a worker host whose media FotoMind catalogues (never modifies)."""

    __tablename__ = "storage_root"
    __table_args__ = (UniqueConstraint("host", "path", name="uq_storage_root_host_path"),)

    label: Mapped[str] = mapped_column(String(200))
    host: Mapped[str] = mapped_column(String(255))
    # Last seen absolute path on the host; media paths are stored relative to it.
    path: Mapped[str] = mapped_column(Text)
    volume_id: Mapped[str | None] = mapped_column(String(64))
    availability: Mapped[Availability] = mapped_column(
        _enum(Availability), default=Availability.ONLINE
    )
    # Glob patterns skipped by the scanner (LIB-003); see modules.storage.paths.is_excluded.
    exclude_patterns: Mapped[list[str]] = mapped_column(JsonDict, default=list)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MediaAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The logical photo or video the user sees; backed by one or more media_file rows."""

    __tablename__ = "media_asset"
    __table_args__ = (
        Index("ix_media_asset_sort", "sort_at", "id"),
        Index(
            "ix_media_asset_located",
            "latitude",
            "longitude",
            postgresql_where=text("latitude IS NOT NULL"),
            sqlite_where=text("latitude IS NOT NULL"),
        ),
        _trigram_index("ix_media_asset_display_name_trgm", "display_name"),
    )

    asset_type: Mapped[AssetType] = mapped_column(_enum(AssetType))
    display_name: Mapped[str] = mapped_column(String(500))
    # Capture time when known, otherwise the file mtime: the library's sort key.
    sort_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_s: Mapped[float | None] = mapped_column(Float)
    camera_make: Mapped[str | None] = mapped_column(String(200))
    camera_model: Mapped[str | None] = mapped_column(String(200))
    lens_model: Mapped[str | None] = mapped_column(String(200))
    rating: Mapped[int] = mapped_column(SmallInteger, default=0)
    title: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    # "file" (GPS in the original), "manual", or "cleared" (no location, ignore place tags).
    location_source: Mapped[str | None] = mapped_column(String(16))
    place_name: Mapped[str | None] = mapped_column(String(200))
    # Fields the user changed by hand (EDITABLE_FIELDS); re-scans keep the edit and only
    # refresh ``file_values``, the values read from the original (for "revert").
    edited_fields: Mapped[list[str]] = mapped_column(JsonDict, default=list)
    file_values: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    # Version of the worker's metadata extractor that last read the original.
    extractor_version: Mapped[int] = mapped_column(Integer, default=0)
    availability: Mapped[Availability] = mapped_column(
        _enum(Availability), default=Availability.ONLINE
    )
    # SHA-256 of the stored thumbnail JPEG (Pi data volume); also the cache validator.
    thumbnail_sha256: Mapped[str | None] = mapped_column(String(64))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JsonDict, default=dict)

    files: Mapped[list["MediaFile"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan", order_by="MediaFile.created_at"
    )
    tags: Mapped[list["Tag"]] = relationship(secondary="asset_tag", order_by="Tag.name")


class MediaFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A physical file on a storage root. Originals are read-only (ADR-0007)."""

    __tablename__ = "media_file"
    __table_args__ = (
        UniqueConstraint("storage_root_id", "relative_path", name="uq_media_file_root_path"),
        _trigram_index("ix_media_file_relative_path_trgm", "relative_path"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("media_asset.id", ondelete="CASCADE"), index=True
    )
    storage_root_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("storage_root.id", ondelete="CASCADE"), index=True
    )
    # POSIX-style, relative to the storage root, never containing "..".
    relative_path: Mapped[str] = mapped_column(Text)
    role: Mapped[MediaFileRole] = mapped_column(_enum(MediaFileRole))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    mtime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    availability: Mapped[Availability] = mapped_column(
        _enum(Availability), default=Availability.ONLINE
    )
    backup_state: Mapped[BackupState] = mapped_column(
        _enum(BackupState), default=BackupState.UNKNOWN
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    asset: Mapped[MediaAsset] = relationship(back_populates="files")
    storage_root: Mapped[StorageRoot] = relationship()


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Background work executed by a worker host (restartable; ADR-0001)."""

    __tablename__ = "job"
    __table_args__ = (Index("ix_job_status_host", "status", "host"),)

    job_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[JobStatus] = mapped_column(_enum(JobStatus), default=JobStatus.QUEUED)
    host: Mapped[str | None] = mapped_column(String(255))
    storage_root_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("storage_root.id", ondelete="SET NULL"), index=True
    )
    params: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[str | None] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    requested_by: Mapped[str | None] = mapped_column(String(200))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


asset_tag = Table(
    "asset_tag",
    Base.metadata,
    Column("asset_id", Uuid, ForeignKey("media_asset.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Uuid, ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class Tag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A free-form keyword. Names are unique case-insensitively (``name_key``)."""

    __tablename__ = "tag"

    name: Mapped[str] = mapped_column(String(100))
    name_key: Mapped[str] = mapped_column(String(100), unique=True)
    # A place-name tag the user confirmed ("confirmed", with coordinates) or dismissed
    # ("rejected"); assets without their own location appear on the map at a confirmed tag.
    place_status: Mapped[str | None] = mapped_column(String(16))
    place_label: Mapped[str | None] = mapped_column(String(200))
    place_kind: Mapped[str | None] = mapped_column(String(16))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)


class Album(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A manual collection. Deleting an album never touches its media."""

    __tablename__ = "album"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    cover_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("media_asset.id", ondelete="SET NULL")
    )
    created_by: Mapped[str | None] = mapped_column(String(200))

    items: Mapped[list["AlbumAsset"]] = relationship(
        back_populates="album", cascade="all, delete-orphan", order_by="AlbumAsset.position"
    )


class AlbumAsset(Base):
    __tablename__ = "album_asset"

    album_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("album.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("media_asset.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    album: Mapped[Album] = relationship(back_populates="items")
