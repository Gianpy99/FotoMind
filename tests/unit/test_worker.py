import httpx
import pytest

from fotomind.workers import cli
from fotomind.workers.client import api_client
from fotomind.workers.config import WorkerSettings


def test_api_client_uses_portal_basic_auth() -> None:
    settings = WorkerSettings(
        api_url="https://photos.example/", api_user="family", api_password="pw", _env_file=None
    )
    with api_client(settings) as client:
        assert str(client.base_url) == "https://photos.example"
        assert isinstance(client.auth, httpx.BasicAuth)


def test_ping_reports_success(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"path": request.url.path})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        cli, "api_client", lambda s: httpx.Client(base_url=s.api_url, transport=transport)
    )
    assert cli.main(["ping"]) == 0
    assert "/api/v1/me -> 200" in capsys.readouterr().out
