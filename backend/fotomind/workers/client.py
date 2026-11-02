import httpx

from fotomind.workers.config import WorkerSettings


def api_client(settings: WorkerSettings) -> httpx.Client:
    auth = None
    if settings.api_user and settings.api_password:
        auth = httpx.BasicAuth(settings.api_user, settings.api_password.get_secret_value())
    return httpx.Client(
        base_url=settings.api_url.rstrip("/"),
        auth=auth,
        timeout=settings.request_timeout_s,
        headers={"User-Agent": "fotomind-worker"},
    )
