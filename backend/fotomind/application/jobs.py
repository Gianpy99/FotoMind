"""Job queue backed by PostgreSQL (ADR-0001): the Pi stores jobs, PC workers claim and run them."""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from fotomind.domain.enums import JobStatus, JobType
from fotomind.infrastructure.db.models import Job, StorageRoot

ACTIVE = (JobStatus.QUEUED, JobStatus.RUNNING)


class JobConflictError(Exception):
    """The job is not (or no longer) owned by the calling worker."""


def queue_scan(session: Session, root: StorageRoot, requested_by: str | None) -> Job:
    """Queue a scan of ``root`` unless one is already queued or running (idempotent)."""
    existing = session.scalar(
        select(Job)
        .where(
            Job.storage_root_id == root.id,
            Job.job_type == JobType.SCAN_ROOT,
            Job.status.in_(ACTIVE),
        )
        .order_by(Job.created_at)
        .limit(1)
    )
    if existing is not None:
        return existing
    job = Job(
        job_type=JobType.SCAN_ROOT,
        status=JobStatus.QUEUED,
        host=root.host,
        storage_root_id=root.id,
        params={},
        result={},
        progress_done=0,
        attempts=0,
        requested_by=requested_by,
    )
    session.add(job)
    session.flush()
    return job


def claim_next(
    session: Session,
    host: str,
    worker_id: str,
    now: datetime,
    stale_after: timedelta,
    job_types: list[str] | None = None,
) -> Job | None:
    """Atomically hand the oldest runnable job for ``host`` to ``worker_id``.

    Running jobs whose heartbeat is older than ``stale_after`` are re-claimed, so a crashed or
    rebooted PC resumes its work (scans are idempotent).
    """
    query = (
        select(Job)
        .where(
            Job.host == host,
            or_(
                Job.status == JobStatus.QUEUED,
                (Job.status == JobStatus.RUNNING) & (Job.heartbeat_at < now - stale_after),
            ),
        )
        .order_by(Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job_types:
        query = query.where(Job.job_type.in_(job_types))
    job = session.scalar(query)
    if job is None:
        return None
    job.status = JobStatus.RUNNING
    job.worker_id = worker_id
    job.attempts += 1
    job.started_at = now
    job.heartbeat_at = now
    job.progress_done = 0
    job.progress_total = None
    job.message = None
    job.error = None
    session.flush()
    return job


def _owned(job: Job, worker_id: str) -> None:
    if job.worker_id != worker_id or job.status not in (JobStatus.RUNNING, JobStatus.CANCELLED):
        raise JobConflictError("job is not running for this worker")


def report_progress(
    job: Job, worker_id: str, done: int, total: int | None, message: str | None, now: datetime
) -> bool:
    """Record a heartbeat. Returns True when the job was cancelled and the worker should stop."""
    _owned(job, worker_id)
    if job.status == JobStatus.CANCELLED:
        return True
    job.progress_done = done
    job.progress_total = total
    job.message = message
    job.heartbeat_at = now
    return False


def complete(
    job: Job,
    worker_id: str,
    succeeded: bool,
    error: str | None,
    result: dict[str, Any],
    now: datetime,
) -> None:
    _owned(job, worker_id)
    if job.status == JobStatus.RUNNING:
        job.status = JobStatus.SUCCEEDED if succeeded else JobStatus.FAILED
    job.error = None if succeeded else (error or "failed")[:4000]
    job.result = result
    job.heartbeat_at = now
    job.finished_at = now


def cancel(job: Job, now: datetime) -> None:
    if job.status in ACTIVE:
        job.status = JobStatus.CANCELLED
        job.finished_at = now


def get_job(session: Session, job_id: uuid.UUID) -> Job | None:
    return session.get(Job, job_id)
