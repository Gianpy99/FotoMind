from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """API configuration from environment variables (or a local .env file).

    Variable names follow the FamilyPortal hosting standard (APP_ENV, PORT, DATABASE_URL,
    DATA_DIR, DEV_USER) so the same image runs on the PC and on the Pi. Secrets are injected
    by Jenkins credentials in production and must never be committed.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"

    # Inside the container the API listens on 0.0.0.0:8000; the host side is bound to
    # 127.0.0.1 so only Caddy can reach it. Locally we default to localhost.
    host: str = "127.0.0.1"
    port: int = 8000

    # Accepts the portal form postgres://user:pw@host:port/db and normalises it for psycopg 3.
    database_url: SecretStr | None = None
    database_connect_timeout_s: int = 5
    run_migrations_on_startup: bool = True

    # Persistent data (thumbnails/previews cache, manifests). /app/data in the container.
    data_dir: Path = Path("./.data")

    # Shared secret the PC worker sends as X-FotoMind-Worker-Token, on top of portal auth.
    # Required in production (worker endpoints are disabled without it); optional elsewhere.
    worker_token: SecretStr | None = None
    # A worker holding a job longer than this without a heartbeat loses it to the next claim.
    job_stale_after_s: int = 900
    thumbnail_max_bytes: int = 2 * 1024 * 1024

    # Local stand-in for the portal Remote-User header; ignored when APP_ENV=production.
    dev_user: str | None = "dev"

    # Built web UI served by the API at "/" (single container, single port).
    web_dist_dir: Path = Path("./apps/web/dist")

    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:1420",
        "tauri://localhost",
        "http://tauri.localhost",
    ]

    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def thumbnails_dir(self) -> Path:
        return self.data_dir / "thumbnails"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @field_validator("worker_token", mode="before")
    @classmethod
    def _blank_token_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalise_db_url(cls, value: object) -> object:
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        if isinstance(value, str):
            if not value.strip():
                return None
            for prefix in ("postgres://", "postgresql://"):
                if value.startswith(prefix):
                    return "postgresql+psycopg://" + value[len(prefix) :]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
