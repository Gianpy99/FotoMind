"""Ratings, tags and albums (EPIC 6). Organisation never modifies original files."""

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fotomind.infrastructure.db.models import Album, AlbumAsset, MediaAsset, Tag, asset_tag

MAX_TAG_LENGTH = 100


def normalise_tag_name(value: str) -> str:
    """Collapse whitespace; raise for empty or over-long names."""
    name = " ".join(value.split())
    if not name:
        raise ValueError("tag name cannot be empty")
    if len(name) > MAX_TAG_LENGTH:
        raise ValueError(f"tag names are at most {MAX_TAG_LENGTH} characters")
    return name


def tag_key(name: str) -> str:
    return normalise_tag_name(name).casefold()


def get_or_create_tags(session: Session, names: Iterable[str]) -> list[Tag]:
    """Tags for ``names`` (case-insensitive), creating missing ones with the given spelling."""
    wanted: dict[str, str] = {}
    for raw in names:
        name = normalise_tag_name(raw)
        wanted.setdefault(name.casefold(), name)
    if not wanted:
        return []
    existing = {t.name_key: t for t in session.scalars(select(Tag).where(Tag.name_key.in_(wanted)))}
    tags = []
    for key, name in wanted.items():
        tag = existing.get(key)
        if tag is None:
            tag = Tag(name=name, name_key=key)
            session.add(tag)
        tags.append(tag)
    session.flush()
    return tags


def find_tags(session: Session, names: Iterable[str]) -> list[Tag]:
    keys = {tag_key(n) for n in names}
    if not keys:
        return []
    return list(session.scalars(select(Tag).where(Tag.name_key.in_(keys))))


def existing_asset_ids(session: Session, asset_ids: Iterable[uuid.UUID]) -> list[uuid.UUID]:
    """The given ids that exist, in the order given, without duplicates."""
    ordered = list(dict.fromkeys(asset_ids))
    if not ordered:
        return []
    found = set(session.scalars(select(MediaAsset.id).where(MediaAsset.id.in_(ordered))))
    return [i for i in ordered if i in found]


def add_to_album(session: Session, album: Album, asset_ids: Iterable[uuid.UUID]) -> int:
    """Append assets not yet in the album, keeping the given order. Returns how many were added."""
    ids = existing_asset_ids(session, asset_ids)
    present = set(
        session.scalars(
            select(AlbumAsset.asset_id).where(
                AlbumAsset.album_id == album.id, AlbumAsset.asset_id.in_(ids)
            )
        )
    )
    position = (
        session.scalar(select(func.max(AlbumAsset.position)).where(AlbumAsset.album_id == album.id))
        or 0
    )
    added = 0
    for asset_id in ids:
        if asset_id in present:
            continue
        position += 1
        session.add(AlbumAsset(album_id=album.id, asset_id=asset_id, position=position))
        added += 1
    session.flush()
    return added


def remove_from_album(session: Session, album: Album, asset_ids: Iterable[uuid.UUID]) -> int:
    ids = list(set(asset_ids))
    if not ids:
        return 0
    removed = 0
    for item in session.scalars(
        select(AlbumAsset).where(AlbumAsset.album_id == album.id, AlbumAsset.asset_id.in_(ids))
    ):
        session.delete(item)
        removed += 1
    if album.cover_asset_id in ids:
        album.cover_asset_id = None
    session.flush()
    return removed


def delete_unused_tags(session: Session) -> None:
    """Tags are only a vocabulary of what is in use; drop ones no asset carries any more."""
    session.execute(
        Tag.__table__.delete().where(~Tag.id.in_(select(asset_tag.c.tag_id).distinct()))
    )
