from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fotomind.config import Settings
from fotomind.main import create_app


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_env": "test",
        "database_url": None,
        "dev_user": "dev",
        "web_dist_dir": Path("__no_web_dist__"),
        "log_format": "console",
        "_env_file": None,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.fixture
def app_factory(tmp_path: Path):
    def _make(**overrides: object) -> FastAPI:
        overrides.setdefault("data_dir", tmp_path / "data")
        return create_app(make_settings(**overrides))

    return _make


@pytest.fixture
def client(app_factory) -> TestClient:
    with TestClient(app_factory()) as c:
        yield c


@pytest.fixture
def db_app_factory(tmp_path: Path):
    """App backed by a throwaway SQLite catalogue (schema from the ORM models)."""
    from fotomind.infrastructure.db.base import Base
    from fotomind.infrastructure.db.models import Job  # noqa: F401  (registers tables)
    from fotomind.infrastructure.db.session import get_engine

    def _make(**overrides: object) -> FastAPI:
        overrides.setdefault("data_dir", tmp_path / "data")
        overrides.setdefault("database_url", f"sqlite:///{(tmp_path / 'catalog.db').as_posix()}")
        overrides.setdefault("run_migrations_on_startup", False)
        settings = make_settings(**overrides)
        Base.metadata.create_all(get_engine(settings))
        return create_app(settings)

    return _make


@pytest.fixture
def db_client(db_app_factory) -> TestClient:
    with TestClient(db_app_factory()) as c:
        yield c
