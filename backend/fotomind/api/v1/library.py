"""Library browsing, search and organisation: assets, facets, ratings and tags (EPIC 4/6)."""

import base64
import binascii
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, delete, exists, func, insert, or_, select, update
from sqlalchemy.orm import Session, selectinload

from fotomind.api.auth import UserDep
from fotomind.api.deps import DbDep, ThumbsDep
from fotomind.api.v1.schemas import (
    AlbumRef,
    AssetDetail,
    AssetPage,
    AssetSummary,
    FacetValue,
    LibraryFacets,
)
from fotomind.domain.enums import AssetType, Availability
from fotomind.infrastructure.db.models import (
    Album,
    AlbumAsset,
    MediaAsset,
    MediaFile,
    Tag,
    asset_tag,
)
from fotomind.modules.library.organise import (
    delete_unused_tags,
    existing_asset_ids,
    find_tags,
    get_or_create_tags,
    normalise_tag_name,
)

router = APIRouter(tags=["library"])

MAX_SEARCH_TERMS = 8
Sort = Literal["newest", "oldest"]


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


def _contains(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _search_condition(term: str) -> Any:
    """One search term matches the name, camera, lens, any file path or any tag."""
    pattern = _contains(term)

    def like(column: Any) -> Any:
        return column.ilike(pattern, escape="\\")

    return or_(
        like(MediaAsset.display_name),
        like(MediaAsset.camera_make),
        like(MediaAsset.camera_model),
        like(MediaAsset.lens_model),
        exists().where(MediaFile.asset_id == MediaAsset.id, like(MediaFile.relative_path)),
        exists().where(
            asset_tag.c.asset_id == MediaAsset.id, asset_tag.c.tag_id == Tag.id, like(Tag.name)
        ),
    )


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


@router.get("/assets", response_model=AssetPage)
def list_assets(
    db: DbDep,
    _user: UserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    cursor: str | None = None,
    asset_type: AssetType | None = None,
    availability: Availability | None = None,
    storage_root_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    min_rating: Annotated[int | None, Query(ge=0, le=5)] = None,
    tag: Annotated[list[str] | None, Query()] = None,
    album_id: uuid.UUID | None = None,
    camera: Annotated[str | None, Query(max_length=200)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: Sort = "newest",
) -> AssetPage:
    """Capture time (falling back to file mtime) order with keyset pagination.

    ``q`` terms are ANDed; each matches name, camera, lens, file path or tag. ``tag`` may be
    repeated (all must match). ``date_from``/``date_to`` are inclusive UTC days.
    """
    filters: list[Any] = []
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
    if q:
        filters.extend(_search_condition(t) for t in q.split()[:MAX_SEARCH_TERMS])
    if min_rating:
        filters.append(MediaAsset.rating >= min_rating)
    for name in tag or []:
        filters.append(
            exists().where(
                asset_tag.c.asset_id == MediaAsset.id,
                asset_tag.c.tag_id == Tag.id,
                Tag.name_key == " ".join(name.split()).casefold(),
            )
        )
    if album_id is not None:
        filters.append(
            exists().where(AlbumAsset.asset_id == MediaAsset.id, AlbumAsset.album_id == album_id)
        )
    if camera:
        filters.append(MediaAsset.camera_model == camera)
    if date_from is not None:
        filters.append(MediaAsset.sort_at >= _day_start(date_from))
    if date_to is not None:
        filters.append(MediaAsset.sort_at < _day_start(date_to + timedelta(days=1)))

    total = db.scalar(select(func.count()).select_from(MediaAsset).where(*filters)) or 0

    query = select(MediaAsset).where(*filters).options(selectinload(MediaAsset.tags))
    newest = sort == "newest"
    if cursor:
        sort_at, asset_id = _decode_cursor(cursor)
        if newest:
            after = or_(
                MediaAsset.sort_at < sort_at,
                and_(MediaAsset.sort_at == sort_at, MediaAsset.id < asset_id),
            )
        else:
            after = or_(
                MediaAsset.sort_at > sort_at,
                and_(MediaAsset.sort_at == sort_at, MediaAsset.id > asset_id),
            )
        query = query.where(after)
    order = (
        (MediaAsset.sort_at.desc(), MediaAsset.id.desc())
        if newest
        else (MediaAsset.sort_at.asc(), MediaAsset.id.asc())
    )
    rows = list(db.scalars(query.order_by(*order).limit(limit + 1)))
    next_cursor = _encode_cursor(rows[limit - 1]) if len(rows) > limit else None
    return AssetPage(
        items=[AssetSummary.from_asset(a) for a in rows[:limit]],
        total=total,
        next_cursor=next_cursor,
    )


@router.get("/library/facets", response_model=LibraryFacets)
def library_facets(db: DbDep, _user: UserDep) -> LibraryFacets:
    """Cameras, tags and years present in the library, with asset counts."""
    cameras = db.execute(
        select(MediaAsset.camera_model, func.count())
        .where(MediaAsset.camera_model.is_not(None))
        .group_by(MediaAsset.camera_model)
        .order_by(func.count().desc(), MediaAsset.camera_model)
        .limit(100)
    )
    tags = db.execute(
        select(Tag.name, func.count())
        .join(asset_tag, asset_tag.c.tag_id == Tag.id)
        .group_by(Tag.id, Tag.name)
        .order_by(func.count().desc(), Tag.name)
        .limit(500)
    )
    year = func.extract("year", MediaAsset.sort_at)
    years = db.execute(select(year, func.count()).group_by(year).order_by(year.desc()))
    types = db.execute(
        select(MediaAsset.asset_type, func.count())
        .group_by(MediaAsset.asset_type)
        .order_by(MediaAsset.asset_type)
    )
    return LibraryFacets(
        cameras=[FacetValue(value=v, count=n) for v, n in cameras],
        tags=[FacetValue(value=v, count=n) for v, n in tags],
        years=[FacetValue(value=str(int(v)), count=n) for v, n in years if v is not None],
        types=[FacetValue(value=getattr(t, "value", t), count=n) for t, n in types],
        total=db.scalar(select(func.count()).select_from(MediaAsset)) or 0,
    )


def _load_detail(db: Session, asset_id: uuid.UUID) -> AssetDetail:
    asset = db.scalar(
        select(MediaAsset)
        .where(MediaAsset.id == asset_id)
        .options(
            selectinload(MediaAsset.files).selectinload(MediaFile.storage_root),
            selectinload(MediaAsset.tags),
        )
    )
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    albums = [
        AlbumRef(id=i, name=n)
        for i, n in db.execute(
            select(Album.id, Album.name)
            .join(AlbumAsset, AlbumAsset.album_id == Album.id)
            .where(AlbumAsset.asset_id == asset_id)
            .order_by(Album.name)
        )
    ]
    return AssetDetail.from_asset(asset, albums)


@router.get("/assets/{asset_id}", response_model=AssetDetail)
def get_asset(asset_id: uuid.UUID, db: DbDep, _user: UserDep) -> AssetDetail:
    return _load_detail(db, asset_id)


TagList = Annotated[list[str], Field(max_length=100)]


class _TagNames(BaseModel):
    @field_validator("tags", "add_tags", "remove_tags", mode="after", check_fields=False)
    @classmethod
    def _valid_tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else [normalise_tag_name(v) for v in value]


class AssetUpdate(_TagNames):
    """Fields left out are unchanged. ``tags`` replaces the asset's tags."""

    rating: int | None = Field(default=None, ge=0, le=5)
    tags: TagList | None = None


class BulkAssetUpdate(_TagNames):
    asset_ids: Annotated[list[uuid.UUID], Field(min_length=1, max_length=1000)]
    rating: int | None = Field(default=None, ge=0, le=5)
    add_tags: TagList = []
    remove_tags: TagList = []


class BulkResult(BaseModel):
    updated: int


@router.patch("/assets/{asset_id}", response_model=AssetDetail)
def update_asset(asset_id: uuid.UUID, body: AssetUpdate, db: DbDep, _user: UserDep) -> AssetDetail:
    """Rate or tag one asset. Catalogue-only: original files are never modified."""
    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    if body.rating is not None:
        asset.rating = body.rating
    if body.tags is not None:
        asset.tags = get_or_create_tags(db, body.tags)
        db.flush()
        delete_unused_tags(db)
    db.commit()
    db.expire_all()
    return _load_detail(db, asset_id)


@router.post("/assets/bulk", response_model=BulkResult)
def bulk_update_assets(body: BulkAssetUpdate, db: DbDep, _user: UserDep) -> BulkResult:
    """Apply a rating and/or add/remove tags across a selection."""
    ids = existing_asset_ids(db, body.asset_ids)
    if ids and body.rating is not None:
        db.execute(
            update(MediaAsset)
            .where(MediaAsset.id.in_(ids))
            .values(rating=body.rating)
            .execution_options(synchronize_session=False)
        )
    if ids and body.add_tags:
        for tag in get_or_create_tags(db, body.add_tags):
            have = set(
                db.scalars(
                    select(asset_tag.c.asset_id).where(
                        asset_tag.c.tag_id == tag.id, asset_tag.c.asset_id.in_(ids)
                    )
                )
            )
            rows = [{"asset_id": i, "tag_id": tag.id} for i in ids if i not in have]
            if rows:
                db.execute(insert(asset_tag), rows)
    if ids and body.remove_tags:
        tag_ids = [t.id for t in find_tags(db, body.remove_tags)]
        if tag_ids:
            db.execute(
                delete(asset_tag).where(
                    asset_tag.c.asset_id.in_(ids), asset_tag.c.tag_id.in_(tag_ids)
                )
            )
            delete_unused_tags(db)
    db.commit()
    return BulkResult(updated=len(ids))


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
