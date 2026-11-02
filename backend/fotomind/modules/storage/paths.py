"""Path rules for media stored relative to a storage root (PRD 3.3, ADR-0002)."""

import posixpath
import re
from collections.abc import Iterable
from fnmatch import fnmatchcase

_DRIVE = re.compile(r"^[A-Za-z]:")
MAX_RELATIVE_PATH = 4096
MAX_EXCLUDE_PATTERNS = 100
MAX_EXCLUDE_PATTERN_LENGTH = 200


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


def normalise_exclude_patterns(patterns: Iterable[str]) -> list[str]:
    """Validate and canonicalise exclusion globs: trimmed, ``/`` separated, de-duplicated."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in patterns:
        pattern = raw.strip().replace("\\", "/").strip("/")
        if not pattern:
            continue
        if len(pattern) > MAX_EXCLUDE_PATTERN_LENGTH or "\x00" in pattern:
            raise ValueError(f"exclusion pattern too long: {pattern[:40]}")
        if ".." in pattern.split("/"):
            raise ValueError("exclusion patterns cannot contain '..'")
        if pattern.lower() not in seen:
            seen.add(pattern.lower())
            out.append(pattern)
    if len(out) > MAX_EXCLUDE_PATTERNS:
        raise ValueError(f"at most {MAX_EXCLUDE_PATTERNS} exclusion patterns")
    return out


def is_excluded(relative_path: str, patterns: Iterable[str]) -> bool:
    """Whether a root-relative POSIX path is skipped by the root's exclusion rules (LIB-003).

    Matching is case-insensitive. A pattern without ``/`` (``@eaDir``, ``*.tmp``) matches any
    single path component, so it excludes matching folders anywhere and everything below
    them. A pattern with ``/`` (``Private/2019*``) matches from the root; it excludes the
    matching folder or file and everything below it.
    """
    parts = relative_path.lower().split("/")
    for raw in patterns:
        pattern = raw.lower()
        if "/" not in pattern:
            if any(fnmatchcase(part, pattern) for part in parts):
                return True
            continue
        depth = pattern.count("/") + 1
        if len(parts) >= depth and fnmatchcase("/".join(parts[:depth]), pattern):
            return True
    return False
