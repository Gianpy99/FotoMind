"""Places: gazetteer search, place tags and the photo map (LIB-008)."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, StringConstraints, model_validator
from sqlalchemy import func, select

from fotomind.api.auth import UserDep
from fotomind.api.deps import DbDep
from fotomind.api.v1.library import FiltersDep, tag_located_condition
from fotomind.api.v1.schemas import (
    MapPoint,
    MapPoints,
    PlaceOut,
    TagPlaceOut,
    TagPlaces,
    TagPlaceSuggestion,
)
from fotomind.infrastructure.db.models import MediaAsset, Tag, asset_tag
from fotomind.modules import places
from fotomind.modules.library.organise import normalise_tag_name

router = APIRouter(tags=["places"])

MAX_MAP_POINTS = 20_000
MAX_SUGGESTIONS = 200


@router.get("/places/search", response_model=list[PlaceOut])
def search_places(
    _user: UserDep,
    q: Annotated[str, Query(min_length=1, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> list[PlaceOut]:
    """Cities (population ≥ 15,000) and countries whose name starts with ``q``."""
    return [PlaceOut.from_place(p) for p in places.search(q, limit)]


@router.get("/places/tags", response_model=TagPlaces)
def tag_places(db: DbDep, _user: UserDep) -> TagPlaces:
    """Tags whose name matches a known place (to confirm once), and decisions already taken."""
    counts = func.count(asset_tag.c.asset_id)
    rows = db.execute(
        select(Tag, counts)
        .outerjoin(asset_tag, asset_tag.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(counts.desc(), Tag.name)
    ).all()
    suggestions: list[TagPlaceSuggestion] = []
    decided: list[TagPlaceOut] = []
    for tag, count in rows:
        if tag.place_status in ("confirmed", "rejected"):
            decided.append(
                TagPlaceOut(
                    tag=tag.name,
                    count=count,
                    status=tag.place_status,
                    label=tag.place_label,
                    kind=tag.place_kind,
                    latitude=tag.latitude,
                    longitude=tag.longitude,
                )
            )
        elif count and len(suggestions) < MAX_SUGGESTIONS:
            candidates = places.lookup(tag.name)
            if candidates:
                suggestions.append(
                    TagPlaceSuggestion(
                        tag=tag.name,
                        count=count,
                        candidates=[PlaceOut.from_place(p) for p in candidates],
                    )
                )
    decided.sort(key=lambda d: (d.status != "confirmed", d.tag.casefold()))
    return TagPlaces(suggestions=suggestions, decided=decided)


class TagPlaceIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    label: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    kind: Literal["city", "country", "custom"] = "city"


class TagPlaceDecision(BaseModel):
    tag: str
    status: Literal["confirmed", "rejected", "unset"]
    place: TagPlaceIn | None = None

    @model_validator(mode="after")
    def _place_when_confirmed(self) -> "TagPlaceDecision":
        if (self.status == "confirmed") != (self.place is not None):
            raise ValueError("a place is required to confirm, and only then")
        return self


@router.put("/places/tags", response_model=TagPlaces)
def decide_tag_place(body: TagPlaceDecision, db: DbDep, _user: UserDep) -> TagPlaces:
    """Confirm a tag as a place (its photos then appear on the map), reject it, or reset."""
    key = normalise_tag_name(body.tag).casefold()
    tag = db.scalar(select(Tag).where(Tag.name_key == key))
    if tag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")
    place = body.place
    tag.place_status = None if body.status == "unset" else body.status
    tag.place_label = " ".join(place.label.split()) if place else None
    tag.place_kind = place.kind if place else None
    tag.latitude = round(place.latitude, 6) if place else None
    tag.longitude = round(place.longitude, 6) if place else None
    db.commit()
    return tag_places(db, _user)


def _thumb(asset_id: Any, sha: str | None) -> str | None:
    return f"/api/v1/assets/{asset_id}/thumbnail?v={sha[:16]}" if sha else None


_POINT_COLUMNS = (
    MediaAsset.id,
    MediaAsset.asset_type,
    MediaAsset.display_name,
    MediaAsset.sort_at,
    MediaAsset.thumbnail_sha256,
)


@router.get("/map/assets", response_model=MapPoints)
def map_assets(db: DbDep, _user: UserDep, filters: FiltersDep) -> MapPoints:
    """Positions of the (filtered) assets that have one, newest first.

    An asset's own position (from the file or set by hand) wins; otherwise its most
    specific confirmed place tag. Capped at ``MAX_MAP_POINTS``.
    """
    own = db.execute(
        select(
            *_POINT_COLUMNS, MediaAsset.latitude, MediaAsset.longitude, MediaAsset.location_source
        )
        .where(*filters, MediaAsset.latitude.is_not(None), MediaAsset.longitude.is_not(None))
        .order_by(MediaAsset.sort_at.desc(), MediaAsset.id.desc())
        .limit(MAX_MAP_POINTS + 1)
    ).all()
    points = [
        MapPoint(
            id=r.id,
            latitude=r.latitude,
            longitude=r.longitude,
            source="manual" if r.location_source == "manual" else "file",
            asset_type=r.asset_type,
            display_name=r.display_name,
            sort_at=r.sort_at,
            thumbnail_url=_thumb(r.id, r.thumbnail_sha256),
        )
        for r in own
    ]

    by_tag = db.execute(
        select(*_POINT_COLUMNS, Tag.latitude, Tag.longitude, Tag.place_kind, Tag.name_key)
        .join(asset_tag, asset_tag.c.asset_id == MediaAsset.id)
        .join(Tag, Tag.id == asset_tag.c.tag_id)
        .where(
            *filters,
            tag_located_condition(),
            Tag.place_status == "confirmed",
            Tag.latitude.is_not(None),
        )
        .order_by(MediaAsset.sort_at.desc(), MediaAsset.id.desc())
    )
    best: dict[Any, Any] = {}
    for r in by_tag:
        rank = (r.place_kind == "country", r.name_key)
        if r.id not in best or rank < best[r.id][0]:
            best[r.id] = (rank, r)
        if len(best) > MAX_MAP_POINTS:
            break
    points.extend(
        MapPoint(
            id=r.id,
            latitude=r.latitude,
            longitude=r.longitude,
            source="tag",
            asset_type=r.asset_type,
            display_name=r.display_name,
            sort_at=r.sort_at,
            thumbnail_url=_thumb(r.id, r.thumbnail_sha256),
        )
        for _, r in best.values()
    )
    points.sort(key=lambda p: (p.sort_at, str(p.id)), reverse=True)
    return MapPoints(items=points[:MAX_MAP_POINTS], truncated=len(points) > MAX_MAP_POINTS)
