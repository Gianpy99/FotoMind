"""Metadata extraction and thumbnail rendering on the worker host (PRD 3.8, 3.9).

Originals are opened read-only and never modified. Heavy imaging libraries (Pillow, rawpy,
exifread, PyAV) are imported lazily so the API image does not need them.
"""

import hashlib
import io
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fotomind.domain.enums import AssetType, MediaFileRole

logger = logging.getLogger(__name__)

MetadataValue = str | int | float | bool | None


@dataclass(frozen=True)
class MediaKind:
    mime_type: str
    asset_type: AssetType
    role: MediaFileRole
    family: str  # "image" | "raw" | "video"


SUPPORTED: dict[str, MediaKind] = {
    ".jpg": MediaKind("image/jpeg", AssetType.PHOTO, MediaFileRole.ORIGINAL, "image"),
    ".jpeg": MediaKind("image/jpeg", AssetType.PHOTO, MediaFileRole.ORIGINAL, "image"),
    ".png": MediaKind("image/png", AssetType.PHOTO, MediaFileRole.ORIGINAL, "image"),
    ".tif": MediaKind("image/tiff", AssetType.PHOTO, MediaFileRole.ORIGINAL, "image"),
    ".tiff": MediaKind("image/tiff", AssetType.PHOTO, MediaFileRole.ORIGINAL, "image"),
    ".cr2": MediaKind("image/x-canon-cr2", AssetType.PHOTO, MediaFileRole.RAW_ORIGINAL, "raw"),
    ".cr3": MediaKind("image/x-canon-cr3", AssetType.PHOTO, MediaFileRole.RAW_ORIGINAL, "raw"),
    ".arw": MediaKind("image/x-sony-arw", AssetType.PHOTO, MediaFileRole.RAW_ORIGINAL, "raw"),
    ".mp4": MediaKind("video/mp4", AssetType.VIDEO, MediaFileRole.ORIGINAL, "video"),
    ".mov": MediaKind("video/quicktime", AssetType.VIDEO, MediaFileRole.ORIGINAL, "video"),
}


def kind_for(path: Path) -> MediaKind | None:
    return SUPPORTED.get(path.suffix.lower())


@dataclass
class Extracted:
    captured_at: datetime | None = None
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    lens_model: str | None = None
    metadata: dict[str, MetadataValue] = field(default_factory=dict)
    thumbnail: bytes | None = None


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def clean_text(value: Any, limit: int = 200) -> str | None:
    """EXIF strings often carry NUL padding, which PostgreSQL JSON/text rejects."""
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value).replace("\x00", "").strip()
    return text[:limit] or None


def _to_float(value: Any) -> float | None:
    try:
        if isinstance(value, list | tuple):
            value = value[0]
        if hasattr(value, "num") and hasattr(value, "den"):
            return None if value.den == 0 else value.num / value.den
        result = float(value)
    except (TypeError, ValueError, ZeroDivisionError, IndexError):
        return None
    return result if result == result else None  # NaN guard


def _exposure_text(value: Any) -> str | None:
    seconds = _to_float(value)
    if not seconds or seconds <= 0:
        return None
    if seconds < 1:
        return f"1/{round(1 / seconds)}"
    return f"{seconds:g}"


