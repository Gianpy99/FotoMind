import socket
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
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
    # Must match WORKER_TOKEN on the API (Jenkins credential fotomind-worker-token in prod).
    worker_token: SecretStr | None = None
    request_timeout_s: float = 30.0

    # Name of this machine in storage_root.host / job.host; roots are scanned only here.
    worker_host: str = Field(default_factory=socket.gethostname)
    thumbnail_px: int = Field(default=512, ge=128, le=1024)
    batch_size: int = Field(default=50, ge=1, le=500)
    poll_interval_s: float = 10.0

    # Working files on the PC's NVMe (PRD 7.1). Originals are never written.
    cache_dir: Path = Path("./.data/worker-cache")

    @field_validator("api_password", "worker_token", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()
