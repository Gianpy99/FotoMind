from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from fotomind import __version__
from fotomind.api.auth import UserDep
from fotomind.config import Settings
from fotomind.infrastructure.db.health import DatabaseHealth, check_database

# Mounted at the root: GET /health is the FamilyPortal contract (Jenkins + dashboard probe).
portal_router = APIRouter(tags=["health"])
router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    version: str


class SystemStatusResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    database: DatabaseHealth


def _db_ok(db: DatabaseHealth, settings: Settings) -> bool:
    # Without a DATABASE_URL (local dev/tests) the API itself is still considered healthy;
    # in production a missing database is a failure.
    return db.status == "ok" or (db.status == "unconfigured" and not settings.is_production)


@portal_router.get("/health", response_model=HealthResponse)
def portal_health(request: Request, response: Response) -> HealthResponse:
    """200 only when the app and its database are usable. No login required."""
    settings: Settings = request.app.state.settings
    if _db_ok(check_database(settings), settings):
        return HealthResponse(status="ok", version=__version__)
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="unavailable", version=__version__)


@router.get("/health", response_model=HealthResponse)
def liveness() -> HealthResponse:
    """Liveness only: the API process is up. Does not touch external dependencies."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/system/status", response_model=SystemStatusResponse)
def system_status(request: Request, _user: UserDep) -> SystemStatusResponse:
    settings: Settings = request.app.state.settings
    db = check_database(settings)
    return SystemStatusResponse(
        status="ok" if db.status == "ok" else "degraded",
        version=__version__,
        environment=settings.app_env,
        database=db,
    )
