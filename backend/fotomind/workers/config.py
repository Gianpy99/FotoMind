from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """Worker configuration (FOTOMIND_* variables, or .env on the Windows PC)."""

    model_config = SettingsConfigDict(
        env_prefix="FOTOMIND_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Production: the portal URL. Local development: http://localhost:8000.
    api_url: str = "http://localhost:8000"
    # Portal (Caddy basic auth) credentials; Caddy turns them into Remote-User for the API.
    api_user: str | None = None
    api_password: SecretStr | None = None
    request_timeout_s: float = 30.0

    # Working files on the PC's NVMe (PRD 7.1). Originals are never written.
    cache_dir: Path = Path("./.data/worker-cache")


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()
