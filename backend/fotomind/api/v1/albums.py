"""Albums: manual collections of assets (EPIC 6). Deleting an album never touches media."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fotomind.api.auth import UserDep
from fotomind.api.deps import DbDep
from fotomind.api.v1.schemas import AlbumOut, thumbnail_url
from fotomind.infrastructure.db.models import Album, AlbumAsset, MediaAsset
from fotomind.modules.library.organise import add_to_album, remove_from_album

router = APIRouter(prefix="/albums", tags=["albums"])

AlbumName = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
Description = Annotated[str, StringConstraints(max_length=5000)]
AssetIds = Annotated[list[uuid.UUID], Field(min_length=1, max_length=1000)]


class AlbumCreate(BaseModel):
    name: AlbumName
    description: Description | None = None
    asset_ids: Annotated[list[uuid.UUID], Field(max_length=1000)] = []


class AlbumUpdate(BaseModel):
    """Fields left out are unchanged; ``cover_asset_id: null`` restores the automatic cover."""

    name: AlbumName | None = None
    description: Description | None = None
    cover_asset_id: uuid.UUID | None = None


class AlbumAssets(BaseModel):
    asset_ids: AssetIds


def _albums_out(db: Session, albums: list[Album]) -> list[AlbumOut]:
    ids = [a.id for a in albums]
    counts = dict(
        db.execute(
            select(AlbumAsset.album_id, func.count())
            .where(AlbumAsset.album_id.in_(ids))
            .group_by(AlbumAsset.album_id)
        ).all()
    )
    # Automatic cover: the first asset by position.
    first_position = (
        select(AlbumAsset.album_id, func.min(AlbumAsset.position).label("position"))
        .where(AlbumAsset.album_id.in_(ids))
        .group_by(AlbumAsset.album_id)
        .subquery()
    )
    first = dict(
        db.execute(
            select(AlbumAsset.album_id, AlbumAsset.asset_id).join(
                first_position,
                (first_position.c.album_id == AlbumAsset.album_id)
                & (first_position.c.position == AlbumAsset.position),
            )
        ).all()
    )
    cover_ids = {a.cover_asset_id or first.get(a.id) for a in albums} - {None}
    covers = {
        asset.id: asset
        for asset in db.scalars(select(MediaAsset).where(MediaAsset.id.in_(cover_ids)))
    }
    out = []
    for album in albums:
        cover_id = album.cover_asset_id or first.get(album.id)
        cover = covers.get(cover_id) if cover_id else None
        out.append(
            AlbumOut(
                id=album.id,
                name=album.name,
                description=album.description,
                cover_asset_id=cover_id,
                cover_thumbnail_url=thumbnail_url(cover) if cover else None,
                asset_count=counts.get(album.id, 0),
                created_by=album.created_by,
                created_at=album.created_at,
                updated_at=album.updated_at,
            )
        )
    return out


def _album_or_404(db: Session, album_id: uuid.UUID) -> Album:
    album = db.get(Album, album_id)
    if album is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Album not found")
    return album


def _one(db: Session, album: Album) -> AlbumOut:
    db.refresh(album)
    return _albums_out(db, [album])[0]


@router.get("", response_model=list[AlbumOut])
def list_albums(db: DbDep, _user: UserDep) -> list[AlbumOut]:
    return _albums_out(db, list(db.scalars(select(Album).order_by(Album.name, Album.id))))


@router.post("", response_model=AlbumOut, status_code=status.HTTP_201_CREATED)
def create_album(body: AlbumCreate, db: DbDep, user: UserDep) -> AlbumOut:
    album = Album(name=body.name, description=body.description, created_by=user.username)
    db.add(album)
    db.flush()
    add_to_album(db, album, body.asset_ids)
    db.commit()
    return _one(db, album)


@router.get("/{album_id}", response_model=AlbumOut)
def get_album(album_id: uuid.UUID, db: DbDep, _user: UserDep) -> AlbumOut:
    return _albums_out(db, [_album_or_404(db, album_id)])[0]


@router.patch("/{album_id}", response_model=AlbumOut)
def update_album(album_id: uuid.UUID, body: AlbumUpdate, db: DbDep, _user: UserDep) -> AlbumOut:
    album = _album_or_404(db, album_id)
    if body.name is not None:
        album.name = body.name
    if "description" in body.model_fields_set:
        album.description = body.description or None
    if "cover_asset_id" in body.model_fields_set:
        if body.cover_asset_id is not None and not db.scalar(
            select(AlbumAsset.asset_id).where(
                AlbumAsset.album_id == album.id, AlbumAsset.asset_id == body.cover_asset_id
            )
        ):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Cover must be in the album")
        album.cover_asset_id = body.cover_asset_id
    db.commit()
    return _one(db, album)


@router.delete("/{album_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_album(album_id: uuid.UUID, db: DbDep, _user: UserDep) -> Response:
    db.delete(_album_or_404(db, album_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{album_id}/assets", response_model=AlbumOut)
def add_album_assets(album_id: uuid.UUID, body: AlbumAssets, db: DbDep, _user: UserDep) -> AlbumOut:
    """Append assets (already present ones and unknown ids are ignored)."""
    album = _album_or_404(db, album_id)
    if add_to_album(db, album, body.asset_ids):
        album.updated_at = datetime.now(UTC)
    db.commit()
    return _one(db, album)


@router.post("/{album_id}/assets/remove", response_model=AlbumOut)
def remove_album_assets(
    album_id: uuid.UUID, body: AlbumAssets, db: DbDep, _user: UserDep
) -> AlbumOut:
    album = _album_or_404(db, album_id)
    if remove_from_album(db, album, body.asset_ids):
        album.updated_at = datetime.now(UTC)
    db.commit()
    return _one(db, album)
