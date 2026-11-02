import httpx

from fotomind.workers.config import WorkerSettings

WORKER_TOKEN_HEADER = "X-FotoMind-Worker-Token"


def api_client(settings: WorkerSettings) -> httpx.Client:
    auth = None
    if settings.api_user and settings.api_password:
        auth = httpx.BasicAuth(settings.api_user, settings.api_password.get_secret_value())
    headers = {"User-Agent": "fotomind-worker"}
    if settings.worker_token:
        headers[WORKER_TOKEN_HEADER] = settings.worker_token.get_secret_value()
    return httpx.Client(
        base_url=settings.api_url.rstrip("/"),
        auth=auth,
        timeout=settings.request_timeout_s,
        headers=headers,
        # Retries connection failures only (not HTTP errors): Wi-Fi blips, Caddy restarts.
        transport=httpx.HTTPTransport(retries=3),
    )
