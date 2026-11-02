"""User-authored metadata edits (LIB-007). Catalogue-only: originals are never modified.

Fields read from the original (date taken, GPS, camera, lens) can be overridden by hand. An
overridden field is listed in ``media_asset.edited_fields``; re-scans then keep the user's
value and only refresh ``media_asset.file_values`` (what the file says) so the edit can be
reverted later. Title and description exist only in the catalogue.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from fotomind.infrastructure.db.models import MediaAsset

EditableField = Literal["captured_at", "location", "camera_make", "camera_model", "lens_model"]
EDITABLE_FIELDS: tuple[EditableField, ...] = (
    "captured_at",
    "location",
    "camera_make",
    "camera_model",
    "lens_model",
)
MAX_SHIFT_SECONDS = 100 * 366 * 24 * 3600

LocationSource = Literal["file", "manual", "cleared"]


class FileValues(BaseModel):
    """What the original says, as reported by a scan."""

    captured_at: datetime | None = None
    sort_at: datetime
    latitude: float | None = None
    longitude: float | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    lens_model: str | None = None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    # SQLite (unit tests) hands back naive datetimes; they are stored as UTC.
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC).isoformat()


def _parse(value: Any) -> datetime | None:
    return datetime.fromisoformat(value) if isinstance(value, str) else None


def _current_value(asset: MediaAsset, field: EditableField) -> Any:
    """The asset's present value of ``field`` in its JSON form (what "revert" restores)."""
    if field == "captured_at":
        return {"captured_at": _iso(asset.captured_at), "sort_at": _iso(asset.sort_at)}
    if field == "location":
        if asset.location_source != "file" or asset.latitude is None:
            return None
        return {"latitude": asset.latitude, "longitude": asset.longitude}
    return getattr(asset, field)


def _file_value(values: FileValues, field: EditableField) -> Any:
    if field == "captured_at":
        return {"captured_at": _iso(values.captured_at), "sort_at": _iso(values.sort_at)}
    if field == "location":
        if values.latitude is None or values.longitude is None:
            return None
        return {"latitude": values.latitude, "longitude": values.longitude}
    return getattr(values, field)


def _set_value(asset: MediaAsset, field: EditableField, value: Any) -> None:
    """Write a JSON-form value (from ``_file_value``) to the asset's columns."""
    if field == "captured_at":
        value = value or {}
        asset.captured_at = _parse(value.get("captured_at"))
        asset.sort_at = _parse(value.get("sort_at")) or asset.captured_at or asset.sort_at
    elif field == "location":
        if value:
            asset.latitude, asset.longitude = value["latitude"], value["longitude"]
            asset.location_source = "file"
        else:
            asset.latitude = asset.longitude = None
            asset.location_source = None
        asset.place_name = None
    else:
        setattr(asset, field, value)


def apply_file_values(asset: MediaAsset, values: FileValues) -> None:
    """Scan result -> asset, keeping fields the user edited (their file value is remembered)."""
    edited = set(asset.edited_fields or [])
    remembered = dict(asset.file_values or {})
    for field in EDITABLE_FIELDS:
        value = _file_value(values, field)
        if field in edited:
            remembered[field] = value
        else:
            _set_value(asset, field, value)
    asset.file_values = remembered


def _mark_edited(asset: MediaAsset, field: EditableField) -> None:
    edited = list(asset.edited_fields or [])
    if field in edited:
        return
    asset.file_values = {**(asset.file_values or {}), field: _current_value(asset, field)}
    asset.edited_fields = [*edited, field]


def revert_field(asset: MediaAsset, field: EditableField) -> None:
    edited = list(asset.edited_fields or [])
    if field not in edited:
        return
    remembered = dict(asset.file_values or {})
    _set_value(asset, field, remembered.pop(field, None))
    asset.file_values = remembered
    asset.edited_fields = [f for f in edited if f != field]


Text300 = Annotated[str, StringConstraints(max_length=300)]
Text200 = Annotated[str, StringConstraints(max_length=200)]


class LocationIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    label: Text200 | None = None


class MetadataEdit(BaseModel):
    """Omitted fields are unchanged; an empty string clears a text field."""

    title: Text300 | None = None
    description: Annotated[str, StringConstraints(max_length=5000)] | None = None
    captured_at: datetime | None = None
    shift_seconds: int | None = Field(default=None, ge=-MAX_SHIFT_SECONDS, le=MAX_SHIFT_SECONDS)
    location: LocationIn | None = None
    clear_location: bool = False
    camera_make: Text200 | None = None
    camera_model: Text200 | None = None
    lens_model: Text200 | None = None
    revert: list[EditableField] = []

    @field_validator("captured_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @model_validator(mode="after")
    def _consistent(self) -> "MetadataEdit":
        if self.captured_at is not None and self.shift_seconds:
            raise ValueError("set the date or shift it, not both")
        if self.location is not None and self.clear_location:
            raise ValueError("set the location or clear it, not both")
        changed = {
            "captured_at": self.captured_at is not None or bool(self.shift_seconds),
            "location": self.location is not None or self.clear_location,
            "camera_make": self.camera_make is not None,
            "camera_model": self.camera_model is not None,
            "lens_model": self.lens_model is not None,
        }
        clash = [f for f in self.revert if changed[f]]
        if clash:
            raise ValueError(f"cannot change and revert the same field: {', '.join(clash)}")
        return self

    def is_empty(self) -> bool:
        return not self.model_dump(exclude_defaults=True)


def _text(value: str) -> str | None:
    return " ".join(value.split()) or None


def apply_edit(asset: MediaAsset, edit: MetadataEdit) -> None:
    for field in edit.revert:
        revert_field(asset, field)
    if edit.title is not None:
        asset.title = _text(edit.title)
    if edit.description is not None:
        asset.description = edit.description.strip() or None
    if edit.captured_at is not None or edit.shift_seconds:
        _mark_edited(asset, "captured_at")
        if edit.captured_at is not None:
            new = edit.captured_at
        else:
            base = asset.captured_at or asset.sort_at
            new = base + timedelta(seconds=edit.shift_seconds or 0)
        asset.captured_at = new
        asset.sort_at = new
    if edit.location is not None:
        _mark_edited(asset, "location")
        asset.latitude = round(edit.location.latitude, 6)
        asset.longitude = round(edit.location.longitude, 6)
        asset.location_source = "manual"
        asset.place_name = _text(edit.location.label or "")
    elif edit.clear_location:
        _mark_edited(asset, "location")
        asset.latitude = asset.longitude = None
        asset.location_source = "cleared"
        asset.place_name = None
    for field in ("camera_make", "camera_model", "lens_model"):
        value = getattr(edit, field)
        if value is not None:
            _mark_edited(asset, field)
            setattr(asset, field, _text(value))
