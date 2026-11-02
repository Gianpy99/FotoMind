"""Typed wrapper over the FotoMind API endpoints the worker uses."""

from typing import Any

import httpx


class WorkerApi:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def _json(self, resp: httpx.Response) -> Any:
        if resp.is_error:
            detail = resp.text[:300]
            raise httpx.HTTPStatusError(
                f"{resp.request.method} {resp.request.url.path} -> {resp.status_code}: {detail}",
                request=resp.request,
                response=resp,
            )
        return resp.json() if resp.content else None

    def register_root(self, host: str, path: str, label: str, volume_id: str | None) -> dict:
        body = {"host": host, "path": path, "label": label, "volume_id": volume_id}
        return self._json(self.client.post("/api/v1/worker/storage-roots", json=body))

    def list_roots(self, host: str) -> list[dict]:
        resp = self.client.get("/api/v1/worker/storage-roots", params={"host": host})
        return self._json(resp)

    def known_files(self, root_id: str) -> list[dict]:
        return self._json(self.client.get(f"/api/v1/worker/storage-roots/{root_id}/files"))

    def ingest(self, root_id: str, files: list[dict], unchanged: list[str]) -> dict:
        body = {"files": files, "unchanged": unchanged}
        resp = self.client.post(f"/api/v1/worker/storage-roots/{root_id}/ingest", json=body)
        return self._json(resp)

    def put_thumbnail(self, asset_id: str, data: bytes) -> None:
        resp = self.client.put(
            f"/api/v1/worker/assets/{asset_id}/thumbnail",
            content=data,
            headers={"Content-Type": "image/jpeg"},
        )
        self._json(resp)

    def queue_scan(self, root_id: str) -> dict:
        return self._json(self.client.post(f"/api/v1/storage-roots/{root_id}/scan"))

    def claim(self, host: str, worker_id: str) -> dict | None:
        resp = self.client.post(
            "/api/v1/worker/jobs/claim", json={"host": host, "worker_id": worker_id}
        )
        if resp.status_code == httpx.codes.NO_CONTENT:
            return None
        return self._json(resp)

    def progress(
        self, job_id: str, worker_id: str, done: int, total: int | None, message: str | None
    ) -> bool:
        body = {"worker_id": worker_id, "done": done, "total": total, "message": message}
        resp = self.client.post(f"/api/v1/worker/jobs/{job_id}/progress", json=body)
        return bool(self._json(resp)["cancel_requested"])

    def complete(
        self,
        job_id: str,
        worker_id: str,
        succeeded: bool,
        error: str | None = None,
        result: dict | None = None,
        root_offline: bool = False,
    ) -> dict:
        body = {
            "worker_id": worker_id,
            "succeeded": succeeded,
            "error": error,
            "result": result or {},
            "root_offline": root_offline,
        }
        return self._json(self.client.post(f"/api/v1/worker/jobs/{job_id}/complete", json=body))
