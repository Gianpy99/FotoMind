"""Shared vocabulary from the PRD. Values are persisted, so never rename existing members."""

from enum import StrEnum


class AssetType(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"


class MediaFileRole(StrEnum):
    ORIGINAL = "original"
    RAW_ORIGINAL = "raw_original"
    JPEG_SIDECAR = "jpeg_sidecar"
    THUMBNAIL = "thumbnail"
    PREVIEW = "preview"
    POSTER_FRAME = "poster_frame"
    EDITED_EXPORT = "edited_export"
    AI_DERIVATIVE = "ai_derivative"


class Availability(StrEnum):
    """LIB-009 / STO-002: unavailable (offline root) is distinct from missing/deleted."""

    ONLINE = "online"
    OFFLINE = "offline"
    MISSING = "missing"


class BackupState(StrEnum):
    """STO-007: success is never inferred from file existence alone."""

    UNKNOWN = "unknown"
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    STALE = "stale"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReviewStatus(StrEnum):
    """Human review for AI outputs and face detections; no silent acceptance."""

    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNKNOWN = "unknown"
    NOT_A_FACE = "not_a_face"


class ProcessingLocation(StrEnum):
    LOCAL = "local"
    CLOUD = "cloud"
