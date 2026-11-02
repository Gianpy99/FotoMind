"""Serve the built React web UI from the API (one container, one port, served from "/")."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

_RESERVED_PREFIXES = ("api/", "health")


def mount_web_ui(app: FastAPI, dist_dir: Path) -> bool:
    index = dist_dir / "index.html"
    if not index.is_file():
        return False
    root = dist_dir.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith(_RESERVED_PREFIXES):
            raise HTTPException(status_code=404)
        candidate = (root / path).resolve()
        # Only serve files inside dist/; anything else falls back to the SPA entry point.
        if path and candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return True
