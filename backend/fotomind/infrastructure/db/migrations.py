import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from fotomind.config import Settings

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"


def alembic_config(settings: Settings) -> Config:
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is not configured")
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(REPO_ROOT / "database" / "migrations"))
    # Passed via attributes, not set_main_option, so the URL is never written into ini
    # interpolation (passwords may contain '%').
    cfg.attributes["database_url"] = settings.database_url.get_secret_value()
    cfg.attributes["configure_logger"] = False
    return cfg


def upgrade_to_head(settings: Settings) -> None:
    """Idempotent: safe to run on every container start (FamilyPortal convention)."""
    logger.info("db.migrate.start")
    command.upgrade(alembic_config(settings), "head")
    logger.info("db.migrate.done")
