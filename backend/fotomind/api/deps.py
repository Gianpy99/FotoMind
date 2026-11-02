"""Shared FastAPI dependencies: database session and worker authentication."""

import hmac
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from fotomind.api.auth import CurrentUser, UserDep
from fotomind.config import Settings
from fotomind.infrastructure.db.session import get_engine
from fotomind.modules.storage.thumbnails import ThumbnailStore

WORKER_TOKEN_HEADER = "X-FotoMind-Worker-Token"


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def get_db(settings: SettingsDep) -> Iterator[Session]:
    """One session per request. Endpoints commit explicitly; anything else is rolled back."""
    if settings.database_url is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    factory = sessionmaker(bind=get_engine(settings), expire_on_commit=False)
    with factory() as session:
        yield session


DbDep = Annotated[Session, Depends(get_db)]


def get_thumbnail_store(settings: SettingsDep) -> ThumbnailStore:
    return ThumbnailStore(settings.thumbnails_dir)


ThumbsDep = Annotated[ThumbnailStore, Depends(get_thumbnail_store)]


def require_worker(request: Request, user: UserDep, settings: SettingsDep) -> CurrentUser:
    """Worker endpoints need portal auth (Caddy) plus the shared worker token.

    Without a configured token the endpoints are open to any portal user in development but
    disabled in production.
    """
    token = settings.worker_token
    if token is None:
        if settings.is_production:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Worker access is not configured")
        return user
    supplied = request.headers.get(WORKER_TOKEN_HEADER, "")
    if not hmac.compare_digest(supplied.encode(), token.get_secret_value().encode()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid worker token")
    return user


WorkerDep = Annotated[CurrentUser, Depends(require_worker)]
