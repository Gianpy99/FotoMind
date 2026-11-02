"""Storage roots and jobs as seen by the user (web UI)."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, StringConstraints, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fotomind.api.auth import UserDep
from fotomind.api.deps import DbDep
from fotomind.api.v1.schemas import JobOut, StorageRootOut
from fotomind.application import jobs as job_service
from fotomind.domain.enums import Availability, JobStatus
from fotomind.infrastructure.db.models import Job, MediaFile, StorageRoot
from fotomind.modules.storage.paths import MAX_EXCLUDE_PATTERNS, normalise_exclude_patterns

router = APIRouter(tags=["storage"])


def roots_with_counts(db: Session, host: str | None = None) -> list[StorageRootOut]:
    query = select(StorageRoot).order_by(StorageRoot.label)
    if host is not None:
        query = query.where(StorageRoot.host == host)
    roots = list(db.scalars(query))
    counts = {
        (root_id, state): n
        for root_id, state, n in db.execute(
            select(MediaFile.storage_root_id, MediaFile.availability, func.count())
            .where(MediaFile.storage_root_id.in_([r.id for r in roots]))
            .group_by(MediaFile.storage_root_id, MediaFile.availability)
        )
    }
    out = []
    for root in roots:
        item = StorageRootOut.model_validate(root)
        item.file_count = sum(n for (rid, _), n in counts.items() if rid == root.id)
        item.missing_count = counts.get((root.id, Availability.MISSING), 0)
        out.append(item)
    return out


@router.get("/storage-roots", response_model=list[StorageRootOut])
def list_roots(db: DbDep, _user: UserDep) -> list[StorageRootOut]:
    """Folders registered by worker hosts (``fotomind-worker roots add`` on the PC)."""
    return roots_with_counts(db)


class StorageRootUpdate(BaseModel):
    """Fields left out are unchanged. Exclusions apply from the next scan (LIB-003)."""

    label: (
        Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
        | None
    ) = None
    exclude_patterns: Annotated[list[str], Field(max_length=MAX_EXCLUDE_PATTERNS * 2)] | None = None

    @field_validator("exclude_patterns")
    @classmethod
    def _patterns(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else normalise_exclude_patterns(value)


@router.patch("/storage-roots/{root_id}", response_model=StorageRootOut)
def update_root(
    root_id: uuid.UUID, body: StorageRootUpdate, db: DbDep, _user: UserDep
) -> StorageRootOut:
    root = db.get(StorageRoot, root_id)
    if root is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Storage root not found")
    if body.label is not None:
        root.label = body.label
    if body.exclude_patterns is not None:
        root.exclude_patterns = body.exclude_patterns
    db.commit()
    return next(r for r in roots_with_counts(db) if r.id == root.id)


@router.post(
    "/storage-roots/{root_id}/scan", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED
)
def scan_root(root_id: uuid.UUID, db: DbDep, user: UserDep) -> JobOut:
    """Queue a scan; the worker on the root's host picks it up. Idempotent while active."""
    root = db.get(StorageRoot, root_id)
    if root is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Storage root not found")
    job = job_service.queue_scan(db, root, requested_by=user.username)
    db.commit()
    return JobOut.model_validate(job)


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    db: DbDep,
    _user: UserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    active_only: bool = False,
) -> list[JobOut]:
    query = select(Job).order_by(Job.created_at.desc()).limit(limit)
    if active_only:
        query = query.where(Job.status.in_(job_service.ACTIVE))
    return [JobOut.model_validate(j) for j in db.scalars(query)]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, db: DbDep, _user: UserDep) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return JobOut.model_validate(job)


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: uuid.UUID, db: DbDep, _user: UserDep) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
        raise HTTPException(status.HTTP_409_CONFLICT, "Job is already finished")
    job_service.cancel(job, datetime.now(UTC))
    db.commit()
    return JobOut.model_validate(job)
