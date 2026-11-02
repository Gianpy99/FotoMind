"""Thumbnail cache on the API host (Pi data volume). Originals never leave the worker host."""

import hashlib
import os
import uuid
from pathlib import Path

JPEG_MAGIC = b"\xff\xd8\xff"


class InvalidThumbnailError(ValueError):
    pass


class ThumbnailStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, asset_id: uuid.UUID) -> Path:
        name = asset_id.hex
        return self.root / name[:2] / f"{name}.jpg"

    def save(self, asset_id: uuid.UUID, data: bytes, max_bytes: int) -> str:
        """Atomically store a JPEG thumbnail and return its SHA-256."""
        if not data or len(data) > max_bytes:
            raise InvalidThumbnailError(f"thumbnail must be 1..{max_bytes} bytes")
        if not data.startswith(JPEG_MAGIC):
            raise InvalidThumbnailError("thumbnail must be a JPEG")
        target = self.path_for(asset_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)
        return hashlib.sha256(data).hexdigest()

    def delete(self, asset_id: uuid.UUID) -> None:
        self.path_for(asset_id).unlink(missing_ok=True)
