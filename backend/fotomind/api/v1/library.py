"""Library browsing: paginated assets, asset detail and thumbnails (EPIC 4)."""

import base64
import binascii
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from fotomind.api.auth import UserDep
from fotomind.api.deps import DbDep, ThumbsDep
from fotomind.api.v1.schemas import AssetDetail, AssetPage, AssetSummary
from fotomind.domain.enums import AssetType, Availability
from fotomind.infrastructure.db.models import MediaAsset, MediaFile

router = APIRouter(tags=["library"])


def _encode_cursor(asset: MediaAsset) -> str:
    raw = f"{asset.sort_at.isoformat()}|{asset.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        sort_at, asset_id = raw.split("|", 1)
        return datetime.fromisoformat(sort_at), uuid.UUID(asset_id)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid cursor") from exc


@router.get("/assets", response_model=AssetPage)
def list_assets(
    db: DbDep,
    _user: UserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    cursor: str | None = None,
    asset_type: AssetType | None = None,
    availability: Availability | None = None,
    storage_root_id: uuid.UUID | None = None,
) -> AssetPage:
    """Newest first (capture time, falling back to file mtime). Keyset pagination."""
    filters = []
    if asset_type is not None:
        filters.append(MediaAsset.asset_type == asset_type)
    if availability is not None:
        filters.append(MediaAsset.availability == availability)
    if storage_root_id is not None:
        filters.append(
            MediaAsset.id.in_(
                select(MediaFile.asset_id).where(MediaFile.storage_root_id == storage_root_id)
            )
        )
    total = db.scalar(select(func.count()).select_from(MediaAsset).where(*filters)) or 0

    query = select(MediaAsset).where(*filters)
    if cursor:
        sort_at, asset_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                MediaAsset.sort_at < sort_at,
                and_(MediaAsset.sort_at == sort_at, MediaAsset.id < asset_id),
            )
        )
    rows = list(
        db.scalars(query.order_by(MediaAsset.sort_at.desc(), MediaAsset.id.desc()).limit(limit + 1))
    )
    next_cursor = _encode_cursor(rows[limit - 1]) if len(rows) > limit else None
    return AssetPage(
        items=[AssetSummary.from_asset(a) for a in rows[:limit]],
        total=total,
        next_cursor=next_cursor,
    )


@router.get("/assets/{asset_id}", response_model=AssetDetail)
def get_asset(asset_id: uuid.UUID, db: DbDep, _user: UserDep) -> AssetDetail:
    asset = db.scalar(
        select(MediaAsset)
        .where(MediaAsset.id == asset_id)
        .options(selectinload(MediaAsset.files).selectinload(MediaFile.storage_root))
    )
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    return AssetDetail.from_asset(asset)


@router.get(
    "/assets/{asset_id}/thumbnail",
    response_class=FileResponse,
    responses={200: {"content": {"image/jpeg": {}}}, 404: {"description": "No thumbnail"}},
)
def get_thumbnail(
    asset_id: uuid.UUID, db: DbDep, thumbs: ThumbsDep, _user: UserDep
) -> FileResponse:
    sha = db.scalar(select(MediaAsset.thumbnail_sha256).where(MediaAsset.id == asset_id))
    path = thumbs.path_for(asset_id)
    if not sha or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thumbnail not available")
    # URLs carry ?v=<sha prefix>, so the content behind a URL never changes.
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=31536000, immutable", "ETag": f'"{sha}"'},
    )