def parse_exif_datetime(value: Any, offset: Any = None) -> tuple[datetime | None, bool]:
    """Returns (datetime, tz_known). Without an offset tag, the PC's local zone is assumed."""
    text = clean_text(value, 40)
    if not text:
        return None, False
    try:
        naive = datetime.strptime(text[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None, False
    off = clean_text(offset, 10)
    if off and len(off) >= 6 and off[0] in "+-":
        try:
            hours, minutes = int(off[1:3]), int(off[4:6])
            delta = timedelta(hours=hours, minutes=minutes)
            tz = timezone(delta if off[0] == "+" else -delta)
            return naive.replace(tzinfo=tz), True
        except ValueError:
            pass
    return naive.astimezone(), False


def _apply_exif_fields(out: Extracted, fields: dict[str, Any]) -> None:
    captured, tz_known = parse_exif_datetime(fields.get("datetime"), fields.get("offset"))
    if captured is not None:
        out.captured_at = captured
        out.metadata["captured_tz_known"] = tz_known
    out.camera_make = clean_text(fields.get("make")) or out.camera_make
    out.camera_model = clean_text(fields.get("model")) or out.camera_model
    out.lens_model = clean_text(fields.get("lens")) or out.lens_model
    f_number = _to_float(fields.get("f_number"))
    if f_number:
        out.metadata["f_number"] = round(f_number, 1)
    exposure = _exposure_text(fields.get("exposure"))
    if exposure:
        out.metadata["exposure_time"] = exposure
    iso = _to_float(fields.get("iso"))
    if iso:
        out.metadata["iso"] = int(iso)
    focal = _to_float(fields.get("focal"))
    if focal:
        out.metadata["focal_length_mm"] = round(focal, 1)


def _pillow_exif_fields(exif: Any) -> dict[str, Any]:
    from PIL import ExifTags

    sub = exif.get_ifd(ExifTags.IFD.Exif)
    return {
        "datetime": sub.get(36867) or sub.get(36868) or exif.get(306),
        "offset": sub.get(36881) or sub.get(36880) or sub.get(36882),
        "make": exif.get(271),
        "model": exif.get(272),
        "lens": sub.get(42036),
        "f_number": sub.get(33437),
        "exposure": sub.get(33434),
        "iso": sub.get(34855),
        "focal": sub.get(37386),
    }


def render_thumbnail(img: Any, size_px: int) -> bytes:
    from PIL import Image

    if img.mode in ("I", "F") or img.mode.startswith("I;16"):
        # 16-bit / float greyscale (scanned TIFFs): scale to 8 bits instead of clipping to white.
        low, high = img.convert("F").getextrema()
        scale = 255.0 / (high - low) if high > low else 1.0
        img = img.convert("F").point(lambda v: (v - low) * scale).convert("L")
    if img.mode in ("RGBA", "LA", "P", "PA"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.getchannel("A"))
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((size_px, size_px), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    return buf.getvalue()


def _extract_image(path: Path, size_px: int) -> Extracted:
    from PIL import Image, ImageOps

    out = Extracted()
    with Image.open(path) as img:
        exif = img.getexif()
        _apply_exif_fields(out, _pillow_exif_fields(exif))
        orientation = exif.get(274, 1)
        width, height = img.size
        if orientation in (5, 6, 7, 8):
            width, height = height, width
        out.width, out.height = width, height
        if orientation != 1:
            out.metadata["orientation"] = int(orientation)
        try:
            if img.format == "JPEG":
                img.draft("RGB", (size_px * 2, size_px * 2))
            out.thumbnail = render_thumbnail(ImageOps.exif_transpose(img), size_px)
        except (OSError, ValueError) as exc:
            logger.warning("thumbnail.failed", extra={"file": path.name, "error": str(exc)})
    return out


_RAW_FLIP_TO_PIL_ROTATION = {3: 180, 5: 90, 6: 270}


def _extract_raw(path: Path, size_px: int) -> Extracted:
    import rawpy
    from PIL import Image

    out = Extracted()
    with rawpy.imread(str(path)) as raw:
        sizes = raw.sizes
        width, height = sizes.width, sizes.height
        if sizes.flip in (5, 6):
            width, height = height, width
        out.width, out.height = int(width), int(height)

        img = None
        jpeg_bytes = None
        try:
            thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                jpeg_bytes = bytes(thumb.data)
                img = Image.open(io.BytesIO(jpeg_bytes))
            elif thumb.format == rawpy.ThumbFormat.BITMAP:
                img = Image.fromarray(thumb.data)
            rotation = _RAW_FLIP_TO_PIL_ROTATION.get(sizes.flip)
            if img is not None and rotation:
                img = img.rotate(rotation, expand=True)
        except (rawpy.LibRawNoThumbnailError, rawpy.LibRawUnsupportedThumbnailError):
            img = None
        if img is None:
            # No usable embedded preview: demosaic at half size (LibRaw applies the flip).
            img = Image.fromarray(raw.postprocess(half_size=True, use_camera_wb=True))
        out.thumbnail = render_thumbnail(img, size_px)

    fields = _exifread_fields(path)
    if fields.get("datetime") is None and jpeg_bytes:
        # CR3 and some bodies: fall back to the EXIF of the embedded preview.
        with Image.open(io.BytesIO(jpeg_bytes)) as preview:
            fields = {k: v for k, v in _pillow_exif_fields(preview.getexif()).items() if v} | {
                k: v for k, v in fields.items() if v
            }
    _apply_exif_fields(out, fields)
    return out


def _exifread_fields(path: Path) -> dict[str, Any]:
    import exifread

    try:
        with path.open("rb") as fh:
            tags = exifread.process_file(fh, details=False)
    except Exception as exc:  # exifread raises assorted errors on unknown containers
        logger.debug("exifread.failed", extra={"file": path.name, "error": str(exc)})
        return {}

    def get(*names: str) -> Any:
        for name in names:
            tag = tags.get(name)
            if tag is not None:
                values = getattr(tag, "values", None)
                if isinstance(values, list) and values and not isinstance(values, str):
                    return values[0] if len(values) == 1 else values
                return values if values is not None else str(tag)
        return None

    return {
        "datetime": get("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"),
        "offset": get("EXIF OffsetTimeOriginal", "EXIF OffsetTime"),
        "make": get("Image Make"),
        "model": get("Image Model"),
        "lens": get("EXIF LensModel"),
        "f_number": get("EXIF FNumber"),
        "exposure": get("EXIF ExposureTime"),
        "iso": get("EXIF ISOSpeedRatings", "EXIF PhotographicSensitivity"),
        "focal": get("EXIF FocalLength"),
    }


def _parse_video_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    # 1904/1970 epochs are what cameras write when the clock was never set.
    if parsed.year < 1980:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _extract_video(path: Path, size_px: int) -> Extracted:
    import av

    out = Extracted()
    with av.open(str(path)) as container:
        meta = {k.lower(): v for k, v in container.metadata.items()}
        if container.duration:
            out.duration_s = round(container.duration / 1_000_000, 3)
        out.captured_at = _parse_video_time(
            meta.get("com.apple.quicktime.creationdate") or meta.get("creation_time")
        )
        out.camera_make = clean_text(meta.get("com.apple.quicktime.make") or meta.get("make"))
        out.camera_model = clean_text(meta.get("com.apple.quicktime.model") or meta.get("model"))

        stream = next(iter(container.streams.video), None)
        if stream is None:
            return out
        out.width = stream.codec_context.width or None
        out.height = stream.codec_context.height or None
        codec = clean_text(stream.codec_context.name, 40)
        if codec:
            out.metadata["video_codec"] = codec
        if stream.average_rate:
            out.metadata["fps"] = round(float(stream.average_rate), 2)
        if container.bit_rate:
            out.metadata["bitrate_kbps"] = round(container.bit_rate / 1000)
        audio = next(iter(container.streams.audio), None)
        out.metadata["has_audio"] = audio is not None
        if audio is not None:
            audio_codec = clean_text(audio.codec_context.name, 40)
            if audio_codec:
                out.metadata["audio_codec"] = audio_codec
            channels = getattr(audio.codec_context, "channels", None)
            if channels:
                out.metadata["audio_channels"] = int(channels)

        target = min(1.0, (out.duration_s or 0) * 0.1)
        if target > 0 and stream.time_base:
            container.seek(int(target / stream.time_base), stream=stream)
        for frame in container.decode(stream):
            img = frame.to_image()
            # Display-matrix rotation, counter-clockwise degrees (PIL.rotate is also CCW).
            rotation = int(getattr(frame, "rotation", 0) or 0)
            if rotation % 360:
                img = img.rotate(rotation, expand=True)
                if rotation % 180 and out.width and out.height:
                    out.width, out.height = out.height, out.width
            out.thumbnail = render_thumbnail(img, size_px)
            break
    return out


def extract(path: Path, kind: MediaKind, size_px: int = 512) -> Extracted:
    if kind.family == "raw":
        return _extract_raw(path, size_px)
    if kind.family == "video":
        return _extract_video(path, size_px)
    return _extract_image(path, size_px)
