"""Path rules for media stored relative to a storage root (PRD 3.3, ADR-0002)."""

import posixpath
import re

_DRIVE = re.compile(r"^[A-Za-z]:")
MAX_RELATIVE_PATH = 4096


class UnsafePathError(ValueError):
    pass


def normalise_relative_path(value: str) -> str:
    """Return a canonical POSIX relative path, or raise if it could escape the root.

    Backslashes are accepted (Windows workers) and converted. Absolute paths, drive letters,
    UNC prefixes, ``..`` segments, NUL bytes and empty paths are rejected.
    """
    if not value or len(value) > MAX_RELATIVE_PATH or "\x00" in value:
        raise UnsafePathError("invalid relative path")
    path = value.replace("\\", "/")
    if path.startswith("/") or _DRIVE.match(path):
        raise UnsafePathError("path must be relative to the storage root")
    parts = [p for p in path.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise UnsafePathError("path must stay inside the storage root")
    return posixpath.join(*parts)
