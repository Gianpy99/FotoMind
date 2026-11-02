"""Requires PostgreSQL: set FOTOMIND_TEST_DATABASE_URL (the fotomind_test DB on the Pi).

Never point this at the production database on the Pi.
"""

import os

import pytest
from sqlalchemy import create_engine, inspect, text

from fotomind.infrastructure.db.migrations import alembic_config, upgrade_to_head
from tests.conftest import make_settings

pytestmark = pytest.mark.integration

TEST_DB_URL = os.getenv("FOTOMIND_TEST_DATABASE_URL")


@pytest.mark.skipif(not TEST_DB_URL, reason="FOTOMIND_TEST_DATABASE_URL not set")
def test_upgrade_downgrade_upgrade_cycle() -> None:
    from alembic import command

    settings = make_settings(database_url=TEST_DB_URL)
    cfg = alembic_config(settings)
    upgrade_to_head(settings)
    command.downgrade(cfg, "base")
    upgrade_to_head(settings)
    upgrade_to_head(settings)  # idempotent on every container start

    engine = create_engine(settings.database_url.get_secret_value())  # type: ignore[union-attr]
    with engine.connect() as conn:
        assert "alembic_version" in inspect(conn).get_table_names()
        ext = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")).scalar()
        assert ext == 1
    engine.dispose()
