"""Response models shared by the v1 routers (the OpenAPI contract for the TS client)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from fotomind.domain.enums import (
    AssetType,
    Availability,
    BackupState,
    JobStatus,
    MediaFileRole,
)
from fotomind.infrastructure.db.models import MediaAsset


class _Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StorageRootOut(_Orm):
    id: uuid.UUID
    label: str
    host: str
    path: str
    volume_id: str | None
    availability: Availability
    last_scan_at: datetime | None
    created_at: datetime
    file_count: int = 0
    missing_count: int = 0


class JobOut(_Orm):
    id: uuid.UUID
    job_type: str
    status: JobStatus
    host: str | None
    storage_root_id: uuid.UUID | None
    progress_done: int
    progress_total: int | None
    message: str | None
    error: str | None
    result: dict[str, Any]
    attempts: int
    requested_by: str | None
    created_at: datetime
    started_at: datetime | None
    heartbeat_at: datetime | None
    finished_at: datetime | None


class AssetSummary(_Orm):
    id: uuid.UUID
    asset_type: AssetType
    display_name: str
    sort_at: datetime
    captured_at: datetime | None
    width: int | None
    height: int | None
    duration_s: float | None
    rating: int
    availability: Availability
    # Relative to the API origin; versioned by content so browsers can cache it forever.
    thumbnail_url: str | None = None

    @classmethod
    def from_asset(cls, asset: MediaAsset) -> "AssetSummary":
        out = cls.model_validate(asset)
        out.thumbnail_url = thumbnail_url(asset)
        return out


class MediaFileOut(_Orm):
    id: uuid.UUID
    storage_root_id: uuid.UUID
    storage_root_label: str
    relative_path: str
    role: MediaFileRole
    mime_type: str
    size_bytes: int
    mtime: datetime
    sha256: str
    availability: Availability
    backup_state: BackupState
    last_seen_at: datetime


class AssetDetail(AssetSummary):
    camera_make: str | None
    camera_model: str | None
    lens_model: str | None
    metadata: dict[str, Any]
    files: list[MediaFileOut]

    @classmethod
    def from_asset(cls, asset: MediaAsset) -> "AssetDetail":
        files = [
            MediaFileOut(
                id=f.id,
                storage_root_id=f.storage_root_id,
                storage_root_label=f.storage_root.label,
                relative_path=f.relative_path,
                role=f.role,
                mime_type=f.mime_type,
                size_bytes=f.size_bytes,
                mtime=f.mtime,
                sha256=f.sha256,
                availability=f.availability,
                backup_state=f.backup_state,
                last_seen_at=f.last_seen_at,
            )
            for f in asset.files
        ]
        summary = AssetSummary.from_asset(asset)
        return cls(
            **summary.model_dump(),
            camera_make=asset.camera_make,
            camera_model=asset.camera_model,
            lens_model=asset.lens_model,
            metadata=asset.metadata_,
            files=files,
        )


class AssetPage(BaseModel):
    items: list[AssetSummary]
    total: int
    next_cursor: str | None


def thumbnail_url(asset: MediaAsset) -> str | None:
    if not asset.thumbnail_sha256:
        return None
    return f"/api/v1/assets/{asset.id}/thumbnail?v={asset.thumbnail_sha256[:16]}"
