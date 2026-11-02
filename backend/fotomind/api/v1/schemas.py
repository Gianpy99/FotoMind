"""Response models shared by the v1 routers (the OpenAPI contract for the TS client)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from fotomind.domain.enums import (
    AssetType,
    Availability,
    BackupState,
    JobStatus,
    MediaFileRole,
)
from fotomind.infrastructure.db.models import MediaAsset
from fotomind.modules import places


class _Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StorageRootOut(_Orm):
    id: uuid.UUID
    label: str
    host: str
    path: str
    volume_id: str | None
    availability: Availability
    exclude_patterns: list[str] = []
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


class LocationOut(BaseModel):
    """Where an asset is shown on the map: its own position, or a confirmed place tag."""

    latitude: float
    longitude: float
    source: Literal["file", "manual", "tag"]
    label: str | None = None
    # The place tag supplying the position (source "tag").
    tag: str | None = None


def effective_location(asset: MediaAsset) -> LocationOut | None:
    if asset.latitude is not None and asset.longitude is not None:
        source = "manual" if asset.location_source == "manual" else "file"
        return LocationOut(
            latitude=asset.latitude,
            longitude=asset.longitude,
            source=source,
            label=asset.place_name,
        )
    if asset.location_source == "cleared":
        return None
    places = [
        t
        for t in asset.tags
        if t.place_status == "confirmed" and t.latitude is not None and t.longitude is not None
    ]
    if not places:
        return None
    # The most specific place wins (a city over a country).
    best = min(places, key=lambda t: (t.place_kind == "country", t.name_key))
    return LocationOut(
        latitude=best.latitude,  # type: ignore[arg-type]
        longitude=best.longitude,  # type: ignore[arg-type]
        source="tag",
        label=best.place_label or best.name,
        tag=best.name,
    )


class AssetSummary(_Orm):
    id: uuid.UUID
    asset_type: AssetType
    display_name: str
    title: str | None = None
    sort_at: datetime
    captured_at: datetime | None
    width: int | None
    height: int | None
    duration_s: float | None
    rating: int
    availability: Availability
    tags: list[str] = []
    location: LocationOut | None = None
    # Relative to the API origin; versioned by content so browsers can cache it forever.
    thumbnail_url: str | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def _tag_names(cls, value: Any) -> Any:
        return [getattr(t, "name", t) for t in value or []]

    @classmethod
    def from_asset(cls, asset: MediaAsset) -> "AssetSummary":
        out = cls.model_validate(asset)
        out.thumbnail_url = thumbnail_url(asset)
        out.location = effective_location(asset)
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


class AlbumRef(BaseModel):
    id: uuid.UUID
    name: str


class AssetDetail(AssetSummary):
    description: str | None = None
    camera_make: str | None
    camera_model: str | None
    lens_model: str | None
    metadata: dict[str, Any]
    files: list[MediaFileOut]
    albums: list[AlbumRef] = []
    # Fields changed by hand, and what the original file says for them (for "revert").
    edited_fields: list[str] = []
    file_values: dict[str, Any] = {}
    # "Near Rome, Lazio, Italy" for GPS positions without a place name.
    location_near: str | None = None

    @classmethod
    def from_asset(  # type: ignore[override]
        cls, asset: MediaAsset, albums: list[AlbumRef] | None = None
    ) -> "AssetDetail":
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
        near = None
        loc = summary.location
        if loc is not None and loc.source != "tag" and not loc.label:
            place = places.nearest(loc.latitude, loc.longitude)
            near = place.label if place else None
        return cls(
            **summary.model_dump(),
            description=asset.description,
            camera_make=asset.camera_make,
            camera_model=asset.camera_model,
            lens_model=asset.lens_model,
            metadata=asset.metadata_,
            files=files,
            albums=albums or [],
            edited_fields=list(asset.edited_fields or []),
            file_values=dict(asset.file_values or {}),
            location_near=near,
        )


class AssetPage(BaseModel):
    items: list[AssetSummary]
    total: int
    next_cursor: str | None


class FacetValue(BaseModel):
    value: str
    count: int


class LibraryFacets(BaseModel):
    """Values present in the library, for the filter bar."""

    cameras: list[FacetValue]
    tags: list[FacetValue]
    years: list[FacetValue]
    types: list[FacetValue] = []
    # Assets with a map position (own GPS/manual, or a confirmed place tag).
    located: int = 0
    total: int


class PlaceOut(BaseModel):
    name: str
    label: str
    kind: Literal["city", "country"]
    country_code: str
    latitude: float
    longitude: float

    @classmethod
    def from_place(cls, place: places.Place) -> "PlaceOut":
        return cls(
            name=place.name,
            label=place.label,
            kind=place.kind,  # type: ignore[arg-type]
            country_code=place.country_code,
            latitude=place.latitude,
            longitude=place.longitude,
        )


class TagPlaceSuggestion(BaseModel):
    tag: str
    count: int
    candidates: list[PlaceOut]


class TagPlaceOut(BaseModel):
    tag: str
    count: int
    status: Literal["confirmed", "rejected"]
    label: str | None = None
    kind: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class TagPlaces(BaseModel):
    """Tags that look like places (awaiting a decision) and the decisions taken."""

    suggestions: list[TagPlaceSuggestion]
    decided: list[TagPlaceOut]
    attribution: str = places.ATTRIBUTION


class MapPoint(BaseModel):
    id: uuid.UUID
    latitude: float
    longitude: float
    source: Literal["file", "manual", "tag"]
    asset_type: AssetType
    display_name: str
    sort_at: datetime
    thumbnail_url: str | None


class MapPoints(BaseModel):
    items: list[MapPoint]
    # More located assets matched than were returned (newest first).
    truncated: bool


class AlbumOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    cover_asset_id: uuid.UUID | None
    cover_thumbnail_url: str | None
    asset_count: int
    created_by: str | None
    created_at: datetime
    updated_at: datetime


def thumbnail_url(asset: MediaAsset) -> str | None:
    if not asset.thumbnail_sha256:
        return None
    return f"/api/v1/assets/{asset.id}/thumbnail?v={asset.thumbnail_sha256[:16]}"
