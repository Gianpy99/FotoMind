"""Catalogue ingest: turns worker scan reports into media_asset / media_file rows.

Identity rules (ADR-0002):
- a file is identified by (storage_root, relative_path);
- an asset is identified by content: a new path whose SHA-256 matches an existing original is
  attached to that asset (duplicate or moved file) instead of creating a new asset;
- files not seen by a completed scan become ``missing``; an unreachable root makes its files
  ``offline`` (never deleted).
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints, field_validator
from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from fotomind.domain.enums import AssetType, Availability, MediaFileRole
from fotomind.infrastructure.db.models import MediaAsset, MediaFile, StorageRoot
from fotomind.modules.storage.paths import normalise_relative_path

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ShortText = Annotated[str, StringConstraints(max_length=200)]
MetadataValue = str | int | float | bool | None

INGESTABLE_ROLES = {MediaFileRole.ORIGINAL, MediaFileRole.RAW_ORIGINAL}


class FileReport(BaseModel):
    """What the worker learned about one original file (no pixels, metadata only)."""

    relative_path: str
    size_bytes: int = Field(ge=0)
    mtime: datetime
    sha256: Sha256
    mime_type: Annotated[str, StringConstraints(max_length=100)]
    asset_type: AssetType
    role: MediaFileRole = MediaFileRole.ORIGINAL
    captured_at: datetime | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    duration_s: float | None = Field(default=None, ge=0)
    camera_make: ShortText | None = None
    camera_model: ShortText | None = None
    lens_model: ShortText | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict, max_length=64)

    @field_validator("relative_path")
    @classmethod
    def _safe_path(cls, value: str) -> str:
        return normalise_relative_path(value)

    @field_validator("mtime", "captured_at")
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @field_validator("role")
    @classmethod
    def _original_roles_only(cls, value: MediaFileRole) -> MediaFileRole:
        if value not in INGESTABLE_ROLES:
            raise ValueError("only original files can be reported by a scan")
        return value


class IngestBatch(BaseModel):
    files: list[FileReport] = Field(default_factory=list, max_length=500)
    # Relative paths whose size and mtime did not change since the previous scan.
    unchanged: list[str] = Field(default_factory=list, max_length=5000)

    @field_validator("unchanged")
    @classmethod
    def _safe_paths(cls, values: list[str]) -> list[str]:
        return [normalise_relative_path(v) for v in values]


class IngestedFile(BaseModel):
    relative_path: str
    asset_id: uuid.UUID
    needs_thumbnail: bool


class IngestResult(BaseModel):
    files: list[IngestedFile]
    unchanged_seen: int
    # Assets left without files (content changed); their thumbnails should be removed.
    orphaned_asset_ids: list[uuid.UUID]


def _apply_report(asset: MediaAsset, report: FileReport, display_name: str) -> None:
    asset.asset_type = report.asset_type
    asset.display_name = display_name[:500]
    asset.captured_at = report.captured_at
    asset.sort_at = report.captured_at or report.mtime
    asset.width = report.width
    asset.height = report.height
    asset.duration_s = report.duration_s
    asset.camera_make = report.camera_make
    asset.camera_model = report.camera_model
    asset.lens_model = report.lens_model
    asset.metadata_ = dict(report.metadata)


def _asset_with_content(session: Session, sha256: str) -> MediaAsset | None:
    return session.scalar(
        select(MediaAsset)
        .join(MediaFile, MediaFile.asset_id == MediaAsset.id)
        .where(MediaFile.sha256 == sha256, MediaFile.role.in_(INGESTABLE_ROLES))
        .limit(1)
    )


def ingest_batch(
    session: Session, root: StorageRoot, batch: IngestBatch, now: datetime
) -> IngestResult:
    results: list[IngestedFile] = []
    touched_assets: set[uuid.UUID] = set()
    previous_assets: set[uuid.UUID] = set()

    for report in batch.files:
        display_name = report.relative_path.rsplit("/", 1)[-1]
        file = session.scalar(
            select(MediaFile).where(
                MediaFile.storage_root_id == root.id,
                MediaFile.relative_path == report.relative_path,
            )
        )
        if file is not None and file.sha256 != report.sha256:
            # Content changed in place: the file belongs to whichever asset has the new content.
            previous_assets.add(file.asset_id)
            asset = _asset_with_content(session, report.sha256)
            if asset is None:
                asset = MediaAsset(rating=0, availability=Availability.ONLINE, metadata_={})
                _apply_report(asset, report, display_name)
                session.add(asset)
                session.flush()
            file.asset = asset
            file.sha256 = report.sha256
        elif file is None:
            asset = _asset_with_content(session, report.sha256)
            if asset is None:
                asset = MediaAsset(rating=0, availability=Availability.ONLINE, metadata_={})
                _apply_report(asset, report, display_name)
                session.add(asset)
                session.flush()
            file = MediaFile(
                asset=asset,
                storage_root_id=root.id,
                relative_path=report.relative_path,
                sha256=report.sha256,
            )
            session.add(file)
        else:
            asset = file.asset
            # Same content, re-extracted metadata (e.g. a better extractor). Duplicates keep the
            # metadata of the copy that created the asset.
            if len(asset.files) == 1:
                _apply_report(asset, report, display_name)

        file.role = report.role
        file.mime_type = report.mime_type
        file.size_bytes = report.size_bytes
        file.mtime = report.mtime
        file.availability = Availability.ONLINE
        file.last_seen_at = now
        session.flush()
        touched_assets.add(asset.id)
        results.append(
            IngestedFile(
                relative_path=report.relative_path,
                asset_id=asset.id,
                needs_thumbnail=asset.thumbnail_sha256 is None,
            )
        )

    unchanged_seen = 0
    if batch.unchanged:
        unchanged_seen = session.execute(
            update(MediaFile)
            .where(
                MediaFile.storage_root_id == root.id,
                MediaFile.relative_path.in_(batch.unchanged),
            )
            .values(last_seen_at=now, availability=Availability.ONLINE)
            .execution_options(synchronize_session=False)
        ).rowcount

    orphaned: list[uuid.UUID] = []
    for asset_id in previous_assets - touched_assets:
        asset = session.get(MediaAsset, asset_id)
        if asset is not None:
            session.refresh(asset, ["files"])
            if not asset.files:
                session.delete(asset)
                orphaned.append(asset_id)
    session.flush()
    return IngestResult(files=results, unchanged_seen=unchanged_seen, orphaned_asset_ids=orphaned)


def recompute_asset_availability(session: Session, root_id: uuid.UUID) -> None:
    """An asset is online if any file is online, offline if any root holding it is offline."""
    in_root = select(MediaFile.asset_id).where(MediaFile.storage_root_id == root_id)

    def has_file(state: Availability) -> Any:
        return exists().where(MediaFile.asset_id == MediaAsset.id, MediaFile.availability == state)

    for state, condition in (
        (Availability.ONLINE, has_file(Availability.ONLINE)),
        (Availability.OFFLINE, ~has_file(Availability.ONLINE) & has_file(Availability.OFFLINE)),
        (
            Availability.MISSING,
            ~has_file(Availability.ONLINE) & ~has_file(Availability.OFFLINE),
        ),
    ):
        session.execute(
            update(MediaAsset)
            .where(MediaAsset.id.in_(in_root), condition, MediaAsset.availability != state)
            .values(availability=state)
            .execution_options(synchronize_session=False)
        )


def finish_scan(
    session: Session, root: StorageRoot, scan_started_at: datetime, now: datetime
) -> int:
    """Mark files not seen since the scan started as missing. Returns how many went missing."""
    missing = session.execute(
        update(MediaFile)
        .where(
            MediaFile.storage_root_id == root.id,
            MediaFile.last_seen_at < scan_started_at,
            MediaFile.availability != Availability.MISSING,
        )
        .values(availability=Availability.MISSING)
        .execution_options(synchronize_session=False)
    ).rowcount
    root.availability = Availability.ONLINE
    root.last_scan_at = now
    recompute_asset_availability(session, root.id)
    return missing


def mark_root_offline(session: Session, root: StorageRoot) -> None:
    """The root's disk/folder is unreachable: files are offline, not missing (LIB-009)."""
    root.availability = Availability.OFFLINE
    session.execute(
        update(MediaFile)
        .where(
            MediaFile.storage_root_id == root.id,
            MediaFile.availability == Availability.ONLINE,
        )
        .values(availability=Availability.OFFLINE)
        .execution_options(synchronize_session=False)
    )
    recompute_asset_availability(session, root.id)
