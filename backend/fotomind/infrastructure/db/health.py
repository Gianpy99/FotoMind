import logging
import time
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import text

from fotomind.config import Settings
from fotomind.infrastructure.db.session import get_engine

logger = logging.getLogger(__name__)


class DatabaseHealth(BaseModel):
    status: Literal["ok", "unconfigured", "unavailable"]
    latency_ms: float | None = None
    server_version: str | None = None
    detail: str | None = None


def check_database(settings: Settings) -> DatabaseHealth:
    if settings.database_url is None:
        return DatabaseHealth(status="unconfigured", detail="FOTOMIND_DATABASE_URL is not set")
    started = time.perf_counter()
    try:
        with get_engine(settings).connect() as conn:
            version = conn.execute(text("SHOW server_version")).scalar_one()
    except Exception as exc:
        # Exception type only: driver messages can include host/user details.
        logger.warning("db.health.failed", extra={"error_type": type(exc).__name__})
        return DatabaseHealth(status="unavailable", detail=type(exc).__name__)
    return DatabaseHealth(
        status="ok",
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        server_version=str(version),
    )
