"""Storage-root scanning on the worker host (PRD 3.4-3.10). Read-only on originals."""

import ctypes
import logging
import os
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fotomind.modules.storage.paths import is_excluded
from fotomind.workers.api import WorkerApi
from fotomind.workers.config import WorkerSettings
from fotomind.workers.media import MediaKind, extract, kind_for, sha256_file

logger = logging.getLogger(__name__)

# Folders that are never photo libraries (Windows system/OneDrive/macOS/Lightroom caches).
_SKIP_DIRS = {"$recycle.bin", "system volume information", "@eadir", ".thumbnails"}
MAX_ERROR_SAMPLES = 20
PROGRESS_EVERY_S = 2.0


def iter_media(
    root: Path, exclude_patterns: Sequence[str] = ()
) -> Iterator[tuple[Path, str, MediaKind]]:
    """Yield (absolute path, POSIX path relative to root, kind) for supported files.

    Symlinks and junctions are not followed, so a scan never leaves the root. Folders and
    files matching the root's exclusion patterns are skipped (LIB-003).
    """
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = sorted(
            d
            for d in dirnames
            if not d.startswith((".", "$"))
            and d.lower() not in _SKIP_DIRS
            and not os.path.islink(current / d)
            and not os.path.isjunction(current / d)
            and not (
                exclude_patterns
                and is_excluded((current / d).relative_to(root).as_posix(), exclude_patterns)
            )
        )
        for name in sorted(filenames):
            if name.startswith((".", "~")):
                continue
            path = current / name
            kind = kind_for(path)
            if kind is None or path.is_symlink():
                continue
            rel = path.relative_to(root).as_posix()
            if exclude_patterns and is_excluded(rel, exclude_patterns):
                continue
            yield path, rel, kind


def volume_id_for(path: Path) -> str | None:
    """Volume serial number on Windows (helps recognise a disk under another letter)."""
    if sys.platform != "win32":
        return None
    drive = path.resolve().anchor
    serial = ctypes.c_uint32()
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(drive), None, 0, ctypes.byref(serial), None, None, None, 0
    )
    return f"{serial.value:08X}" if ok else None


def _mtime(stat: os.stat_result) -> datetime:
    return datetime.fromtimestamp(stat.st_mtime, UTC)


def _same_mtime(known: str, current: datetime) -> bool:
    try:
        parsed = datetime.fromisoformat(known.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return abs((parsed - current).total_seconds()) < 0.001


def _report(rel: str, stat: os.stat_result, sha: str, kind: MediaKind, ex: Any) -> dict:
    return {
        "relative_path": rel,
        "size_bytes": stat.st_size,
        "mtime": _mtime(stat).isoformat(),
        "sha256": sha,
        "mime_type": kind.mime_type,
        "asset_type": kind.asset_type.value,
        "role": kind.role.value,
        "captured_at": ex.captured_at.isoformat() if ex.captured_at else None,
        "width": ex.width,
        "height": ex.height,
        "duration_s": ex.duration_s,
        "camera_make": ex.camera_make,
        "camera_model": ex.camera_model,
        "lens_model": ex.lens_model,
        "metadata": ex.metadata,
    }


class ScanCancelledError(Exception):
    pass


def run_scan_job(
    api: WorkerApi,
    settings: WorkerSettings,
    worker_id: str,
    job: dict,
    echo: Callable[[str], None] = lambda _msg: None,
) -> dict:
    """Scan one storage root and report it. Returns the completed job."""
    job_id = job["id"]
    roots = {r["id"]: r for r in api.list_roots(settings.worker_host)}
    root = roots.get(job.get("storage_root_id") or "")
    if root is None:
        return api.complete(job_id, worker_id, False, error="Storage root not registered here")
    root_path = Path(root["path"])
    if not root_path.is_dir():
        echo(f"  {root['label']}: {root_path} is not reachable, marking it offline")
        return api.complete(
            job_id, worker_id, False, error=f"Not reachable: {root_path}", root_offline=True
        )

    known = {f["relative_path"]: f for f in api.known_files(root["id"])}
    candidates = list(iter_media(root_path, root.get("exclude_patterns") or []))
    total = len(candidates)
    stats: Counter[str] = Counter()
    errors: list[str] = []
    pending: list[tuple[dict, bytes | None]] = []
    unchanged: list[str] = []
    last_progress = 0.0
    echo(f"  {root['label']}: {total} media files under {root_path}")

    def flush() -> None:
        if not pending and not unchanged:
            return
        result = api.ingest(root["id"], [r for r, _ in pending], list(unchanged))
        thumbs = {r["relative_path"]: t for r, t in pending}
        for item in result["files"]:
            thumb = thumbs.get(item["relative_path"])
            if item["needs_thumbnail"] and thumb:
                api.put_thumbnail(item["asset_id"], thumb)
                stats["thumbnails"] += 1
        stats["ingested"] += len(result["files"])
        stats["unchanged"] += result["unchanged_seen"]
        pending.clear()
        unchanged.clear()

    def heartbeat(done: int, force: bool = False) -> None:
        nonlocal last_progress
        if not force and time.monotonic() - last_progress < PROGRESS_EVERY_S:
            return
        last_progress = time.monotonic()
        message = f"{done}/{total} files"
        if api.progress(job_id, worker_id, done, total, message):
            raise ScanCancelledError
        echo(f"  {message}")

    try:
        heartbeat(0, force=True)
        for done, (path, rel, kind) in enumerate(candidates, start=1):
            try:
                stat = path.stat()
            except OSError as exc:
                stats["errors"] += 1
                if len(errors) < MAX_ERROR_SAMPLES:
                    errors.append(f"{rel}: {exc}")
                continue
            prev = known.get(rel)
            if (
                prev is not None
                and prev["size_bytes"] == stat.st_size
                and _same_mtime(prev["mtime"], _mtime(stat))
                and not prev["needs_thumbnail"]
            ):
                unchanged.append(rel)
            else:
                try:
                    sha = sha256_file(path)
                    ex = extract(path, kind, settings.thumbnail_px)
                    pending.append((_report(rel, stat, sha, kind, ex), ex.thumbnail))
                except Exception as exc:
                    # One unreadable file must not stop the scan. A known file that is still
                    # present is reported as seen so it is not marked missing.
                    stats["errors"] += 1
                    if len(errors) < MAX_ERROR_SAMPLES:
                        errors.append(f"{rel}: {type(exc).__name__}: {exc}"[:300])
                    logger.warning("scan.file_failed", extra={"file": rel, "error": str(exc)})
                    if prev is not None:
                        unchanged.append(rel)
            if len(pending) >= settings.batch_size or len(unchanged) >= 1000:
                flush()
            heartbeat(done)
        flush()
        heartbeat(total, force=True)
    except ScanCancelledError:
        echo("  cancelled")
        return api.complete(job_id, worker_id, False, error="Cancelled", result=dict(stats))

    result: dict[str, Any] = {"files": total, **stats}
    if errors:
        result["error_samples"] = errors
    return api.complete(job_id, worker_id, True, result=result)
