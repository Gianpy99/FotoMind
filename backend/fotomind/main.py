import json
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fotomind import __version__
from fotomind.api.v1 import health
from fotomind.api.v1 import router as v1_router
from fotomind.api.web import mount_web_ui
from fotomind.config import Settings, get_settings
from fotomind.logging_config import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        if settings.database_url is not None and settings.run_migrations_on_startup:
            from fotomind.infrastructure.db.migrations import upgrade_to_head

            upgrade_to_head(settings)
        logger.info("api.started", extra={"environment": settings.app_env, "version": __version__})
        yield

    app = FastAPI(
        title="FotoMind API",
        version=__version__,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.portal_router)
    app.include_router(v1_router, prefix="/api/v1")
    # Last: catch-all route for the SPA.
    mount_web_ui(app, settings.web_dist_dir)
    return app


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "fotomind.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


def export_openapi() -> None:
    """Write the OpenAPI contract used to generate the shared TypeScript client."""
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("packages/api-client/openapi.json")
    app = create_app(Settings(database_url=None, web_dist_dir=Path("__none__")))
    out.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"OpenAPI schema written to {out}")
