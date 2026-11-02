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
