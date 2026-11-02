from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from fotomind.config import Settings


@lru_cache(maxsize=4)
def _engine_for(url: str, connect_timeout_s: int) -> Engine:
    if url.startswith("sqlite"):
        # Unit tests only; the API threadpool shares the connection pool.
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": connect_timeout_s},
    )


def get_engine(settings: Settings) -> Engine:
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is not configured")
    return _engine_for(
        settings.database_url.get_secret_value(), settings.database_connect_timeout_s
    )


def session_scope(settings: Settings) -> Iterator[Session]:
    """Transactional unit of work: commit on success, roll back on error."""
    factory = sessionmaker(bind=get_engine(settings), expire_on_commit=False)
    with factory() as session, session.begin():
        yield session
