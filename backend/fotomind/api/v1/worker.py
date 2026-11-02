"""Endpoints for the PC worker (portal auth + X-FotoMind-Worker-Token).

The worker sends metadata and small JPEG thumbnails only; originals never leave the PC.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select

from fotomind.api.deps import DbDep, SettingsDep, ThumbsDep, WorkerDep
from fotomind.api.v1.schemas import JobOut, StorageRootOut
from fotomind.api.v1.storage import roots_with_counts
from fotomind.application import jobs as job_service
from fotomind.domain.enums import JobStatus, JobType
from fotomind.infrastructure.db.models import Job, MediaAsset, MediaFile, StorageRoot
from fotomind.modules.library.ingest import (
    IngestBatch,
    IngestResult,
    finish_scan,
    ingest_batch,
    mark_root_offline,
)
from fotomind.modules.storage.thumbnails import InvalidThumbnailError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/worker", tags=["worker"])

Host = Annotated[str, StringConstraints(min_length=1, max_length=255, strip_whitespace=True)]


class RegisterRoot(BaseModel):
    host: Host
    path: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    label: Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
    volume_id: Annotated[str, StringConstraints(max_length=64)] | None = None


class KnownFile(BaseModel):
    relative_path: str
    size_bytes: int
    mtime: datetime
    needs_thumbnail: bool


class ClaimRequest(BaseModel):
    host: Host
    worker_id: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    job_types: list[str] | None = None


class ProgressReport(BaseModel):
    worker_id: str
    done: int = Field(ge=0)
    total: int | None = Field(default=None, ge=0)
    message: Annotated[str, StringConstraints(max_length=1000)] | None = None


class ProgressAck(BaseModel):
    cancel_requested: bool


class CompleteReport(BaseModel):
    worker_id: str
    succeeded: bool
    error: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    # The storage root could not be reached (disk unplugged): files become offline, not missing.
    root_offline: bool = False


class ThumbnailStored(BaseModel):
    sha256: str


def _root_or_404(db: DbDep, root_id: uuid.UUID) -> StorageRoot:
    root = db.get(StorageRoot, root_id)
    if root is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Storage root not found")
    return root


def _job_or_404(db: DbDep, job_id: uuid.UUID) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@router.post("/storage-roots", response_model=StorageRootOut)
def register_root(body: RegisterRoot, db: DbDep, _worker: WorkerDep) -> StorageRootOut:
    """Idempotent on (host, path): re-registering updates the label and volume id."""
    root = db.scalar(
        select(StorageRoot).where(StorageRoot.host == body.host, StorageRoot.path == body.path)
    )
    if root is None:
        root = StorageRoot(host=body.host, path=body.path)
        db.add(root)
    root.label = body.label
    root.volume_id = body.volume_id
    db.commit()
    return next(r for r in roots_with_counts(db, body.host) if r.id == root.id)


@router.get("/storage-roots", response_model=list[StorageRootOut])
def list_host_roots(host: str, db: DbDep, _worker: WorkerDep) -> list[StorageRootOut]:
    return roots_with_counts(db, host)


@router.get("/storage-roots/{root_id}/files", response_model=list[KnownFile])
def known_files(root_id: uuid.UUID, db: DbDep, _worker: WorkerDep) -> list[KnownFile]:
    """What the catalogue already knows, so the worker can skip unchanged files."""
    _root_or_404(db, root_id)
    rows = db.execute(
        select(
            MediaFile.relative_path,
            MediaFile.size_bytes,
            MediaFile.mtime,
            MediaAsset.thumbnail_sha256,
        )
        .join(MediaAsset, MediaAsset.id == MediaFile.asset_id)
        .where(MediaFile.storage_root_id == root_id)
    )
    return [
        KnownFile(relative_path=p, size_bytes=s, mtime=m, needs_thumbnail=t is None)
        for p, s, m, t in rows
    ]


@router.post("/storage-roots/{root_id}/ingest", response_model=IngestResult)
def ingest(
    root_id: uuid.UUID, body: IngestBatch, db: DbDep, thumbs: ThumbsDep, _worker: WorkerDep
) -> IngestResult:
    root = _root_or_404(db, root_id)
    result = ingest_batch(db, root, body, datetime.now(UTC))
    db.commit()
    for asset_id in result.orphaned_asset_ids:
        thumbs.delete(asset_id)
    return result


@router.put(
    "/assets/{asset_id}/thumbnail",
    response_model=ThumbnailStored,
    openapi_extra={"requestBody": {"required": True, "content": {"image/jpeg": {"schema": {}}}}},
)
async def upload_thumbnail(
    asset_id: uuid.UUID,
    request: Request,
    db: DbDep,
    thumbs: ThumbsDep,
    settings: SettingsDep,
    _worker: WorkerDep,
) -> ThumbnailStored:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.thumbnail_max_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Thumbnail too large")
    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    data = await request.body()
    try:
        sha = thumbs.save(asset_id, data, settings.thumbnail_max_bytes)
    except InvalidThumbnailError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    asset.thumbnail_sha256 = sha
    db.commit()
    return ThumbnailStored(sha256=sha)


@router.post(
    "/jobs/claim",
    response_model=JobOut,
    responses={204: {"description": "No job available"}},
)
def claim_job(
    body: ClaimRequest, db: DbDep, settings: SettingsDep, _worker: WorkerDep
) -> JobOut | Response:
    job = job_service.claim_next(
        db,
        host=body.host,
        worker_id=body.worker_id,
        now=datetime.now(UTC),
        stale_after=timedelta(seconds=settings.job_stale_after_s),
        job_types=body.job_types,
    )
    if job is None:
        db.rollback()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    db.commit()
    logger.info("job.claimed", extra={"job_id": str(job.id), "worker_id": body.worker_id})
    return JobOut.model_validate(job)


@router.post("/jobs/{job_id}/progress", response_model=ProgressAck)
def job_progress(
    job_id: uuid.UUID, body: ProgressReport, db: DbDep, _worker: WorkerDep
) -> ProgressAck:
    job = _job_or_404(db, job_id)
    try:
        cancel = job_service.report_progress(
            job, body.worker_id, body.done, body.total, body.message, datetime.now(UTC)
        )
    except job_service.JobConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.commit()
    return ProgressAck(cancel_requested=cancel)


@router.post("/jobs/{job_id}/complete", response_model=JobOut)
def job_complete(job_id: uuid.UUID, body: CompleteReport, db: DbDep, _worker: WorkerDep) -> JobOut:
    job = _job_or_404(db, job_id)
    now = datetime.now(UTC)
    result = dict(body.result)
    was_running = job.status == JobStatus.RUNNING
    try:
        job_service.complete(job, body.worker_id, body.succeeded, body.error, result, now)
    except job_service.JobConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    root = db.get(StorageRoot, job.storage_root_id) if job.storage_root_id else None
    if job.job_type == JobType.SCAN_ROOT and root is not None:
        if body.root_offline:
            mark_root_offline(db, root)
        elif was_running and body.succeeded and job.started_at is not None:
            # Only a complete, uncancelled scan may conclude that unseen files are missing.
            result["missing"] = finish_scan(db, root, job.started_at, now)
            job.result = result
    db.commit()
    logger.info(
        "job.finished",
        extra={"job_id": str(job.id), "status": str(job.status), "result": job.result},
    )
    return JobOut.model_validate(job)
